from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import time

from app.models import AskRequest, AskResponse, Citation, EnrichmentData, ExternalSource, RatingRequest, RatingResponse
from app.models.auth import UserResponse
from app.config import get_settings, Settings
from app.services.vector_store import VectorStore
from app.services.llm_service import LLMService
from app.services.enrichment_service import EnrichmentService
from app.services.mongo_rating_service import MongoRatingService
from app.services.analytics_service import AnalyticsService
from app.routes.auth import get_current_user_optional

router = APIRouter(prefix="/search", tags=["search"])


def get_vector_store(settings: Settings = Depends(get_settings), current_user: Optional[UserResponse] = Depends(get_current_user_optional)):
    # Use user-specific namespace if authenticated, otherwise use default
    if current_user:
        namespace = settings.get_user_namespace(current_user.id)
    else:
        namespace = settings.pinecone_namespace
    
    # Create vector store with user-specific namespace
    return VectorStore(settings, namespace=namespace)


def get_llm_service(settings: Settings = Depends(get_settings)):
    return LLMService(settings)


def get_enrichment_service():
    return EnrichmentService()


def get_rating_service():
    return MongoRatingService()


def get_analytics_service():
    return AnalyticsService()


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    settings: Settings = Depends(get_settings),
    vector_store: VectorStore = Depends(get_vector_store),
    llm_service: LLMService = Depends(get_llm_service),
    enrichment_service: EnrichmentService = Depends(get_enrichment_service),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """
    Ask a question and get an AI-generated answer with completeness check and auto-enrichment
    """
    start_time = time.time()
    
    try:
        # Step 1: Generate query variations for multi-query retrieval
        query_variations = llm_service.generate_query_variations(request.question)
        
        # Step 2: Retrieve relevant chunks
        contexts = await vector_store.multi_query_search(
            queries=query_variations,
            top_k=settings.top_k,
            doc_filter=request.doc_filter
        )
        
        # Extract unique document names for rating purposes
        documents_used = list(set(
            ctx.get('metadata', {}).get('source', 'Unknown')
            for ctx in contexts
        )) if contexts else []
        
        # Calculate average retrieval score
        avg_score = sum(ctx.get('score', 0) for ctx in contexts) / len(contexts) if contexts else 0.0
        
        # Step 3: Generate answer with citations
        # If no contexts, still generate answer but indicate lack of knowledge
        if not contexts:
            answer = "I don't have any documents in my knowledge base to answer this question. However, I can search external sources for you!"
            citations = []
        else:
            answer, citations = llm_service.generate_answer(request.question, contexts)
        
        # Step 4: Self-check completeness
        completeness_check = llm_service.check_completeness(
            request.question,
            answer,
            contexts if contexts else []
        )
        
        # Step 5: Auto-enrichment - trigger if KB is empty OR answer is incomplete
        enrichment_data = None
        external_sources_found = 0
        if request.auto_enrich and not completeness_check.is_complete:
            if completeness_check.search_queries and len(completeness_check.search_queries) > 0:
                enrichment_result = enrichment_service.auto_enrich(
                    completeness_check.search_queries
                )
                external_sources_found = len(enrichment_result.get('sources_found', []))
                enrichment_data = EnrichmentData(
                    enrichment_performed=enrichment_result['enrichment_performed'],
                    sources_found=[ExternalSource(**s) for s in enrichment_result.get('sources_found', [])],
                    search_terms=enrichment_result.get('search_terms', []),
                    message=enrichment_result.get('message', '')
                )
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Step 6: Log analytics
        await analytics_service.log_query(
            question=request.question,
            answer=answer,
            user_id=current_user.id if current_user else None,
            session_id=None,  # Can add session tracking later
            latency_ms=round(latency_ms, 2),
            confidence=completeness_check.confidence,
            completeness=completeness_check.completeness,
            is_complete=completeness_check.is_complete,
            contexts_retrieved=len(contexts),
            documents_used=documents_used,
            avg_retrieval_score=round(avg_score, 3),
            enrichment_triggered=enrichment_data is not None,
            external_sources_found=external_sources_found
        )
        
        return AskResponse(
            question=request.question,
            answer=answer,
            citations=[Citation(**c) for c in citations],
            completeness_check=completeness_check,
            enrichment_data=enrichment_data,
            latency_ms=round(latency_ms, 2),
            retrieved_docs=contexts,  # Include for rating
            documents_used=documents_used  # Include for rating
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/feedback", response_model=RatingResponse)
async def submit_feedback(
    request: RatingRequest,
    rating_service: MongoRatingService = Depends(get_rating_service),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """
    Submit user rating for an answer to improve document quality scoring
    """
    try:
        result = await rating_service.save_rating(
            question=request.question,
            answer=request.answer,
            rating=request.rating,
            documents_used=request.documents_used,
            retrieved_docs=request.retrieved_docs,
            completeness=request.completeness,
            user_id=current_user.id if current_user else None,
            feedback_text=request.feedback_text
        )
        
        message = "Thank you for your feedback!"
        if result["should_update_docs"]:
            message += " Your rating helps improve document quality."
        else:
            message += f" ({result['reason']})"
        
        return RatingResponse(
            rating_id=result["rating_id"],
            should_update_docs=result["should_update_docs"],
            reason=result["reason"],
            message=message
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {str(e)}")


@router.get("/stats")
async def get_rating_stats(
    rating_service: MongoRatingService = Depends(get_rating_service)
):
    """
    Get statistics about collected ratings and document quality scores
    """
    try:
        doc_scores = await rating_service.get_document_scores()
        all_ratings = await rating_service.get_all_ratings(limit=100)
        
        return {
            "total_ratings": len(all_ratings),
            "document_scores": doc_scores
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
