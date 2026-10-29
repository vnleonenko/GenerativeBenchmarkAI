from trialmind.pubmed import pmid2papers, PubmedAPIWrapper
from trialmind.api import LiteratureScreening
from trialmind.llm_utils.openai_async import batch_function_call_openai

import os
import ftfy
import logging
import time
import numpy as np
import pandas as pd
from pydantic import BaseModel, validator, Field, field_validator, conlist,BeforeValidator
from typing_extensions import Literal
from typing import Dict,Annotated

from queries import papers_criteria as papers_criteria
from queries import PROMPT_NAME_ERRORS,PROMPT_CLUSTER_ERRORS, PROMPT_AUGMENT, PROMPT_ADD_KNOWN_SCORE


class ErrorIdentify(BaseModel):
    reasoning: str = Field(description='Explain: why the model assessment was incorrect? UNDER 800 characters', max_length=800)
    error: str = Field(description="A concise description of the model's error. UNDER 350 characters", max_length=350)

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_f(cls, v):
        return v[:800]

    @field_validator('error', mode='before')
    @classmethod
    def truncate_fs(cls, v):
        return v[:350]

# ---     
class Cluster(BaseModel):
    reasoning: str = Field(description='Explain briefly: why this cluster is necessary? UNDER 300 characters', max_length=300)
    index: int 
    name: str = Field(description="A concise description of the error cluster. UNDER 100 characters", max_length=100)
    notable_pointers: list[str] = Field(description="Short phrases describing how the root cause manifested in specific papers in this cluster", min_length=1, max_length=5)

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_r(cls, v):
        return v[:300]
    
    @field_validator('name', mode='before')
    @classmethod
    def truncate_fs(cls, v):
        return v[:100]
    
class Error(BaseModel):
    reasoning: str = Field(description='Explain briefly: why the error is in this cluster? UNDER 100 characters', max_length=100)
    error_index: int
    cluster_index: int

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_r(cls, v):
        return v[:100]

class ErrorsAndClusters(BaseModel):
    reasoning: str = Field(description='Briefly explain the clustering strategy. UNDER 1000 characters', max_length=1000)
    clusters: list[Cluster]
    errors: list[Error]

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_f(cls, v):
        return v[:1000]

    
# ---   
class CriteriaScore(BaseModel):
    criteria_index: int
    new_expert_rationale: str = Field(description='A rationale for a criterion evaluation; UNDER 350 characters', max_length=350)
    new_expert_score: Literal[1, -1, 0] = Field(description=f"Evaluation for a criterion")
    @field_validator('new_expert_rationale', mode='before')
    @classmethod
    def truncate_r(cls, v):
        return v[:350]

class ScreeningSample2(BaseModel):
    error_type_index: int
    reasoning: str = Field(description='Briefly explain the abstract changes and what it tests in the model. UNDER 350 characters', max_length=350)
    new_abstract: str = Field(description='Changed abstract. UNDER 3000 characters', max_length=3000)
    new_ground_truth: list[CriteriaScore]

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_r(cls, v):
        return v[:350]
    @field_validator('new_abstract', mode='before')
    @classmethod
    def truncate_a(cls, v):
        return v[:3000]

class ScreeningSample(BaseModel):
    error_type_index: int
    reasoning: str = Field(description='Briefly explain the abstract changes and what it tests in the model. UNDER 350 characters', max_length=350)
    new_abstract: str = Field(description='Changed abstract. UNDER 3000 characters', max_length=3000)

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_r(cls, v):
        return v[:350]
    @field_validator('new_abstract', mode='before')
    @classmethod
    def truncate_a(cls, v):
        return v[:3000]
    
class AugmentedSamples(BaseModel):
    new_samples: list[ScreeningSample]


class SampleScore(BaseModel):
    error_type_index: int
    reasoning: str = Field(description='Briefly explain what the change tests and what must be the correct answer. UNDER 350 characters', max_length=350)
    new_ground_truth: list[CriteriaScore]

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_r(cls, v):
        return v[:350]
    
class SamplesWIthScore(BaseModel):
    new_samples: list[SampleScore]

    
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

    error_types = 'error_index | error_type_description | notable_pointers\n'
    for idx,cl_name in enumerate(error_type_df.error_type.unique()):
        notable_p = [c for c in error_class.clusters if c.name==cl_name][0]
        error_types+=f"{idx} | {cl_name} | {notable_p.notable_pointers}\n"
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
    '''for i,pmid in enumerate(pmid_list):
        df = pd.DataFrame([d.model_dump() for d in outputs[i].new_samples])
        # превращая каждый элемент в отдельную строку
        df_exploded = df.explode("new_ground_truth").reset_index(drop=True)
        # Разворачиваем словари в отдельные колонки
        df_c = pd.json_normalize(df_exploded["new_ground_truth"])
        df_final = pd.concat([df_exploded.drop(columns=["new_ground_truth"]), df_c], axis=1)

        df_final['PMID'] = pmid
        alldf.append(df_final)
    alldf = pd.concat(alldf)    '''

    '''errors_df.loc[:,['error_type_reason','error_type']] = [[i.reasoning, 
                                *[j.name for j in outputs.clusters if j.index==i.cluster_index]] 
                                for i in outputs.errors]
    '''
    return outputs,alldf



def add_correct_scores(change_class,
                    fin_condition,treatment):
    
    user_prompt0 = """
    new_abstracts = {new_abstracts}
    eligibility_criteria = {eligibility_criteria}
    your_response = 
    """
    messages = []

    change_df = pd.DataFrame([j.model_dump() for i in change_class for j in i.new_samples])

    error_types = 'error_type_index | change_reasoning | new_abstract\n'
    for c_name in change_df.values:
        error_types+=f"{c_name[0]} | {c_name[1]} | {c_name[2]}\n"
    #print(error_types)

    eligibility_criteria_t = [papers_criteria[num].format(
                                treatment=treatment,
                                fin_condition=fin_condition
                                ) for num in range(0,3)]

    eligibility_criteria = "criteria_index | criteria_description\n"
    for idx,i in enumerate(eligibility_criteria_t):
        eligibility_criteria+=f"{idx} | {i}\n"
    #print(eligibility_criteria)

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
    for i,pmid in enumerate(outputs):
        df = pd.DataFrame([d.model_dump() for d in outputs[i].new_samples])
        # превращая каждый элемент в отдельную строку
        df_exploded = df.explode("new_ground_truth").reset_index(drop=True)
        # Разворачиваем словари в отдельные колонки
        df_c = pd.json_normalize(df_exploded["new_ground_truth"])
        df_final = pd.concat([df_exploded.drop(columns=["new_ground_truth"]), df_c], axis=1)

        #df_final['PMID'] = pmid
        alldf.append(df_final)
    alldf = pd.concat(alldf)   

    '''errors_df.loc[:,['error_type_reason','error_type']] = [[i.reasoning, 
                                *[j.name for j in outputs.clusters if j.index==i.cluster_index]] 
                                for i in outputs.errors]
    '''
    return outputs,alldf
