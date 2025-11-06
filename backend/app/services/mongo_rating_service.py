"""
MongoDB-based Rating Service
Replaces JSON file storage with MongoDB
"""
from typing import Dict, List, Optional
from datetime import datetime
import uuid
from app.database import MongoDB, COLLECTIONS
from app.models.rating import RatingDocument, DocumentScoreDocument


class MongoRatingService:
    """Service to manage answer ratings and document quality scoring with MongoDB"""
    
    def __init__(self):
        self.MIN_RELEVANCE_THRESHOLD = 0.4  # Only score if docs meet this threshold
    
    async def save_rating(
        self,
        question: str,
        answer: str,
        rating: str,  # "up" or "down"
        documents_used: List[str],
        retrieved_docs: List[Dict],  # List of {score, metadata}
        completeness: str,
        user_id: Optional[str] = None,  # NEW: User who rated
        feedback_text: Optional[str] = None
    ) -> Dict:
        """
        Save a rating and update document quality scores if applicable
        
        Returns: {rating_id, should_update_docs, reason}
        """
        # Create rating record
        rating_id = str(uuid.uuid4())
        rating_record = {
            "_id": rating_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "question": question,
            "answer": answer,
            "rating": rating,
            "feedback_text": feedback_text,
            "documents_used": documents_used,
            "completeness": completeness,
            "max_relevance_score": max((doc.get('score', 0) for doc in retrieved_docs), default=0)
        }
        
        # Save rating to MongoDB
        ratings_collection = MongoDB.get_collection(COLLECTIONS["ratings"])
        await ratings_collection.insert_one(rating_record)
        
        # Determine if we should update document scores
        should_update, reason = self._should_update_doc_scores(
            retrieved_docs, 
            completeness
        )
        
        if should_update:
            await self._update_document_scores(documents_used, rating, user_id)
            return {
                "rating_id": rating_id,
                "should_update_docs": True,
                "reason": "Document scores updated"
            }
        else:
            return {
                "rating_id": rating_id,
                "should_update_docs": False,
                "reason": reason
            }
    
    def _should_update_doc_scores(
        self,
        retrieved_docs: List[Dict],
        completeness: str
    ) -> tuple[bool, str]:
        """
        Determine if document scores should be updated
        
        Returns: (should_update: bool, reason: str)
        """
        # Check 1: Were the retrieved documents relevant enough?
        max_score = max((doc.get('score', 0) for doc in retrieved_docs), default=0)
        
        if max_score < self.MIN_RELEVANCE_THRESHOLD:
            return False, f"Document relevance too low ({max_score:.2f} < {self.MIN_RELEVANCE_THRESHOLD})"
        
        # Check 2: Was the answer complete enough?
        if completeness != "complete":
            return False, f"Answer not complete (status: {completeness})"
        
        return True, "Conditions met for document scoring"
    
    async def _update_document_scores(
        self, 
        doc_ids: List[str], 
        rating: str,
        user_id: Optional[str] = None
    ):
        """Update quality scores for documents that were used"""
        doc_scores_collection = MongoDB.get_collection(COLLECTIONS["document_scores"])
        
        for doc_id in doc_ids:
            # Get current scores
            doc_score = await doc_scores_collection.find_one({"_id": doc_id})
            
            if doc_score:
                # Update existing
                upvotes = doc_score.get("upvotes", 0)
                downvotes = doc_score.get("downvotes", 0)
                
                if rating == "up":
                    upvotes += 1
                else:
                    downvotes += 1
                
                total_votes = upvotes + downvotes
                score = (upvotes - downvotes) / total_votes if total_votes > 0 else 0
                
                await doc_scores_collection.update_one(
                    {"_id": doc_id},
                    {
                        "$set": {
                            "upvotes": upvotes,
                            "downvotes": downvotes,
                            "total_votes": total_votes,
                            "score": score,
                            "last_updated": datetime.utcnow()
                        }
                    }
                )
            else:
                # Create new
                upvotes = 1 if rating == "up" else 0
                downvotes = 1 if rating == "down" else 0
                total_votes = 1
                score = 1.0 if rating == "up" else -1.0
                
                await doc_scores_collection.insert_one({
                    "_id": doc_id,
                    "user_id": user_id,
                    "title": doc_id,  # Will be updated when we have metadata
                    "upvotes": upvotes,
                    "downvotes": downvotes,
                    "total_votes": total_votes,
                    "score": score,
                    "last_updated": datetime.utcnow()
                })
    
    async def get_document_scores(self) -> Dict[str, Dict]:
        """Get all document quality scores"""
        doc_scores_collection = MongoDB.get_collection(COLLECTIONS["document_scores"])
        cursor = doc_scores_collection.find({})
        
        scores = {}
        async for doc in cursor:
            doc_id = doc["_id"]
            scores[doc_id] = {
                "upvotes": doc.get("upvotes", 0),
                "downvotes": doc.get("downvotes", 0),
                "total_votes": doc.get("total_votes", 0),
                "score": doc.get("score", 0.0),
                "last_updated": doc.get("last_updated")
            }
        
        return scores
    
    async def get_ratings_by_user(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get ratings by a specific user"""
        ratings_collection = MongoDB.get_collection(COLLECTIONS["ratings"])
        cursor = ratings_collection.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(limit)
        
        ratings = []
        async for rating in cursor:
            ratings.append(rating)
        
        return ratings
    
    async def get_all_ratings(self, limit: int = 100) -> List[Dict]:
        """Get all ratings (for admin/analytics)"""
        ratings_collection = MongoDB.get_collection(COLLECTIONS["ratings"])
        cursor = ratings_collection.find({}).sort("timestamp", -1).limit(limit)
        
        ratings = []
        async for rating in cursor:
            ratings.append(rating)
        
        return ratings
    
    async def get_document_quality_factor(self, doc_id: str) -> float:
        """
        Get quality multiplier for a document (1.0 = neutral)
        
        Returns:
            1.0 + (score / 10) where score is normalized between -1 and 1
            Range: 0.9 (bad docs) to 1.1 (good docs)
        """
        doc_scores_collection = MongoDB.get_collection(COLLECTIONS["document_scores"])
        doc_score = await doc_scores_collection.find_one({"_id": doc_id})
        
        if not doc_score or doc_score.get("total_votes", 0) < 3:
            return 1.0  # Neutral if no ratings or too few votes
        
        # Get normalized score (-1 to 1)
        score = doc_score.get("score", 0.0)
        
        # Convert to quality multiplier (0.9 to 1.1)
        quality_factor = 1.0 + (score / 10)
        
        return max(0.9, min(1.1, quality_factor))  # Clamp to range
