from abc import ABC, abstractmethod
from typing import List, Dict


class SearchProvider(ABC):
    """Base class for external search providers"""
    
    @abstractmethod
    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """
        Search for content
        
        Args:
            query: Search term
            max_results: Maximum number of results to return
            
        Returns:
            List of dicts with keys: title, summary, url, source
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is configured and available"""
        pass
