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
from queries import PROMPT_NAME_ERRORS


class ErrorIdentify(BaseModel):
    reasoning: str = Field(description='Explain: why the model assessment was incorrect? UNDER 600 characters', max_length=600)
    error: str = Field(description="A concise description of the model's error. UNDER 400 characters", max_length=400)

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_f(cls, v):
        return v[:600]

    @field_validator('error', mode='before')
    @classmethod
    def truncate_fs(cls, v):
        return v[:400]
    

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

    user_prompt = """
    eligibility_criteria = "{eligibility_criteria}"
    abstract = "{abstract}"
    model_rationale = "{model_rationale}"
    expert_rationale = "{expert_rationale}"
    model_score = {model_score}
    expert_score = {expert_score}
    your_response = 
    """
    resultsct = {}
    messages = []
    
    for error_one in errors_df.values:
        pmid, num,abstract,model_score,model_rationale,expert_score,expert_rationale =  error_one

        user_prompt = user_prompt.format(eligibility_criteria = \
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


    outputs = batch_function_call_openai([i[1:] for i in messages], 
                                    os.getenv('MODEL_NAME'), 
                                    [ErrorIdentify],
                                    int(os.getenv('TEMPERATURE', 0)), 
                                    thinking=False)
        
        
    '''for paper_id, one_response in enumerate(outputs):
        papers_res_fin.iloc[paper_id,
                            papers_res_fin.columns.get_loc('enhanced')
                            ] = one_response.model_dump_json()
        #logging.info(one_response)
        logging.info('')
        all_resp.append(one_response)

    logging.info(resultsct)'''
    return ErrorIdentify