import requests
from typing import List, Dict
from .base import SearchProvider


class WikipediaSearch(SearchProvider):
    """Wikipedia search provider"""
    
    def __init__(self):
        self.base_url = "https://en.wikipedia.org/w/api.php"
        self.headers = {
            "User-Agent": "WandAI/1.0 (Educational Project)"
        }
    
    def is_available(self) -> bool:
        """Wikipedia is always available (no API key required)"""
        return True
    
    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """
        Search Wikipedia using the query API
        
        Args:
            query: Search term
            max_results: Maximum number of results to return
            
        Returns:
            List of Wikipedia article summaries
        """
        try:
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "srprop": "snippet"
            }
            
            response = requests.get(
                self.base_url, 
                params=params, 
                headers=self.headers, 
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("query", {}).get("search", []):
                title = item.get("title")
                snippet = item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
                article_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                
                results.append({
                    "title": title,
                    "summary": snippet,
                    "url": article_url,
                    "source": "Wikipedia"
                })
            
            return results
            
        except Exception as e:
            print(f"Wikipedia search failed for '{query}': {e}")
            return []
