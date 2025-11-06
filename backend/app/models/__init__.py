from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    size_bytes: int
    uploaded_at: datetime
    message: str


class IngestRequest(BaseModel):
    doc_id: str


class IngestResponse(BaseModel):
    doc_id: str
    chunks_created: int
    vectors_upserted: int
    message: str


class Citation(BaseModel):
    doc_id: str
    title: str
    page: Optional[int] = None
    chunk_text: str
    score: float
    metadata: Optional[Dict[str, Any]] = None


class CompletenessCheck(BaseModel):
    confidence: float = Field(..., ge=0.0, le=1.0, description="0-1 confidence score")
    completeness: float = Field(..., ge=0.0, le=1.0, description="0-1 completeness score")
    is_complete: bool = Field(..., description="Whether answer is complete (>= 85% threshold)")
    missing_information: Optional[str] = Field(None, description="What info is missing")
    suggested_documents: List[str] = Field(default_factory=list, description="Docs to add")
    suggested_actions: List[str] = Field(default_factory=list, description="Actions to take")
    search_queries: List[str] = Field(default_factory=list, description="Wikipedia search terms")


class ExternalSource(BaseModel):
    title: str
    summary: str
    url: str
    source: str  # e.g., "Wikipedia"


class EnrichmentData(BaseModel):
    enrichment_performed: bool
    sources_found: List[ExternalSource] = Field(default_factory=list)
    search_terms: List[str] = Field(default_factory=list)
    message: str


class AskRequest(BaseModel):
    question: str
    doc_filter: Optional[List[str]] = Field(None, description="Filter by doc_ids")
    auto_enrich: bool = Field(True, description="Auto-fetch external sources if incomplete")


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: List[Citation]
    completeness_check: CompletenessCheck
    enrichment_data: Optional[EnrichmentData] = None
    latency_ms: float
    retrieved_docs: List[Dict] = Field(default_factory=list, description="Raw retrieval results for rating")
    documents_used: List[str] = Field(default_factory=list, description="Document names used")


class RatingRequest(BaseModel):
    question: str
    answer: str
    rating: str = Field(..., pattern="^(up|down)$", description="'up' or 'down'")
    feedback_text: Optional[str] = Field(None, description="Optional user feedback")
    documents_used: List[str] = Field(..., description="List of document names used")
    retrieved_docs: List[Dict] = Field(..., description="Raw retrieval results with scores")
    completeness: str = Field(..., pattern="^(complete|incomplete)$", description="'complete' or 'incomplete'")


class RatingResponse(BaseModel):
    rating_id: str
    should_update_docs: bool
    reason: str
    message: str


class IngestUrlRequest(BaseModel):
    url: str = Field(..., description="URL to scrape and ingest")
    title: Optional[str] = Field(None, description="Optional custom title")


class IngestUrlResponse(BaseModel):
    success: bool
    message: str
    doc_id: Optional[str] = None
    already_exists: bool = Field(False, description="True if URL was already in KB")
    chunks_created: Optional[int] = None


class CheckUrlRequest(BaseModel):
    url: str = Field(..., description="URL to check")


class CheckUrlResponse(BaseModel):
    exists: bool
    doc_id: Optional[str] = None

