import os
from dotenv import load_dotenv, find_dotenv

use = 'rogozin'
if use == 'rogozin':
    os.environ["BASE_URL"] = "http://localhost:8501/v1"
    os.environ["MODEL_NAME"] ='/models/Qwen3.6-27B-UD-Q4_K_XL.gguf'#'ggml-org/gemma-3-1b-it-GGUF'
    os.environ["TRANSL_MODEL_NAME"] = '/models/Qwen3.6-27B-UD-Q4_K_XL.gguf'
    os.environ["OPENAI_API_KEY"] = 'hello'
elif use == 'sirius':
    os.environ["BASE_URL"] = "http://127.0.0.1:8082/v1"
    os.environ["MODEL_NAME"] ='Qwen3.6-27B'#'ggml-org/gemma-3-1b-it-GGUF'
    os.environ["OPENAI_API_KEY"] = 'hello'
    os.environ["TRANSL_MODEL_NAME"] = 'Qwen3.6-27B'
os.environ['TEMPERATURE'] = '0'

import ftfy
import logging
import time
import numpy as np
import pandas as pd
from pathlib import Path
from pydantic import BaseModel, validator, Field, field_validator, conlist,BeforeValidator
from typing_extensions import Literal
from typing import Dict,Annotated
from sklearn.model_selection import train_test_split

from queries import papers_criteria as papers_criteria
from queries import *
from trialmind.pubmed import pmid2papers, PubmedAPIWrapper
from trialmind.api import LiteratureScreening
from trialmind.llm_utils.openai_async import batch_function_call_openai,batch_call_openai
from trialmind.pydantic_classes import *



load_dotenv(find_dotenv(usecwd=True), override=True)

    
def run_screening(pmid_list, fin_condition, treatment,
                  ps_thresh = [1,1,0], real=False):
    # collect text from pmid
    logging.info('COLLECTING PAPER TEXTS')
    start = time.time()
    df_papers = pmid2papers(pmid_list=pmid_list,
                     api_key=os.getenv("PUBMED_API_KEY"))[0]
    df_papers[['Title','Abstract']] = df_papers[['Title','Abstract']].fillna('')
    df_papers['Abstract'] = df_papers['Abstract'].fillna(''
                                                         ).apply(ftfy.fix_text)
    papers = df_papers["Title"] + ": " +\
                    df_papers["Abstract"].fillna("")
    #papers = papers.tolist()
    # https://pubmed.ncbi.nlm.nih.gov/27454254/
    papers = [i[:5000] for i in papers.tolist()]
    
    end = time.time()
    logging.info(end-start)
    start = end
    logging.info('SCREENING PAPERS')

    # screening
    if real:
        api = LiteratureScreening()
        ec_predP = api.run(
            llm = os.getenv("MODEL_NAME"),
            criteria = [i.format(fin_condition=fin_condition,
                                treatment=treatment) for i in papers_criteria],
            papers = papers, 
        )

        
        evalsP = [i.evaluations for i in ec_predP]
        word2int = {"YES": 1, "UNCERTAIN": 0, "NO": -1}
        new_evalsP = []
        for one_e in evalsP:
            new_evalsP.append([word2int.get(item, 0) for item in one_e ])
        new_evalsP = np.array(new_evalsP)  

        df_p_e = df_papers
        df_p_e[['s1','s2','s3']] = new_evalsP
        df_p_e[['r1','r2','r3']] = [i.rationale for i in ec_predP]

    else:
        df_p_e = pd.read_csv('new_criteria_qwen36_27b.csv')
        df_p_e.PMID = df_p_e.PMID.apply(lambda x: str(x.split('/')[-1]))
        df_p_e = df_p_e[df_p_e.PMID.isin(pmid_list)]

        df_papers['Fin_text'] = df_papers[['Title','Abstract']
                                   ].apply(lambda x: x["Title"] + ": " +x["Abstract"], 
                                           axis=1)
        df_p_e= pd.merge(df_p_e, 
                 df_papers[['PMID','Fin_text']],
                 on='PMID'
                 )
        df_p_e = df_p_e.set_index('PMID').reindex(index = pmid_list).reset_index()

    # filtering
    '''
    chosen_df = df_p_e[(df_p_e['s1']>=ps_thresh[0]
                    )&(df_p_e['s2']>=ps_thresh[1]
                        )&(df_p_e['s3']>=ps_thresh[2])]
    logging.info(chosen_df.shape[0])
    '''
    end = time.time()
    logging.info(end-start)
    start = end
    return df_p_e


def find_mistakes(df_pred, df_expert):
    df_pred.PMID = df_pred.PMID.astype(str)
    pmid_list=df_pred.PMID.values
    df_long = pd.wide_to_long(df_pred, stubnames=['s', 'r'], 
                              i='PMID', j='num').reset_index()
    df_longe = pd.wide_to_long(df_expert.iloc[:,:-1], stubnames=['s', 'r'], 
                               i='PMID', j='num').reset_index()
    merged = pd.merge(df_long,
            df_longe, how='outer',
            on=['PMID','num'],suffixes=('_pred','_expert')
            ).sort_values(by='PMID')
    errors_df = merged[merged.s_pred!=merged.s_expert]
    correct_df = merged[merged.s_pred==merged.s_expert]
    return errors_df, correct_df


def find_ind_errors(errors_df,fin_condition,treatment):

    user_prompt0 = """
    eligibility_criteria = "{eligibility_criteria}"
    abstract = "{abstract}"
    model_rationale = "{model_rationale}"
    expert_rationale = "{expert_rationale}"
    model_score = {model_score}
    expert_score = {expert_score}
    your_response = 
    """
    messages = []
    
    for error_one in errors_df.values:
        pmid, num,abstract,model_score,model_rationale,expert_score,expert_rationale =  error_one
        logging.info(f"{pmid}, {num}, {model_rationale[:200]}")
        user_prompt = user_prompt0.format(eligibility_criteria = \
                                         papers_criteria[num-1].format(treatment=treatment,
                                                                       fin_condition=fin_condition),
                                 abstract=abstract,
                                 model_rationale=model_rationale,
                                 expert_rationale=expert_rationale,
                                 model_score=model_score,
                                 expert_score=expert_score)
        
        messages.append([{'pmid':pmid},
                            {'role':'system', 
                            'content':PROMPT_NAME_ERRORS+' \no_think'},
                            {'role':'user', 'content':user_prompt}
                        ])

    #print([i[2:] for i in messages])
    outputs = batch_function_call_openai([i[1:] for i in messages], 
                                    os.getenv('MODEL_NAME'), 
                                    [ErrorIdentify],
                                    int(os.getenv('TEMPERATURE', 0)), 
                                    thinking=False)
        
    #errors_df['error_id'] = [i.model_dump_json() for i in outputs]
    errors_df.loc[:,['error_id_reason','error_id']] = [[i.reasoning, i.error]
                                                 for i in outputs]    
    '''for paper_id, one_response in enumerate(outputs):
        errors_df.iloc[paper_id,
                            errors_df.columns.get_loc('enhanced')
                            ] = one_response.model_dump_json()
        #logging.info(one_response)
        logging.info('')
        all_resp.append(one_response)

    logging.info(resultsct)'''
    return errors_df


def find_error_clusters(errors_df,fin_condition,treatment):
    errors = errors_df[['PMID','num','error_id']]
   # errors.loc[:,'error_id'] = errors['error_id'].apply(lambda x: x.error)

    user_prompt0 = """
    eligibility_criteria = {eligibility_criteria}
    model_errors = {model_errors}
    your_response = 
    """
    messages = []

    unique_criteria = errors['num'].unique()
    eligibility_criteria = [papers_criteria[num-1].format(
                                treatment=treatment,
                                fin_condition=fin_condition
                                ) for num in unique_criteria]
    
    model_errors = 'error_index | criteria_num | error_description\n'
    for idx,i in enumerate(errors.iloc[:,1:].values):
        model_errors+=f"{idx} | {i[0]} | {i[1]}\n"

    user_prompt = user_prompt0.format(eligibility_criteria = eligibility_criteria,
                                model_errors=model_errors)
    print(user_prompt)
    messages.append([{'role':'system', 
                        'content':PROMPT_CLUSTER_ERRORS+' \no_think'},
                        {'role':'user', 'content':user_prompt}
                    ])

    outputs = batch_function_call_openai(messages, 
                                    os.getenv('MODEL_NAME'), 
                                    [ErrorsAndClusters],
                                    int(os.getenv('TEMPERATURE', 0)), 
                                    thinking=False
                                    )[0]
        
    errors_df.loc[:,['error_type_reason','error_type']] = [[i.reasoning, 
                                *[j.name for j in outputs.clusters if j.index==i.cluster_index]] 
                                for i in outputs.errors]

    return errors_df,outputs


def augment_samples(error_type_df,correct_df,
                    error_class,
                    pmid_list,
                    fin_condition,treatment):
    
    error_type_df.PMID = error_type_df.PMID.astype(str)
    user_prompt0 = """
    error_types = {error_types}
    eligibility_criteria = {eligibility_criteria}
    abstract = {abstract}
    expert_screening = {expert_screening}
    your_response = 
    """
    messages = []

    error_types = 'error_index | error_type_description | common_patterns\n'
    for idx,cl_name in enumerate(error_type_df.error_type.unique()):
        notable_p = [c for c in error_class.clusters if c.name==cl_name][0]
        error_types+=f"{idx} | {cl_name} | {notable_p.common_patterns}\n"
    #print(error_types)

    eligibility_criteria_t = [papers_criteria[num].format(
                                treatment=treatment,
                                fin_condition=fin_condition
                                ) for num in range(0,3)]

    eligibility_criteria = "criteria_index | criteria_description\n"
    for idx,i in enumerate(eligibility_criteria_t):
        eligibility_criteria+=f"{idx} | {i}\n"
    #print(eligibility_criteria)

    for pmid in pmid_list:
        abstract = correct_df[correct_df.PMID==pmid].Fin_text.iloc[0]

        expert_screening = "criteria_index | score | rationale\n"
        for idx,i in enumerate(correct_df[correct_df.PMID==pmid
                                          ].sort_values('num').values):
            expert_screening+=f"{i[1]-1} | {i[-2]} | {i[-1]}\n"

        user_prompt = user_prompt0.format(error_types = error_types,
                                    eligibility_criteria=eligibility_criteria,
                                    abstract=abstract,
                                    expert_screening=expert_screening)
        
        messages.append([{'role':'system', 
                            'content':PROMPT_AUGMENT+' \no_think'},
                            {'role':'user', 'content':user_prompt}
                        ])

    outputs = batch_function_call_openai(messages, 
                                    os.getenv('MODEL_NAME'), 
                                    [AugmentedSamples],
                                    int(os.getenv('TEMPERATURE', 0)), 
                                    #0.7,
                                    thinking=False
                                    )
    alldf = []
    for i,pmid in enumerate(pmid_list):
        df_final = pd.DataFrame([d.model_dump() for d in outputs[i].new_samples])
        df_final['PMID'] = pmid
        alldf.append(df_final)
    alldf = pd.concat(alldf)    

    '''errors_df.loc[:,['error_type_reason','error_type']] = [[i.reasoning, 
                                *[j.name for j in outputs.clusters if j.index==i.cluster_index]] 
                                for i in outputs.errors]
    '''
    return outputs,alldf



def add_correct_scores(change_df,
                    fin_condition,treatment):
    
    user_prompt0 = """
    new_abstracts = {new_abstracts}
    eligibility_criteria = {eligibility_criteria}
    your_response = 
    """

    eligibility_criteria_t = [papers_criteria[num].format(
                                treatment=treatment,
                                fin_condition=fin_condition
                                ) for num in range(0,3)]

    eligibility_criteria = "criteria_index | criteria_description\n"
    for idx,i in enumerate(eligibility_criteria_t):
        eligibility_criteria+=f"{idx} | {i}\n"
    #print(eligibility_criteria)

    messages = []

    pmid_list = list(change_df.PMID.unique())

    for pmid in pmid_list:
        error_types = 'error_type_index | change_reasoning | new_abstract\n'
        for c_name in change_df[change_df.PMID==pmid].values:
            error_types+=f"{c_name[0]} | {c_name[1]} | {c_name[2]}\n"
        #print(error_types)
    
        user_prompt = user_prompt0.format(new_abstracts = error_types,
                                    eligibility_criteria=eligibility_criteria)
        
        messages.append([{'role':'system', 
                            'content':PROMPT_ADD_KNOWN_SCORE+' \no_think'},
                            {'role':'user', 'content':user_prompt}
                        ])

    outputs = batch_function_call_openai(messages, 
                                    os.getenv('MODEL_NAME'), 
                                    [SamplesWIthScore],
                                    int(os.getenv('TEMPERATURE', 0)), 
                                    #0.7,
                                    thinking=False
                                    )
    alldf = []
    for i,pmid in enumerate(pmid_list):
        df = pd.DataFrame([d.model_dump() for d in outputs[i].new_samples])
        # превращая каждый элемент в отдельную строку
        df_exploded = df.explode("new_ground_truth").reset_index(drop=True)
        # Разворачиваем словари в отдельные колонки
        df_c = pd.json_normalize(df_exploded["new_ground_truth"])
        df_final = pd.concat([df_exploded.drop(columns=["new_ground_truth"]), df_c], axis=1)

        df_final['PMID'] = pmid
        alldf.append(df_final)

    alldf = pd.concat(alldf)   

    '''errors_df.loc[:,['error_type_reason','error_type']] = [[i.reasoning, 
                                *[j.name for j in outputs.clusters if j.index==i.cluster_index]] 
                                for i in outputs.errors]
    '''
    return outputs,alldf


if __name__=='__main__':

    #error_type_df = pd.read_csv('outputs/error_type_df.csv', index_col=0)
    the_path = 'outputs/'
    real = False # to screen
    fin_condition='Colorectal cancer'
    treatment='Crizotinib'

    # ____ real expert answers
    df_expert = pd.read_csv('new_criteria_ana_en2.csv')
    df_expert['PMID'] = df_expert['PMID'].astype(str)
    df_expert[['s1','s2','s3']] = df_expert[['s1','s2','s3']].astype(int)
    X = df_expert.iloc[:,:1]
    y = df_expert.iloc[:,]
    # stratify by accept/not accept. maybe instead by [1,1,0]?
    X_train, X_test, y_train, y_test = train_test_split(X,y, train_size=0.7, 
                                                        random_state=42,stratify=df_expert.accept)
    
    # ____ model's screening
    if os.path.exists(f"{the_path}/screening.csv"):
        screened_df = pd.read_csv(f"{the_path}screening.csv")
    else:
        screened_df = run_screening(pmid_list=X_train.PMID.values, 
                            fin_condition=fin_condition, 
                            treatment=treatment,
                            ps_thresh = [1,1,0], real=real)
        screened_df.to_csv(f"{the_path}/screening.csv",index=False)
    
    # ____ mistakes
    errors_df, correct_df = find_mistakes(screened_df, y_train)
    correct_df_grouped = correct_df.groupby('PMID').count()['num']

    # ____ error identification
    if os.path.exists(f"{the_path}/error_id_df.csv"):
        error_id_df = pd.read_csv(f"{the_path}/error_id_df.csv")
    else:
        error_id_df = find_ind_errors(errors_df=errors_df,
                                fin_condition=fin_condition, 
                                    treatment=treatment)
        error_id_df.to_csv(f"{the_path}/error_id_df.csv", index=False)

    # ____ clustering errors
    if os.path.exists(f"{the_path}/error_type_c.json"):
        error_type_df = pd.read_csv(f"{the_path}/error_type_df.csv")
        file_path = Path(f"{the_path}/error_type_c.json")
        file_content = file_path.read_text(encoding="utf-8")
        error_type_c = ErrorsAndClusters.model_validate_json(file_content)
    else:
        error_type_df, error_type_c = find_error_clusters(error_id_df,
                                                    fin_condition, treatment)
        error_type_df.to_csv(f"{the_path}/error_type_df.csv", index=False)
        file_path = Path(f"{the_path}/error_type_c.json")
        file_path.write_text(error_type_c.model_dump_json(indent=2), encoding="utf-8")

    print(error_type_c.clusters)
    error_types = 'error_index | error_type_description | common_patterns\n'
    for idx,cl_name in enumerate(error_type_df.error_type.unique()):
        notable_p = [c for c in error_type_c.clusters if c.name==cl_name][0]
        error_types+=f"{idx} | {cl_name} | {notable_p.common_patterns}\n"
    print(error_types)

    # ____ augmenting samples
    if os.path.exists(f"{the_path}/augmented_df.csv"):
        augmented_df = pd.read_csv(f"{the_path}/augmented_df.csv")
        #file_path = Path(f"{the_path}/augmented_c.json")
        #file_content = file_path.read_text(encoding="utf-8")
        #augmented_c = AugmentedSamples.model_validate_json(file_content)
    else:
        augmented_c,augmented_df = augment_samples(error_type_df,correct_df,
                                error_type_c,
                                correct_df_grouped[correct_df_grouped==3
                                                   ].index.values[:2],
                                fin_condition,treatment)
        augmented_df.to_csv(f"{the_path}/augmented_df.csv", index=False)
        #file_path = Path(f"{the_path}/augmented_c.json")
        #file_path.write_text(augmented_c.model_dump_json(indent=2), encoding="utf-8")

    print(augmented_df.drop(columns=['new_abstract']).values)

    # ____ generating new expert answers
    if os.path.exists(f"{the_path}/correct_score_df.csv"):
        correct_score_df = pd.read_csv(f"{the_path}/correct_score_df.csv")
        #file_path = Path(f"{the_path}/correct_score_c.json")
        #file_content = file_path.read_text(encoding="utf-8")
        #correct_score_c = SamplesWIthScore.model_validate_json(file_content)
    else:
        correct_score_c,correct_score_df = add_correct_scores(augmented_df,
                                fin_condition, treatment)
        correct_score_df.to_csv(f"{the_path}/correct_score_df.csv", index=False)
        #file_path = Path(f"{the_path}/correct_score_c.json")
        #file_path.write_text(correct_score_c.model_dump_json(indent=2), encoding="utf-8")
    print(correct_score_df.head(5))
    print(correct_score_df.values)