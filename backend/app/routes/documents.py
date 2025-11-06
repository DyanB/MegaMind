from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
from pathlib import Path
from datetime import datetime, timedelta
import shutil
import traceback
import logging

from app.models import (
    DocumentUploadResponse, 
    IngestRequest, 
    IngestResponse,
    IngestUrlRequest,
    IngestUrlResponse,
    CheckUrlResponse
)
from app.models.auth import UserResponse
from app.config import get_settings, Settings
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import VectorStore
from app.services.web_scraper import (
    scrape_webpage,
    WebScraperError,
    URLNotFoundError,
    NetworkError,
    ContentExtractionError
)
from app.services.s3_service import S3Service
from app.routes.auth import get_current_user_optional

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)


def get_s3_service():
    """Get S3 service instance (returns None if S3 not configured)"""
    try:
        return S3Service()
    except Exception as e:
        logger.warning(f"S3 service not available: {e}")
        return None


def get_document_processor(settings: Settings = Depends(get_settings)):
    return DocumentProcessor(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap
    )


def get_vector_store(
    settings: Settings = Depends(get_settings),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Get VectorStore with user-specific namespace if authenticated"""
    namespace = settings.get_user_namespace(current_user.id) if current_user else None
    return VectorStore(settings, namespace=namespace)


@router.post("/upload", response_model=List[DocumentUploadResponse])
async def upload_documents(
    files: List[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Upload one or more documents (optional authentication). Supports PDF, TXT, DOCX."""
    # Allowed file extensions and MIME types
    ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.docx', '.doc'}
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'text/plain',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword'
    }
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit
    
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    responses = []
    processor = DocumentProcessor()
    
    for file in files:
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{file_ext}' not supported. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Validate MIME type
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
            logger.warning(f"Suspicious MIME type: {file.content_type} for {file.filename}")
            # Allow but log - some browsers send incorrect MIME types
        
        # Read file content
        content = await file.read()
        
        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {len(content) / 1024 / 1024:.1f}MB. Maximum size: 50MB"
            )
        
        # Validate file is not empty
        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' is empty"
            )
        
        # Generate doc ID
        doc_id = processor.generate_doc_id(content)
        
        # Save file
        file_path = upload_dir / f"{doc_id}_{file.filename}"
        with open(file_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"✓ Uploaded file: {file.filename} ({len(content) / 1024:.1f}KB)")
        
        responses.append(DocumentUploadResponse(
            doc_id=doc_id,
            filename=file.filename,
            size_bytes=len(content),
            uploaded_at=datetime.utcnow(),
            message=f"Uploaded successfully. Use doc_id '{doc_id}' to ingest."
        ))
    
    return responses


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    request: IngestRequest,
    settings: Settings = Depends(get_settings),
    processor: DocumentProcessor = Depends(get_document_processor),
    vector_store: VectorStore = Depends(get_vector_store),
    s3_service: Optional[S3Service] = Depends(get_s3_service),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """Parse, chunk, embed, and upsert a document to Pinecone. Uploads PDFs to S3."""
    upload_dir = Path(settings.upload_dir)
    
    # Find the file with this doc_id
    matching_files = list(upload_dir.glob(f"{request.doc_id}_*"))
    
    if not matching_files:
        raise HTTPException(status_code=404, detail=f"Document {request.doc_id} not found")
    
    file_path = matching_files[0]
    
    try:
        # Check if file is PDF and upload to S3
        s3_metadata = {}
        if file_path.suffix.lower() == '.pdf' and s3_service:
            try:
                # Read PDF content
                with open(file_path, 'rb') as f:
                    pdf_content = f.read()
                
                # Generate S3 key with user namespace
                import hashlib
                from datetime import datetime as dt
                pdf_hash = hashlib.md5(pdf_content).hexdigest()[:12]
                
                # Include user ID in S3 path for isolation
                user_prefix = f"users/{current_user.id}" if current_user else "users/anonymous"
                s3_key = f"{user_prefix}/pdfs/{pdf_hash}_{file_path.name}"
                
                # Upload to S3
                s3_result = s3_service.upload_pdf(
                    file_content=pdf_content,
                    s3_key=s3_key,
                    metadata={
                        'doc_id': request.doc_id,
                        'filename': file_path.name,
                        'uploaded_by': current_user.id if current_user else 'anonymous',
                        'user_id': current_user.id if current_user else None
                    }
                )
                
                s3_metadata = {
                    'storage_type': 's3',
                    'storage_bucket': s3_result['bucket'],
                    'storage_key': s3_key
                }
                
                logger.info(f"✓ Uploaded PDF to S3: {s3_key}")
                
            except Exception as e:
                logger.warning(f"Failed to upload to S3, keeping local file: {e}")
                s3_metadata = {
                    'storage_type': 'local',
                    'storage_path': str(file_path)
                }
        else:
            # Non-PDF or S3 not available
            s3_metadata = {
                'storage_type': 'local',
                'storage_path': str(file_path)
            }
        
        # Process document into chunks with S3 metadata
        chunks = processor.process_document(file_path, request.doc_id, metadata_overrides=s3_metadata)
        
        # Upsert to Pinecone
        vectors_upserted = vector_store.upsert_chunks(chunks)
        
        # Delete local file AFTER successful processing if stored in S3
        if s3_metadata.get('storage_type') == 's3':
            try:
                file_path.unlink()
                logger.info(f"🗑️ Deleted local file after S3 upload: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete local file: {e}")
        
        return IngestResponse(
            doc_id=request.doc_id,
            chunks_created=len(chunks),
            vectors_upserted=vectors_upserted,
            message=f"Successfully ingested {len(chunks)} chunks"
        )
    
    except Exception as e:
        print(f"Ingestion error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    settings: Settings = Depends(get_settings),
    vector_store: VectorStore = Depends(get_vector_store),
    s3_service: Optional[S3Service] = Depends(get_s3_service)
):
    """Delete document and its vectors from Pinecone, local storage, and S3"""
    upload_dir = Path(settings.upload_dir)
    
    # Get document metadata from Pinecone to find S3 key
    s3_key_to_delete = None
    try:
        # Try to fetch first chunk
        vectors = vector_store.index.fetch(ids=[f"{doc_id}_0"], namespace=vector_store.namespace)
        
        if vectors and vectors.vectors and f"{doc_id}_0" in vectors.vectors:
            metadata = vectors.vectors[f"{doc_id}_0"].metadata
        else:
            # Try to find any chunk from this document
            logger.info(f"First chunk not found, searching for any chunk with doc_id={doc_id}")
            query_response = vector_store.index.query(
                vector=[0.0] * 1536,  # Dummy vector
                filter={'doc_id': doc_id},
                top_k=1,
                namespace=vector_store.namespace,
                include_metadata=True
            )
            if query_response.matches:
                metadata = query_response.matches[0].metadata
                logger.info(f"Found metadata from chunk: {query_response.matches[0].id}")
            else:
                metadata = None
                logger.warning(f"⚠️ No chunks found for doc_id={doc_id}")
        
        if metadata:
            logger.info(f"📋 Document metadata: storage_key={metadata.get('storage_key')}, storage_type={metadata.get('storage_type')}")
            
            # Delete from S3 if stored there
            if metadata.get('storage_key'):
                s3_key_to_delete = metadata['storage_key']
                if s3_service:
                    try:
                        s3_service.delete_file(s3_key_to_delete)
                        logger.info(f"🗑️ Deleted from S3: {s3_key_to_delete}")
                    except Exception as e:
                        logger.error(f"❌ Failed to delete from S3: {e}")
                else:
                    logger.error(f"❌ S3 service not available, file remains in S3: {s3_key_to_delete}")
            else:
                logger.info("ℹ️ No storage_key found, document not in S3")
    except Exception as e:
        logger.error(f"❌ Could not fetch metadata for S3 cleanup: {e}")
        import traceback
        traceback.print_exc()
    
    # Delete local file
    matching_files = list(upload_dir.glob(f"{doc_id}_*"))
    for file in matching_files:
        file.unlink()
        logger.info(f"🗑️ Deleted local file: {file}")
    
    # Delete from Pinecone
    vector_store.delete_by_doc_id(doc_id)
    
    return {"message": f"Document {doc_id} deleted successfully"}


@router.post("/ingest-url", response_model=IngestUrlResponse)
async def ingest_url(
    request: IngestUrlRequest,
    processor: DocumentProcessor = Depends(get_document_processor),
    vector_store: VectorStore = Depends(get_vector_store),
    s3_service: Optional[S3Service] = Depends(get_s3_service),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    """
    Scrape content from URL and ingest into knowledge base.
    Handles both HTML pages and PDFs. Uploads PDFs to S3 if configured.
    """
    try:
        logger.info(f"Ingesting URL: {request.url}")
        
        # Check if URL already exists
        exists, existing_doc_id = vector_store.url_exists_in_kb(request.url)
        if exists:
            logger.info(f"URL already exists with doc_id: {existing_doc_id}")
            return IngestUrlResponse(
                success=True,
                message="URL already exists in knowledge base",
                doc_id=existing_doc_id,
                already_exists=True
            )
        
        # Scrape the webpage (with S3 service for PDF uploads and user_id for isolation)
        scraped_data = scrape_webpage(
            request.url, 
            timeout=30, 
            s3_service=s3_service,
            user_id=current_user.id if current_user else None
        )
        
        # Generate doc_id from URL
        doc_id = processor.generate_doc_id(request.url.encode('utf-8'))
        
        # Use custom title if provided, otherwise use scraped title
        title = request.title or scraped_data['title']
        
        # Build metadata
        metadata_overrides = {
            'source': title,
            'source_type': 'web',
            'source_url': request.url
        }
        
        # If PDF was uploaded to S3, add S3 metadata
        if scraped_data.get('s3_key'):
            metadata_overrides.update({
                'storage_type': 's3',
                'storage_bucket': scraped_data.get('s3_bucket'),
                'storage_key': scraped_data['s3_key']
            })
            logger.info(f"PDF stored in S3: {scraped_data['s3_key']}")
        else:
            metadata_overrides['storage_type'] = 'none'
        
        # Process scraped text into chunks
        chunks = processor.process_text(
            text=scraped_data['text'],
            doc_id=doc_id,
            metadata_overrides=metadata_overrides
        )
        
        # Upsert to Pinecone
        vectors_upserted = vector_store.upsert_chunks(chunks)
        
        logger.info(f"✓ Ingested {len(chunks)} chunks from {request.url}")
        
        return IngestUrlResponse(
            success=True,
            message=f"Successfully ingested {len(chunks)} chunks from URL",
            doc_id=doc_id,
            already_exists=False,
            chunks_created=len(chunks)
        )
        
    except URLNotFoundError as e:
        logger.error(f"URL not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    
    except NetworkError as e:
        logger.error(f"Network error: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    
    except ContentExtractionError as e:
        logger.error(f"Content extraction failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    
    except WebScraperError as e:
        logger.error(f"Web scraping error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to ingest URL: {str(e)}")


@router.get("/{doc_id}/metadata")
async def get_document_metadata(
    doc_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_settings)
):
    """Debug endpoint to check document metadata"""
    try:
        chunk_id = f"{doc_id}_0"
        vectors = vector_store.index.fetch(ids=[chunk_id], namespace=vector_store.namespace)
        
        if vectors and vectors.vectors and chunk_id in vectors.vectors:
            return {"metadata": vectors.vectors[chunk_id].metadata}
        
        # Try query fallback
        query_result = vector_store.index.query(
            vector=[0.0] * 1536,
            filter={"doc_id": doc_id},
            top_k=1,
            include_metadata=True,
            namespace=vector_store.namespace
        )
        
        if query_result.matches:
            return {"metadata": query_result.matches[0].metadata}
        
        return {"error": "Document not found"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/{doc_id}/pdf-url")
async def get_pdf_url(
    doc_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
    s3_service: Optional[S3Service] = Depends(get_s3_service),
    settings: Settings = Depends(get_settings)
):
    """Get presigned URL for viewing PDF stored in S3 or return source URL for web PDFs"""
    try:
        # Try to fetch first chunk
        chunk_id = f"{doc_id}_0"
        logger.info(f"Fetching metadata for chunk: {chunk_id}")
        
        vectors = vector_store.index.fetch(ids=[chunk_id], namespace=vector_store.namespace)
        
        metadata = None
        if vectors and vectors.vectors and chunk_id in vectors.vectors:
            metadata = vectors.vectors[chunk_id].metadata
            logger.info(f"Found metadata via fetch: {metadata}")
        else:
            logger.warning(f"Chunk {chunk_id} not found, searching for any chunk with doc_id={doc_id}")
            
            # Try to find any chunk from this document
            query_result = vector_store.index.query(
                vector=[0.0] * 1536,
                filter={"doc_id": doc_id},
                top_k=1,
                include_metadata=True,
                namespace=vector_store.namespace
            )
            
            if query_result.matches and len(query_result.matches) > 0:
                metadata = query_result.matches[0].metadata
                logger.info(f"Found metadata via query: {metadata}")
            else:
                logger.error(f"No chunks found for doc_id: {doc_id}")
                raise HTTPException(status_code=404, detail=f"Document {doc_id} not found in knowledge base")
        
        # Extract storage info
        storage_type = metadata.get('storage_type')
        storage_key = metadata.get('storage_key')
        source_url = metadata.get('source_url')
        filename = metadata.get('filename') or metadata.get('source', '')
        
        logger.info(f"Document {doc_id}: storage_type={storage_type}, storage_key={storage_key}, source_url={source_url}, filename={filename}")
        
        # Priority 1: S3 storage with key - ALWAYS prefer S3 if available
        if storage_key and s3_service:
            try:
                presigned_url = s3_service.get_presigned_url(storage_key, expiration=3600)
                logger.info(f"✓ Generated presigned URL for S3 key: {storage_key}")
                return {
                    "url": presigned_url,
                    "storage_type": "s3",
                    "expires_in": 3600
                }
            except Exception as e:
                logger.error(f"Failed to generate presigned URL for {storage_key}: {e}")
                # Only fallback to source_url if S3 completely fails
                if source_url:
                    logger.warning(f"S3 failed, falling back to source URL: {source_url}")
                    return {
                        "url": source_url,
                        "storage_type": "web",
                        "expires_in": None
                    }
                raise HTTPException(status_code=500, detail="Failed to access PDF from S3")
        
        # Priority 2: Web source URL (only if NOT in S3)
        if source_url and storage_type != 's3':
            logger.info(f"✓ Returning source URL: {source_url}")
            return {
                "url": source_url,
                "storage_type": "web",
                "expires_in": None
            }
        
        # Priority 3: Check if file exists in S3 by filename pattern
        if s3_service and filename:
            # Try to find the file in S3 by searching for the filename
            try:
                # Check common S3 paths
                import hashlib
                from datetime import datetime as dt
                
                # Try to reconstruct S3 key from filename
                if filename.endswith('.pdf'):
                    # Try recent dates (last 7 days)
                    for days_ago in range(7):
                        date_prefix = (dt.utcnow() - timedelta(days=days_ago)).strftime("%Y%m%d")
                        # Try with doc_id in filename
                        potential_keys = [
                            f"pdfs/{date_prefix}/{doc_id[:12]}_{filename}",
                            f"pdfs/{date_prefix}/{doc_id}_{filename}",
                            f"pdfs/{date_prefix}/{filename}"
                        ]
                        
                        for key in potential_keys:
                            if s3_service.file_exists(key):
                                logger.info(f"✓ Found file in S3: {key}")
                                presigned_url = s3_service.get_presigned_url(key, expiration=3600)
                                return {
                                    "url": presigned_url,
                                    "storage_type": "s3",
                                    "expires_in": 3600
                                }
            except Exception as e:
                logger.warning(f"Failed to search S3 for file: {e}")
        
        # Priority 4: Fallback to source URL if everything else failed
        if source_url:
            logger.warning(f"All S3 attempts failed, falling back to source URL: {source_url}")
            return {
                "url": source_url,
                "storage_type": "web",
                "expires_in": None
            }
        
        # No viewable PDF found
        logger.error(f"Cannot view document: no accessible URL found. metadata={metadata}")
        raise HTTPException(
            status_code=404, 
            detail="PDF not accessible. Document may be stored locally or metadata is incomplete."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate PDF URL for {doc_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-url", response_model=CheckUrlResponse)
async def check_url(
    url: str,
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Check if a URL already exists in the knowledge base"""
    exists, doc_id = vector_store.url_exists_in_kb(url)
    return CheckUrlResponse(exists=exists, doc_id=doc_id)


@router.get("/list")
async def list_documents(
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    List all documents in the knowledge base with their metadata
    Returns unique documents grouped by doc_id
    """
    try:
        docs = vector_store.list_all_documents()
        
        # Debug: Log first document details
        if docs:
            logger.info(f"Sample document from list: {docs[0]}")
        
        return {"documents": docs, "total": len(docs)}
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

