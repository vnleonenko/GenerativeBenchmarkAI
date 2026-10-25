from pydantic import BaseModel, validator, Field, field_validator, conlist,BeforeValidator
from typing_extensions import Literal
from typing import Dict,Annotated
# ================== Clinical trials, choosing outcomes/groups

def ct_res_eval(full_outs, full_gr, full=False):
    class ResultEval(BaseModel):
        id: int = Field(description='Index of the result')
        reasoning: str = Field(description='Explain: why this result was included or excluded? UNDER 500 characters',max_length=500)
        decision: Literal['YES', 'NO'] = Field(description='Decision: YES (to include) or NO (to exclude)')

        @field_validator('reasoning', mode='before')
        @classmethod
        def truncate_f(cls, v):
            return v[:500]

    class CTChosenOutcomes(BaseModel):
        reasoning_main: str = Field(description="Explain: if there're complications about choosing outcomes and matching measures, how to solve them? UNDER 1000 characters",max_length=1000)
        result_eval: list[ResultEval] = Field(description='Explain: why each outcome measure was included or excluded (starting from 0)?',
                                                min_length=len(full_outs), 
                                                max_length=len(full_outs))
        chosen_ids: list[int] = Field(description='Indexes of chosen outcomes')
        ids_of_mentioned_measures: list[int] = Field(description='Index of the mentioned measure for each chosen outcome')

        @field_validator('reasoning_main', mode='before')
        @classmethod
        def truncate_f(cls, v):
            return v[:1000]
        
    class CTChosenGroups(BaseModel):
        result_eval: list[ResultEval] = Field(description='Explain: why each participant group was included or excluded (starting from 0)?',
                                                min_length=len(full_gr), 
                                                max_length=len(full_gr))
        chosen_ids: list[int] = Field(description='Indexes of chosen groups')

    class CTFinalDecisions(BaseModel):
        original_id: list[int] = Field(description='Id of the original group; -1 if not applicable')
        parent_group_id: int = Field(description='Id of the parent group; -1 if not applicable')
        enhanced_group_name: str = Field(description='Enhanced group name; UNDER 80 chars')
        matching_outcome_ids: list[int] = Field(description='Indexes of outcomes  where the group appears')

    class CTChosenGroupsOutcomes(BaseModel):
        reasoning_main: str = Field(description="Explain: if there're complications about matching groups to outcomes, how to solve them? UNDER 1500 characters",max_length=1500)
        orig_participant_groups: CTChosenGroups
        orig_outcome_measures: CTChosenOutcomes
        final_decisions: list[CTFinalDecisions]

        @field_validator('reasoning_main', mode='before')
        @classmethod
        def truncate_f(cls, v):
            return v[:1500]
    
    if full:
        return CTChosenGroupsOutcomes, CTChosenGroups,CTChosenOutcomes,CTFinalDecisions, ResultEval
    else:
        return CTChosenGroupsOutcomes



class ResultEval(BaseModel):
    id: int = Field(description='Index of the result')
    reasoning: str = Field(description='Explain: why this result was included or excluded? UNDER 500 characters',max_length=500)
    decision: Literal['YES', 'NO'] = Field(description='Decision: YES (to include) or NO (to exclude)')

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_f(cls, v):
        return v[:500]

class CTChosenOutcomes(BaseModel):
    reasoning_main: str = Field(description="Explain: if there're complications about choosing outcomes and matching measures, how to solve them? UNDER 1000 characters",max_length=1000)
    result_eval: list[ResultEval] = Field(description='Explain: why each outcome measure was included or excluded (starting from 0)?')
    chosen_ids: list[int] = Field(description='Indexes of chosen outcomes')
    ids_of_mentioned_measures: list[int] = Field(description='Index of the mentioned measure for each chosen outcome')

    @field_validator('reasoning_main', mode='before')
    @classmethod
    def truncate_f(cls, v):
        return v[:1000]
    
class CTChosenGroups(BaseModel):
    result_eval: list[ResultEval] = Field(description='Explain: why each participant group was included or excluded (starting from 0)?')
    chosen_ids: list[int] = Field(description='Indexes of chosen groups')

class CTFinalDecisions(BaseModel):
    original_id: list[int] = Field(description='Id of the original group; -1 if not applicable')
    parent_group_id: int = Field(description='Id of the parent group; -1 if not applicable')
    enhanced_group_name: str = Field(description='Enhanced group name; UNDER 80 chars')
    matching_outcome_ids: list[int] = Field(description='Indexes of outcomes  where the group appears')

class CTChosenGroupsOutcomesNoVal(BaseModel):
    reasoning_main: str = Field(description="Explain: if there're complications about matching groups to outcomes, how to solve them? UNDER 1500 characters",max_length=1500)
    orig_participant_groups: CTChosenGroups
    orig_outcome_measures: CTChosenOutcomes
    final_decisions: list[CTFinalDecisions]

    @field_validator('reasoning_main', mode='before')
    @classmethod
    def truncate_f(cls, v):
        return v[:1500]


    
def safe_int_convert(value):
    if isinstance(value, str):
        try:
            return float(value) 
        except ValueError:
            return -1.          
    return value

our_float = Annotated[float, BeforeValidator(safe_int_convert)]

class CTMeasure(BaseModel):
    measure : str
    value : our_float
    lo : our_float
    hi : our_float
    small_n : our_float
    orig : our_float

class CTGroup(BaseModel):
    title : str
    new_n: str
    N : our_float
    measures :list[CTMeasure]
    
class ChoiceCT(BaseModel):
    id : str
    groups : list[CTGroup]


# ==================
      
class TranslatedText(BaseModel):
    reasoning: str = Field(description='Explain: where and how each term was translated?; UNDER 2000 characters')
    translation: str = Field(description='The final translation')
    
    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate(cls, v):
        return v[:2000]

    
class FieldResult(BaseModel):
    name: str = Field( description='Field name that accurately represents the content of the field based on its description; UNDER 100 characters',
     max_length=100)
    reasoning: str = Field(description='Explain: why this value of data was chosen for extraction, why these documents were cited, how the percentage was calculated? UNDER 300 characters',
                              max_length=300)
    value: str = Field(description='Extracted information from the text based on the field description; UNDER 300 characters',
                      max_length=300)
    source_id: conlist(int, min_length=0, max_length=3) = Field(description='Cited document IDs; MAX 3 items.')
    
    @field_validator('source_id', mode='before')
    @classmethod
    def truncate(cls, v):
        return v[:3]
        
    @field_validator('name', mode='before')
    @classmethod
    def truncate_n(cls, v):
        return v[:100]
        
    @field_validator('value', mode='before')
    @classmethod
    def truncate_v(cls, v):
        return v[:300]

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_r(cls, v):
        return v[:300]
        

class Results(BaseModel):
    fieldresult: list[FieldResult] = Field(min_length=1, max_length=1)


#An observational study, by contrast, does not assign participants to a treatment. Instead, researchers collect and analyse data generated during routine clinical practice to understand outcomes in a real‑world setting
class FieldResultSType(BaseModel):
    name: str = Field( description='Field name that accurately represents the content of the field based on its description; UNDER 100 characters',
     max_length=100)
    reasoning: str = Field(description='Explain: why this value of data was chosen for extraction, why these documents were cited, how the percentage was calculated? UNDER 300 characters',
                              max_length=300)
    value: Literal["clinical study","case report","study","review","other"] = \
    Field(description='Extracted information from the text based on the field description. `Clinical study` -- clinical trials or observational studies that test interventions and/or report results for clinically relevant efficacy outcomes (ORR, DCR, ...), `case report` -- a clinical presentation of a single patient or small group with clinically relevant efficacy outcomes, `study` -- comparative/evaluation/validation study that assesses/compares a specific program, intervention, or tool on a targeted group of subjects with clinically relevant efficacy outcomes, `review` -- overview of peer-reviewed studies/clinical trials in health and synthesis of empirical evidence with clinically relevant efficacy outcomes, `other` -- another study type not mentioned above, usually experimental, preclinical (in vitro, in vivo) research reporting results for biologically relevant efficacy outcomes (tumour regression, ...); UNDER 200 characters',
                      max_length=200)
    source_id: conlist(int, min_length=0, max_length=3) = Field(description='Cited document IDs; MAX 3 items.')
    
    @field_validator('source_id', mode='before')
    @classmethod
    def truncate(cls, v):
        return v[:3]
        
    @field_validator('name', mode='before')
    @classmethod
    def truncate_n(cls, v):
        return v[:100]
        
    @field_validator('value', mode='before')
    @classmethod
    def truncate_v(cls, v):
        return v[:300]

    @field_validator('reasoning', mode='before')
    @classmethod
    def truncate_r(cls, v):
        return v[:300]


class ResultsSType(BaseModel):
    fieldresult: list[FieldResultSType] = Field(min_length=1, max_length=1)


class GroupOutcomesOLD(BaseModel):
    reasoning: str = Field(description='Explain: where and why each value was chosen, how each percentage was calculated?')

    group_name: str = Field(description='Description of the analyzed group based on a measure title field, a population description field and a group title field; UNDER 100 characters', max_length=100)
    population_size: int = Field(description='Population size of the analyzed group; number of participants; value GREATER or EQUAL TO 0', ge=0)
    
    complete_response: float = Field(description='Complete Response (CR); percentage of participants; value UNDER or EQUAL TO 100.0', le=100.0)
    partial_response: float = Field(description='Partial Response (PR); percentage of participants; value UNDER or EQUAL TO 100.0', le=100.0)
    objective_response_rate: float = Field(description='Objective Response Rate (ORR); ORR = CR + PR; percentage of participants; value UNDER or EQUAL TO 100.0', le=100.0)
    
    stable_disease: float = Field(description='Stable Disease (SD); percentage of participants; value UNDER or EQUAL TO 100.0', le=100.0)
    disease_control_rate: float = Field(description='Disease Control Rate (DCR); DCR = CR + PR + SD; percentage of participants; value UNDER or EQUAL TO 100.0', le=100.0)
    
    progression_free_survival_months: float = Field(description='Progression Free Survival (PFS); number of months; value GREATER or EQUAL TO 0')
    overall_survival_months: float = Field(description='Overall Survival (OS); number of months; value GREATER or EQUAL TO 0')
    progression_free_survival_weeks: float = Field(description='Progression Free Survival (PFS); number of weeks; value GREATER or EQUAL TO 0')
    overall_survival_weeks: float = Field(description='Overall Survival (OS); number of weeks; value GREATER or EQUAL TO 0')
    @field_validator('complete_response','partial_response','objective_response_rate',
                     'stable_disease','disease_control_rate','progression_free_survival_months',
                     'overall_survival_months',
                     'progression_free_survival_weeks','overall_survival_weeks',
                     mode='before')
    @classmethod
    def truncate_f(cls, v):
        return round(min(v,100.0),2)


class GroupOutcomes(BaseModel):
    reasoning: str = Field(description='Explain: where and why each value was chosen, how each percentage was calculated?')

    group_name: str = Field(description='Description of the analyzed group based on a measure title field, a population description field and a group title field; UNDER 100 characters', max_length=100)
    population_size: int = Field(description='Population size of the analyzed group; number of participants; value GREATER or EQUAL TO 0', ge=0)
    
    complete_response: float = Field(description='Complete Response (CR); percentage of participants; missing data: set value to -1, valid data: set value UNDER or EQUAL TO 100.0', le=100.0)
    partial_response: float = Field(description='Partial Response (PR); percentage of participants; missing data: set value to -1, valid data:  set value UNDER or EQUAL TO 100.0', le=100.0)
    objective_response_rate: float = Field(description='Objective Response Rate (ORR); ORR = CR + PR; percentage of participants; missing data: set value to -1, valid data: set value UNDER or EQUAL TO 100.0', le=100.0)
    
    stable_disease: float = Field(description='Stable Disease (SD); percentage of participants; set value UNDER or EQUAL TO 100.0', le=100.0)
    disease_control_rate: float = Field(description='Disease Control Rate (DCR); DCR = CR + PR + SD; percentage of participants; missing data: set value to -1, valid data: set value UNDER or EQUAL TO 100.0', le=100.0)
    
    progression_free_survival_months: float = Field(description='Progression Free Survival (PFS); number of months; missing data: set value to -1, valid data: set value GREATER or EQUAL TO 0')
    overall_survival_months: float = Field(description='Overall Survival (OS); number of months; missing data: set value to -1, valid data: set value GREATER or EQUAL TO 0')
    progression_free_survival_weeks: float = Field(description='Progression Free Survival (PFS); number of weeks; missing data: set value to -1, valid data: set value GREATER or EQUAL TO 0')
    overall_survival_weeks: float = Field(description='Overall Survival (OS); number of weeks; missing data: set value to -1, valid data: set value GREATER or EQUAL TO 0')
    
    @field_validator('complete_response','partial_response','objective_response_rate',
                     'stable_disease','disease_control_rate','progression_free_survival_months',
                     'overall_survival_months',
                     'progression_free_survival_weeks','overall_survival_weeks',
                     mode='before')
    @classmethod
    def truncate_f(cls, v):
        return round(min(v,100.0),2)
    

class ClinicalTrialOutcomes(BaseModel):
    main_reasoning: str = Field(description='Explain: what was included/excluded and why? List final chosen groups')
    groups_outcomes: list[GroupOutcomes] = Field(description='Extracted measurements for each chosen group.')


def sentence_eval(n_criteria):
    class SentenceEval(BaseModel):
        rationale_enhance: str = Field(description="The rationale for chosen enhancements",
                                      max_length=800)
        enhanced_ver: str = Field(description="The enhanced version of the sentence",
                                      max_length=400)
        rationale_evals: conlist(str,min_length=n_criteria, 
                           max_length=n_criteria
                          ) = Field(description="The rationale for each criteria evaluation")
        evaluations: conlist(Literal['YES', 'NO', 'UNCERTAIN'], 
                             min_length=n_criteria, max_length=n_criteria
                            ) = Field(description="Evaluations for each criteria")
    return SentenceEval


def results_eval(top_n,full_pr):    
    class ResultEval(BaseModel):
        id: int = Field(description='Index of the result')
        reasoning: str = Field(description='Reasoning for including or excluding the result',max_length=800)
        decision: Literal['YES', 'NO'] = Field(description='Decision to include: YES (to include) or NO (to exclude)')
        
    
    class ResultsEval(BaseModel):
        main_reasoning: str = Field(description='Reasoning for the final result set, why does it have these chosen results? UNDER 5000 characters')
        result_eval: list[ResultEval] = Field(description='Detailed reasoning for each result starting from 0',
                                             min_length=len(full_pr), 
                                              max_length=len(full_pr))
        chosen_ids: list[int] = Field(description='Indexes of top-10 results according to the criteria',
                                     max_length=top_n)
       
        @field_validator('main_reasoning',
                         mode='before')
        @classmethod
        def truncate_f(cls, v):
            return v[:5000]
        
    return ResultsEval,ResultEval
