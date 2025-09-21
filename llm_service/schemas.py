from pydantic import BaseModel
from typing import List, Dict

class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    answer: str
    processing_time: float 

class UrlInjectionRequest(BaseModel):
    urls: List[str]

class DeleteRequest(BaseModel):
    url: str

class MetadataQueryResponse(BaseModel):
    metadata_counts: Dict[str, int]

class DebugPoint(BaseModel):
    id: str
    payload: Dict
    vector: List[float]

class DebugResponse(BaseModel):
    points: List[DebugPoint]    



