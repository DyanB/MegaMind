"""
MongoDB schemas for ratings and document scores
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class RatingDocument(BaseModel):
    """Rating document schema for MongoDB"""
    id: str = Field(alias="_id")
    user_id: Optional[str] = None  # Link to user who rated
    timestamp: datetime
    question: str
    answer: str
    rating: str  # "up" or "down"
    feedback_text: Optional[str] = None
    documents_used: List[str]
    completeness: str
    max_relevance_score: float
    
    class Config:
        populate_by_name = True


class DocumentScoreDocument(BaseModel):
    """Document score schema for MongoDB"""
    doc_id: str = Field(alias="_id")
    user_id: Optional[str] = None  # Who uploaded/owns this doc
    title: str
    upvotes: int = 0
    downvotes: int = 0
    total_votes: int = 0
    score: float = 0.0  # Calculated score
    last_updated: datetime
    
    class Config:
        populate_by_name = True


class RatingCreate(BaseModel):
    """Model for creating a new rating"""
    question: str
    answer: str
    rating: str
    documents_used: List[str]
    retrieved_docs: List[dict]
    completeness: str
    feedback_text: Optional[str] = None


class RatingResponse(BaseModel):
    """Response after saving a rating"""
    rating_id: str
    should_update_docs: bool
    reason: str
