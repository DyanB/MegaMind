from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class QueryAnalytics(BaseModel):
    """Enhanced analytics for query tracking"""
    query_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    question: str
    answer_length: int
    
    # Metrics
    latency_ms: float
    confidence: float
    completeness: float
    is_complete: bool
    
    # Retrieved context
    contexts_retrieved: int
    documents_used: List[str]
    avg_retrieval_score: float
    
    # User feedback
    rating: Optional[int] = None  # 1-5 stars
    feedback_text: Optional[str] = None
    feedback_at: Optional[datetime] = None
    
    # Enrichment
    enrichment_triggered: bool = False
    external_sources_found: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "q_abc123",
                "user_id": "user_123",
                "question": "What is GPT-4?",
                "latency_ms": 1234.56,
                "confidence": 0.92,
                "completeness": 0.88,
                "is_complete": True,
                "contexts_retrieved": 10,
                "documents_used": ["gpt-4.pdf", "openai-docs"],
                "avg_retrieval_score": 0.85
            }
        }


class DocumentAnalytics(BaseModel):
    """Analytics for document usage"""
    doc_id: str
    title: str
    source_type: str  # web, upload, enrichment
    
    # Usage metrics
    total_queries: int = 0
    total_citations: int = 0
    avg_relevance_score: float = 0.0
    
    # Quality metrics
    user_ratings: List[int] = []
    avg_rating: float = 0.0
    
    # Timestamps
    added_at: datetime
    last_used_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "doc_id": "abc123",
                "title": "GPT-4 Technical Report",
                "source_type": "upload",
                "total_queries": 45,
                "total_citations": 120,
                "avg_relevance_score": 0.87,
                "avg_rating": 4.2
            }
        }


class UserAnalytics(BaseModel):
    """User behavior analytics"""
    user_id: str
    
    # Activity
    total_queries: int = 0
    total_documents_uploaded: int = 0
    total_feedback_given: int = 0
    
    # Quality
    avg_answer_completeness: float = 0.0
    avg_confidence: float = 0.0
    
    # Engagement
    first_activity_at: datetime
    last_activity_at: datetime
    active_days: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "total_queries": 150,
                "total_documents_uploaded": 12,
                "avg_answer_completeness": 0.82,
                "active_days": 15
            }
        }
