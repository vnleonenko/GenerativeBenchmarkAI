
from .llm import (
    batch_function_call_llm,
)
from .prompts.screening import LITERATURE_SCREENING_FC2
import httpx
from pydantic import BaseModel, validator, Field,field_validator, conlist  
from typing_extensions import Literal
from typing import Dict


import logging
logger = logging.getLogger().setLevel(logging.INFO)
# Silence other loggers
for log_name, log_obj in logging.Logger.manager.loggerDict.items():
    if log_name != 'my_module_name':
        log_obj.disabled = True
        
httpx_client = httpx.Client(verify=False,trust_env=False,)#,proxy="socks5://127.0.0.1:10808")


class LiteratureScreening:
    """Pass the papers through the screening criteria to determine if they are relevant to the research question.
    The input contains a list of criteria for screening the papers, and the papers to be screened.

    Args:
        papers: A list of clinical study papers' raw content in text, to be screened.
        criteria: A list of screening criteria for the papers.
        llm: The language model to use for the screening. Default is "gpt-4".
    """
    def __init__(self):
        pass

    def run(self,
        #population: str,
        #intervention: str,
        #comparator: str,
        #outcome: str,
        papers: list[str],
        criteria: list[str],
        llm: str="gpt-4",
        batch_size: int = None,
        ):

        # build the criteria text with index
        criteria_text = [f"{idx+1}. {c}" for idx, c in enumerate(criteria)]
        n_criteria = len(criteria_text)

        # build batch inputs
        batch_inputs = []
        for paper in papers:
            batch_inputs.append({
                #"P": population,
                #"I": intervention,
                #"C": comparator,
                #"O": outcome,
                "paper_content": paper,
                "criteria_text": criteria_text,
                "num_criteria": n_criteria
            })

        # call llm
        #from langchain.pydantic_v1 import BaseModel, validator, Field, conlist
        
        class PaperEvaluation(BaseModel):
            evaluations: conlist(Literal['YES', 'NO', 'UNCERTAIN'], min_length=n_criteria, max_length=n_criteria) = Field(description=f"Evaluations for {n_criteria} criteria")
            rationale: conlist(str,min_length=n_criteria, max_length=n_criteria) = Field(description="A rationale for each criteria evaluation")
        #outputs = batch_function_call_llm(LITERATURE_SCREENING_FC, batch_inputs, [PaperEvaluation.model_json_schema()], llm=llm, batch_size=batch_size) 
        
        
        outputs = batch_function_call_llm(LITERATURE_SCREENING_FC2, batch_inputs, [PaperEvaluation], llm=llm, batch_size=batch_size)

        return outputs
    
    