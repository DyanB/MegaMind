from typing import List, Optional
from datetime import datetime
import uuid
from app.database import get_database
from app.models.analytics import QueryAnalytics, DocumentAnalytics, UserAnalytics


class AnalyticsService:
    """Service for tracking and analyzing usage metrics"""
    
    def __init__(self):
        self.db = get_database()
        self.queries_collection = self.db.query_analytics
        self.documents_collection = self.db.document_analytics
        self.users_collection = self.db.user_analytics
    
    async def log_query(
        self,
        question: str,
        answer: str,
        user_id: Optional[str],
        session_id: Optional[str],
        latency_ms: float,
        confidence: float,
        completeness: float,
        is_complete: bool,
        contexts_retrieved: int,
        documents_used: List[str],
        avg_retrieval_score: float,
        enrichment_triggered: bool = False,
        external_sources_found: int = 0
    ) -> str:
        """Log a query with all metrics"""
        query_id = f"q_{uuid.uuid4().hex[:12]}"
        
        query_analytics = QueryAnalytics(
            query_id=query_id,
            user_id=user_id,
            session_id=session_id,
            question=question,
            answer_length=len(answer),
            latency_ms=latency_ms,
            confidence=confidence,
            completeness=completeness,
            is_complete=is_complete,
            contexts_retrieved=contexts_retrieved,
            documents_used=documents_used,
            avg_retrieval_score=avg_retrieval_score,
            enrichment_triggered=enrichment_triggered,
            external_sources_found=external_sources_found
        )
        
        await self.queries_collection.insert_one(query_analytics.dict())
        
        # Update user analytics if user is logged in
        if user_id:
            await self._update_user_analytics(user_id, completeness, confidence)
        
        # Update document analytics for used documents
        for doc_name in documents_used:
            await self._increment_document_usage(doc_name, avg_retrieval_score)
        
        return query_id
    
    async def log_feedback(
        self,
        query_id: str,
        rating: int,
        feedback_text: Optional[str] = None
    ):
        """Log user feedback for a query"""
        await self.queries_collection.update_one(
            {"query_id": query_id},
            {
                "$set": {
                    "rating": rating,
                    "feedback_text": feedback_text,
                    "feedback_at": datetime.utcnow()
                }
            }
        )
        
        # Get user_id from query
        query = await self.queries_collection.find_one({"query_id": query_id})
        if query and query.get("user_id"):
            await self.users_collection.update_one(
                {"user_id": query["user_id"]},
                {"$inc": {"total_feedback_given": 1}}
            )
    
    async def _update_user_analytics(
        self,
        user_id: str,
        completeness: float,
        confidence: float
    ):
        """Update user-level analytics"""
        existing = await self.users_collection.find_one({"user_id": user_id})
        
        if existing:
            # Update averages
            total = existing["total_queries"]
            new_total = total + 1
            new_avg_completeness = (
                (existing["avg_answer_completeness"] * total + completeness) / new_total
            )
            new_avg_confidence = (
                (existing["avg_confidence"] * total + confidence) / new_total
            )
            
            await self.users_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "total_queries": new_total,
                        "avg_answer_completeness": round(new_avg_completeness, 3),
                        "avg_confidence": round(new_avg_confidence, 3),
                        "last_activity_at": datetime.utcnow()
                    }
                }
            )
        else:
            # Create new user analytics
            user_analytics = UserAnalytics(
                user_id=user_id,
                total_queries=1,
                avg_answer_completeness=completeness,
                avg_confidence=confidence,
                first_activity_at=datetime.utcnow(),
                last_activity_at=datetime.utcnow()
            )
            await self.users_collection.insert_one(user_analytics.dict())
    
    async def _increment_document_usage(
        self,
        doc_name: str,
        relevance_score: float
    ):
        """Increment document usage metrics"""
        existing = await self.documents_collection.find_one({"title": doc_name})
        
        if existing:
            total_citations = existing["total_citations"]
            new_total = total_citations + 1
            new_avg_score = (
                (existing["avg_relevance_score"] * total_citations + relevance_score) / new_total
            )
            
            await self.documents_collection.update_one(
                {"title": doc_name},
                {
                    "$inc": {
                        "total_queries": 1,
                        "total_citations": 1
                    },
                    "$set": {
                        "avg_relevance_score": round(new_avg_score, 3),
                        "last_used_at": datetime.utcnow()
                    }
                }
            )
        else:
            # Create new document analytics
            # Use doc_name as doc_id if it's a hash-like string, otherwise generate a simple ID
            doc_id = doc_name if len(doc_name) > 10 else f"doc_{doc_name}"
            
            doc_analytics = DocumentAnalytics(
                doc_id=doc_id,
                title=doc_name,
                source_type="unknown",  # Will be updated when we have metadata
                total_queries=1,
                total_citations=1,
                avg_relevance_score=relevance_score,
                added_at=datetime.utcnow(),
                last_used_at=datetime.utcnow()
            )
            await self.documents_collection.insert_one(doc_analytics.dict())
    
    async def get_user_stats(self, user_id: str) -> Optional[dict]:
        """Get analytics for a specific user"""
        return await self.users_collection.find_one({"user_id": user_id})
    
    async def get_document_stats(self, doc_id: str) -> Optional[dict]:
        """Get analytics for a specific document"""
        return await self.documents_collection.find_one({"doc_id": doc_id})
    
    async def get_recent_queries(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[dict]:
        """Get recent queries, optionally filtered by user"""
        query = {"user_id": user_id} if user_id else {}
        cursor = self.queries_collection.find(query).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
