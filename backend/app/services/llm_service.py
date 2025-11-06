from openai import OpenAI
import json
from typing import List, Dict, Tuple
from app.config import Settings
from app.models import CompletenessCheck


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_llm_model
    
    def generate_query_variations(self, question: str) -> List[str]:
        """Generate 1 alternative phrasing of the question for multi-query retrieval"""
        prompt = f"""Given this question, generate 1 alternative phrasing that preserves the core intent but uses different words.

Original question: {question}

Return ONLY a JSON array with one string, like: ["variation 1"]"""
        
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,  # Reduced for faster generation
            max_tokens=100  # Reduced token limit
        )
        
        try:
            variations = json.loads(response.choices[0].message.content)
            return [question] + variations[:1]  # Original + 1 variation
        except:
            return [question]  # Fallback to original only
    
    def generate_answer(
        self,
        question: str,
        contexts: List[Dict]
    ) -> Tuple[str, List[Dict]]:
        """
        Generate answer from retrieved contexts with citations
        Returns: (answer_text, citations)
        """
        # Build context string with citation markers
        context_parts = []
        citations = []
        
        for idx, ctx in enumerate(contexts[:10], start=1):  # Use top 10
            metadata = ctx['metadata']
            page = metadata.get('page', '?')
            # Use 'source' field (new metadata structure) or fallback to 'filename' (old structure)
            title = metadata.get('source') or metadata.get('filename', 'Unknown')
            text = metadata.get('text', '')
            
            citation_marker = f"[{idx}]"
            context_parts.append(f"{citation_marker} (Source: {title}, p.{page})\n{text}\n")
            
            citations.append({
                'doc_id': metadata.get('doc_id'),
                'title': title,
                'page': page if isinstance(page, int) else None,
                'chunk_text': text[:200] + '...' if len(text) > 200 else text,
                'score': ctx['score'],
                'metadata': {
                    'source_url': metadata.get('source_url'),
                    'storage_type': metadata.get('storage_type'),
                    'source_type': metadata.get('source_type')
                }
            })
        
        context_text = "\n".join(context_parts)
        
        prompt = f"""You are a helpful assistant that answers questions based strictly on the provided documents.

**Instructions:**
1. Answer the question using ONLY information from the context below
2. Include citation markers [1], [2], etc. in your answer
3. If the context doesn't contain enough information, acknowledge what's missing
4. Be concise but complete

**Context:**
{context_text}

**Question:** {question}

**Answer:**"""
        
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,  # More deterministic for faster response
            max_tokens=600  # Reduced for faster generation
        )
        
        answer = response.choices[0].message.content
        return answer, citations
    
    def check_completeness(
        self,
        question: str,
        answer: str,
        contexts: List[Dict]
    ) -> CompletenessCheck:
        """
        Perform self-check on answer completeness
        """
        avg_score = sum(c['score'] for c in contexts[:5]) / min(5, len(contexts)) if contexts else 0.0
        
        prompt = f"""You are an AI quality checker. Evaluate this Q&A pair for completeness and confidence.

**Question:** {question}

**Answer:** {answer}

**Task:** Return a JSON object with:
{{
  "confidence": 0.0-1.0,  // How confident is the answer?
  "completeness": 0.0-1.0,  // How complete is the answer?
  "is_complete": true/false,  // Is it satisfactory? (>= 0.85 completeness = complete)
  "missing_information": "what's missing or unclear (null if complete)",
  "suggested_documents": ["list of document types that would help"],
  "suggested_actions": ["actions to improve the knowledge base"],
  "search_queries": ["2-3 short search terms (2-4 words each, empty if complete)"]
}}

For search_queries: Generate SHORT, SIMPLE search terms optimized for web/knowledge base search. Use proper nouns and technical terms, but keep them concise (2-4 words max). Focus on KEY CONCEPTS that need more information. Examples: "CUDA programming", "neural networks basics", "PyTorch tensors", "A15 Bionic chip" - NOT "detailed explanation of CUDA programming concepts".

Be strict but fair. Mark is_complete=true ONLY if completeness >= 0.85 (85% threshold). The answer must fully address the question."""
        
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,  # Very deterministic for consistency
            max_tokens=300  # Reduced for speed
        )
        
        try:
            check_data = json.loads(response.choices[0].message.content)
            
            # Blend LLM confidence with retrieval scores
            llm_confidence = check_data.get('confidence', 0.5)
            blended_confidence = 0.6 * llm_confidence + 0.4 * avg_score
            
            # Apply 85% threshold for completeness
            completeness_score = check_data.get('completeness', 0.5)
            is_complete = completeness_score >= 0.85
            
            return CompletenessCheck(
                confidence=round(blended_confidence, 2),
                completeness=round(completeness_score, 2),
                is_complete=is_complete,
                missing_information=check_data.get('missing_information'),
                suggested_documents=check_data.get('suggested_documents', []),
                suggested_actions=check_data.get('suggested_actions', []),
                search_queries=check_data.get('search_queries', [])
            )
        except Exception as e:
            # Fallback if JSON parsing fails
            return CompletenessCheck(
                confidence=round(avg_score, 2),
                completeness=0.5,
                is_complete=False,
                missing_information=f"Error in completeness check: {str(e)}",
                suggested_documents=[],
                suggested_actions=["Retry completeness check"],
                search_queries=[]
            )
