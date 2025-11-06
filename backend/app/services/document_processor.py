import hashlib
import fitz  # PyMuPDF
import docx
from typing import List, Tuple, Optional, Dict
from pathlib import Path
from datetime import datetime
import tiktoken


class DocumentChunk:
    def __init__(self, text: str, page: int = None, metadata: dict = None):
        self.text = text
        self.page = page
        self.metadata = metadata or {}


class DocumentProcessor:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def parse_pdf(self, file_path: Path) -> List[Tuple[str, int]]:
        """Parse PDF and return list of (text, page_num)"""
        doc = fitz.open(file_path)
        pages = []
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            if text.strip():
                pages.append((text, page_num))
        doc.close()
        return pages
    
    def parse_docx(self, file_path: Path) -> List[Tuple[str, int]]:
        """Parse DOCX and return list of (text, page_num)"""
        doc = docx.Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        return [(text, 1)]  # DOCX doesn't have clear page breaks
    
    def parse_txt(self, file_path: Path) -> List[Tuple[str, int]]:
        """Parse TXT file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        return [(text, 1)]
    
    def parse_document(self, file_path: Path) -> List[Tuple[str, int]]:
        """Route to appropriate parser based on extension"""
        suffix = file_path.suffix.lower()
        if suffix == '.pdf':
            return self.parse_pdf(file_path)
        elif suffix in ['.docx', '.doc']:
            return self.parse_docx(file_path)
        elif suffix == '.txt':
            return self.parse_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
    
    def chunk_text(self, text: str, page: int = None) -> List[DocumentChunk]:
        """Split text into overlapping chunks based on token count"""
        # Encode with allowed_special to handle special tokens in text
        tokens = self.tokenizer.encode(text, allowed_special="all")
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            chunks.append(DocumentChunk(
                text=chunk_text,
                page=page,
                metadata={'token_count': len(chunk_tokens)}
            ))
            
            start += self.chunk_size - self.chunk_overlap
        
        return chunks
    
    def process_document(
        self, 
        file_path: Path, 
        doc_id: str,
        metadata_overrides: Optional[Dict[str, any]] = None
    ) -> List[dict]:
        """
        Parse document, chunk it, and return list of chunks with metadata
        
        Args:
            file_path: Path to document file
            doc_id: Unique document identifier
            metadata_overrides: Additional metadata to merge (e.g., source_type, source_url)
        """
        pages = self.parse_document(file_path)
        
        # Create base metadata for this document
        base_metadata = self._create_metadata(file_path, doc_id, metadata_overrides)
        
        all_chunks = []
        chunk_idx = 0
        
        for text, page_num in pages:
            chunks = self.chunk_text(text, page=page_num)
            for chunk in chunks:
                chunk_id = f"{doc_id}:chunk_{chunk_idx}"
                all_chunks.append({
                    'id': chunk_id,
                    'text': chunk.text,
                    'metadata': {
                        **base_metadata,
                        'page': chunk.page,
                        'chunk_index': chunk_idx,
                        'token_count': chunk.metadata.get('token_count', 0)
                    }
                })
                chunk_idx += 1
        
        return all_chunks
    
    def _create_metadata(
        self, 
        file_path: Path, 
        doc_id: str,
        metadata_overrides: Optional[Dict[str, any]] = None
    ) -> dict:
        """
        Create standardized metadata for document chunks.
        Supports S3-compatible structure with backwards compatibility.
        
        Args:
            file_path: Path to document file
            doc_id: Unique document identifier
            metadata_overrides: Dict with optional: source_type, source_url, storage_type, etc.
        """
        metadata_overrides = metadata_overrides or {}
        
        # Base metadata (always present)
        metadata = {
            'doc_id': doc_id,
            'source': metadata_overrides.get('source', file_path.name),
            'filename': file_path.name,  # Keep for backwards compatibility
            'added_at': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Source tracking
        metadata['source_type'] = metadata_overrides.get('source_type', 'upload')  # 'upload' | 'web' | 'enrichment'
        metadata['source_url'] = metadata_overrides.get('source_url')  # None for uploads, URL for web/enrichment
        
        # Storage location (S3-ready)
        metadata['storage_type'] = metadata_overrides.get('storage_type', 'local')  # 'local' | 's3'
        metadata['storage_path'] = metadata_overrides.get('storage_path', str(file_path))
        metadata['storage_bucket'] = metadata_overrides.get('storage_bucket')  # For S3
        metadata['storage_key'] = metadata_overrides.get('storage_key')  # For S3
        
        return metadata
    
    def process_text(
        self,
        text: str,
        doc_id: str,
        metadata_overrides: Optional[Dict[str, any]] = None
    ) -> List[dict]:
        """
        Process raw text (e.g., from web scraping) without a file.
        
        Args:
            text: Text content to chunk
            doc_id: Unique document identifier
            metadata_overrides: Additional metadata (source_type, source_url, etc.)
        """
        metadata_overrides = metadata_overrides or {}
        
        # Create base metadata
        base_metadata = {
            'doc_id': doc_id,
            'source': metadata_overrides.get('source', 'web_content'),
            'source_type': metadata_overrides.get('source_type', 'web'),
            'source_url': metadata_overrides.get('source_url'),
            'storage_type': 'none',  # No file storage for web content
            'storage_path': None,
            'storage_bucket': None,
            'storage_key': None,
            'added_at': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Chunk the text
        chunks = self.chunk_text(text, page=None)
        
        all_chunks = []
        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}:chunk_{chunk_idx}"
            all_chunks.append({
                'id': chunk_id,
                'text': chunk.text,
                'metadata': {
                    **base_metadata,
                    'chunk_index': chunk_idx,
                    'token_count': chunk.metadata.get('token_count', 0)
                }
            })
        
        return all_chunks
    
    @staticmethod
    def generate_doc_id(content: bytes) -> str:
        """Generate deterministic doc ID from content"""
        return hashlib.sha1(content).hexdigest()[:16]
