import os
import re
from typing import List, Dict
from exa_py import Exa
from .base import SearchProvider


class ExaSearch(SearchProvider):
    """Exa neural search provider"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("EXA_API_KEY")
        self.client = Exa(api_key=self.api_key) if self.api_key else None
        
        # Debug logging
        if self.api_key:
            print(f"✓ ExaSearch initialized with API key: {self.api_key[:8]}...")
        else:
            print("✗ ExaSearch: No API key found (EXA_API_KEY not set)")
    
    def is_available(self) -> bool:
        """Check if Exa is configured"""
        return self.client is not None
    
    def _clean_text(self, text: str, max_length: int = 300) -> str:
        """Clean and truncate text for display"""
        if not text:
            return "No content available"
        
        # Remove excessive whitespace and newlines
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove HTML tags if any
        text = re.sub(r'<[^>]+>', '', text)
        
        # Truncate at sentence boundary if possible
        if len(text) > max_length:
            # Try to cut at last sentence within limit
            truncated = text[:max_length]
            last_period = truncated.rfind('.')
            last_question = truncated.rfind('?')
            last_exclamation = truncated.rfind('!')
            
            cut_point = max(last_period, last_question, last_exclamation)
            
            if cut_point > max_length * 0.5:  # Only cut at sentence if it's not too short
                text = text[:cut_point + 1]
            else:
                text = truncated + '...'
        
        return text
    
    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """
        Search using Exa neural search
        
        Args:
            query: Search term
            max_results: Maximum number of results to return
            
        Returns:
            List of search results
        """
        if not self.is_available():
            return []
        
        try:
            response = self.client.search_and_contents(
                query,
                type="neural",  # Neural search for semantic understanding
                num_results=max_results,
                text=True  # Get full text content
            )
            
            results = []
            for result in response.results:
                results.append({
                    "title": result.title,
                    "summary": self._clean_text(result.text),
                    "url": result.url,
                    "source": "Exa"
                })
            
            return results
            
        except Exception as e:
            print(f"Exa search failed for '{query}': {e}")
            return []
