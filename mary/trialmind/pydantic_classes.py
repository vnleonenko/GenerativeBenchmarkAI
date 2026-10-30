from pydantic import BaseModel, validator, Field, field_validator, conlist,BeforeValidator
from typing_extensions import Literal
from typing import Dict,Annotated


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
    common_patterns: list[str] = Field(description="Common patterns representing how the root cause manifests in this cluster", min_length=1, max_length=5)

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
    sample_index: int
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