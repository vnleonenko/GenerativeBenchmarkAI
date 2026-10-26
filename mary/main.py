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
from queries import PROMPT_NAME_ERRORS,PROMPT_CLUSTER_ERRORS


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

    
class Cluster(BaseModel):
    reasoning: str = Field(description='Explain briefly: why this cluster is necessary? UNDER 300 characters', max_length=300)
    index: int 
    name: str = Field(description="A concise description of the error cluster. UNDER 100 characters", max_length=100)

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
    return errors_df


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
