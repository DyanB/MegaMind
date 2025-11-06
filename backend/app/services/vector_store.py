from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Optional
from openai import OpenAI
from app.config import Settings


class VectorStore:
    def __init__(self, settings: Settings, namespace: Optional[str] = None):
        self.settings = settings
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index_name = settings.pinecone_index_name
        # Use provided namespace or fall back to default
        self.namespace = namespace or settings.pinecone_namespace
        
        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
        # Initialize rating service for quality scoring
        from app.services.mongo_rating_service import MongoRatingService
        self.rating_service = MongoRatingService()
        
        # Get or create index
        self._ensure_index_exists()
        self.index = self.pc.Index(self.index_name)
    
    def _ensure_index_exists(self):
        """Create index if it doesn't exist"""
        try:
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                self.pc.create_index(
                    name=self.index_name,
                    dimension=1536,  # text-embedding-3-small dimension
                    metric='cosine',
                    spec=ServerlessSpec(cloud='aws', region='us-east-1')
                )
        except Exception as e:
            print(f"Index check/creation warning: {e}")
            # Index might already exist, continue anyway
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        response = self.openai_client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=text
        )
        return response.data[0].embedding
    
    def embed_batch(self, texts: List[str], batch_size: int = 25) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with batching to avoid rate limits.
        Processes in smaller batches to stay within token limits.
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self.openai_client.embeddings.create(
                    model=self.settings.openai_embedding_model,
                    input=batch
                )
                all_embeddings.extend([item.embedding for item in response.data])
            except Exception as e:
                print(f"Error embedding batch {i}-{i+len(batch)}: {e}")
                # If batch fails, try smaller batches
                if batch_size > 1:
                    print(f"Retrying with smaller batch size: {batch_size // 2}")
                    smaller_embeddings = self.embed_batch(batch, batch_size=batch_size // 2)
                    all_embeddings.extend(smaller_embeddings)
                else:
                    raise
        
        return all_embeddings
    
    def upsert_chunks(self, chunks: List[dict]) -> int:
        """
        Upsert document chunks to Pinecone
        chunks: [{id, text, metadata}]
        """
        # Extract texts for batch embedding
        texts = [chunk['text'] for chunk in chunks]
        embeddings = self.embed_batch(texts)
        
        # Prepare vectors for upsert
        vectors = []
        for chunk, embedding in zip(chunks, embeddings):
            # Filter out None values from metadata (Pinecone doesn't accept null)
            clean_metadata = {
                k: v for k, v in chunk['metadata'].items() 
                if v is not None
            }
            clean_metadata['text'] = chunk['text']  # Store text in metadata for retrieval
            
            vectors.append({
                'id': chunk['id'],
                'values': embedding,
                'metadata': clean_metadata
            })
        
        # Upsert in batches of 100
        batch_size = 100
        total_upserted = 0
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace=self.namespace)
            total_upserted += len(batch)
        
        return total_upserted
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        doc_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search for similar chunks with document quality scoring applied
        Returns: List of {id, score, metadata}
        """
        query_embedding = self.embed_text(query)
        
        # Build filter if doc_ids provided
        filter_dict = None
        if doc_filter:
            filter_dict = {'doc_id': {'$in': doc_filter}}
        
        # Retrieve more results than needed to account for re-ranking
        retrieval_k = top_k * 2
        
        results = self.index.query(
            vector=query_embedding,
            top_k=retrieval_k,
            namespace=self.namespace,
            include_metadata=True,
            filter=filter_dict
        )
        
        # Apply document quality factors to scores
        adjusted_results = []
        for match in results.matches:
            doc_name = match.metadata.get('source', 'Unknown')
            quality_factor = await self.rating_service.get_document_quality_factor(doc_name)
            
            adjusted_results.append({
                'id': match.id,
                'score': match.score * quality_factor,  # Apply quality boost/penalty
                'original_score': match.score,  # Keep original for debugging
                'quality_factor': quality_factor,
                'metadata': match.metadata
            })
        
        # Re-sort by adjusted scores
        adjusted_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Return top_k after re-ranking
        return adjusted_results[:top_k]
    
    async def multi_query_search(
        self,
        queries: List[str],
        top_k: int = 10,
        doc_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Perform multi-query retrieval and deduplicate results
        """
        seen_ids = set()
        all_results = []
        
        for query in queries:
            results = await self.search(query, top_k=top_k, doc_filter=doc_filter)
            for result in results:
                if result['id'] not in seen_ids:
                    seen_ids.add(result['id'])
                    all_results.append(result)
        
        # Sort by score descending
        all_results.sort(key=lambda x: x['score'], reverse=True)
        return all_results[:top_k]
    
    def delete_by_doc_id(self, doc_id: str):
        """Delete all chunks for a document"""
        self.index.delete(
            filter={'doc_id': doc_id},
            namespace=self.namespace
        )
    
    def url_exists_in_kb(self, url: str) -> tuple[bool, Optional[str]]:
        """
        Check if a URL already exists in the knowledge base.
        
        Args:
            url: Source URL to check
            
        Returns:
            Tuple of (exists: bool, doc_id: Optional[str])
        """
        try:
            # Query with filter on source_url
            results = self.index.query(
                vector=[0] * 1536,  # Dummy vector (not used with filter)
                top_k=1,
                namespace=self.namespace,
                include_metadata=True,
                filter={'source_url': url}
            )
            
            if results.matches:
                doc_id = results.matches[0].metadata.get('doc_id')
                return (True, doc_id)
            
            return (False, None)
            
        except Exception as e:
            print(f"Error checking URL existence: {e}")
            return (False, None)
    
    def list_all_documents(self) -> List[Dict]:
        """
        List all unique documents in the knowledge base.
        Returns deduplicated list of documents with their metadata.
        """
        try:
            # Fetch all vectors with metadata (Pinecone limits to 10k per query)
            # Use a dummy query to get all docs
            results = self.index.query(
                vector=[0] * 1536,
                top_k=10000,
                namespace=self.namespace,
                include_metadata=True
            )
            
            # Group by doc_id to get unique documents
            docs_dict = {}
            for match in results.matches:
                metadata = match.metadata
                doc_id = metadata.get('doc_id')
                
                if doc_id and doc_id not in docs_dict:
                    docs_dict[doc_id] = {
                        'doc_id': doc_id,
                        'title': metadata.get('source') or metadata.get('filename', 'Unknown'),
                        'source_type': metadata.get('source_type', 'upload'),
                        'source_url': metadata.get('source_url'),
                        'storage_type': metadata.get('storage_type', 'local'),
                        'added_at': metadata.get('added_at'),
                        'chunk_count': 0
                    }
                
                if doc_id in docs_dict:
                    docs_dict[doc_id]['chunk_count'] += 1
            
            # Sort by added_at (newest first)
            docs_list = list(docs_dict.values())
            docs_list.sort(
                key=lambda x: x.get('added_at') or '', 
                reverse=True
            )
            
            return docs_list
            
        except Exception as e:
            print(f"Error listing documents: {e}")
            return []
