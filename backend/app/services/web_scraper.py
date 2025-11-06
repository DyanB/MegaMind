"""
Web scraping service for extracting content from URLs.
Handles both HTML pages and PDF documents.
Uploads PDFs to S3 for permanent storage.
"""
import requests
import trafilatura
import fitz  # PyMuPDF
from typing import Dict, Optional
from io import BytesIO
import logging
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


class WebScraperError(Exception):
    """Base exception for web scraping errors"""
    pass


class URLNotFoundError(WebScraperError):
    """Raised when URL returns 404"""
    pass


class NetworkError(WebScraperError):
    """Raised for network timeouts or connection issues"""
    pass


class ContentExtractionError(WebScraperError):
    """Raised when content extraction fails"""
    pass


def is_pdf_url(url: str, timeout: int = 10) -> bool:
    """
    Check if URL points to a PDF by checking Content-Type header.
    
    Args:
        url: URL to check
        timeout: Request timeout in seconds
        
    Returns:
        True if URL points to a PDF, False otherwise
    """
    # Quick check: URL extension
    if url.lower().endswith('.pdf'):
        return True
    
    # Reliable check: HEAD request for Content-Type
    try:
        response = requests.head(
            url, 
            allow_redirects=True, 
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; WandAI/1.0)'}
        )
        content_type = response.headers.get('Content-Type', '').lower()
        return 'application/pdf' in content_type
    except Exception as e:
        logger.warning(f"Failed to check Content-Type for {url}: {e}")
        return False


def scrape_pdf(url: str, timeout: int = 30, s3_service=None, user_id: Optional[str] = None) -> Dict[str, str]:
    """
    Download and extract text from PDF URL. Optionally upload to S3.
    
    Args:
        url: PDF URL to scrape
        timeout: Request timeout in seconds
        s3_service: Optional S3Service instance for uploading PDF
        user_id: Optional user ID for S3 path isolation
        
    Returns:
        Dict with 'text', 'title', 'url', 'content_type', 's3_key' (if S3 enabled), 'pdf_bytes'
        
    Raises:
        URLNotFoundError: If URL returns 404
        NetworkError: If network request fails
        ContentExtractionError: If PDF extraction fails
    """
    try:
        logger.info(f"Downloading PDF from: {url}")
        response = requests.get(
            url,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; WandAI/1.0)'}
        )
        
        if response.status_code == 404:
            raise URLNotFoundError(f"PDF not found: {url}")
        
        response.raise_for_status()
        
        pdf_content = response.content
        
        # Extract text from PDF
        pdf_bytes = BytesIO(pdf_content)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Extract text from all pages
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        
        text = "\n\n".join(text_parts).strip()
        
        if not text:
            raise ContentExtractionError("PDF contains no extractable text")
        
        # Try to get title from PDF metadata
        title = doc.metadata.get('title', '') or url.split('/')[-1]
        
        doc.close()
        
        result = {
            'text': text,
            'title': title,
            'url': url,
            'content_type': 'application/pdf',
            'pdf_bytes': pdf_content  # Include raw bytes for S3 upload
        }
        
        # Upload to S3 if service provided
        if s3_service:
            # Generate S3 key with user namespace
            pdf_hash = hashlib.md5(pdf_content).hexdigest()[:12]
            
            # Include user ID in S3 path for isolation
            user_prefix = f"users/{user_id}" if user_id else "users/anonymous"
            s3_key = f"{user_prefix}/pdfs/{pdf_hash}.pdf"
            
            try:
                s3_result = s3_service.upload_pdf(
                    file_content=pdf_content,
                    s3_key=s3_key,
                    metadata={
                        'source_url': url,
                        'title': title,
                        'user_id': user_id
                    }
                )
                result['s3_key'] = s3_key
                result['s3_bucket'] = s3_result['bucket']
                logger.info(f"✓ Uploaded PDF to S3: {s3_key}")
            except Exception as e:
                logger.warning(f"Failed to upload PDF to S3: {e}")
                # Continue without S3 - not a critical failure
        
        logger.info(f"✓ Extracted {len(text)} characters from PDF")
        
        return result
        
    except requests.exceptions.Timeout:
        raise NetworkError(f"Timeout downloading PDF: {url}")
    except requests.exceptions.ConnectionError:
        raise NetworkError(f"Connection failed: {url}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise URLNotFoundError(f"PDF not found: {url}")
        raise NetworkError(f"HTTP error {e.response.status_code}: {url}")
    except Exception as e:
        raise ContentExtractionError(f"Failed to extract PDF content: {str(e)}")


def scrape_html(url: str, timeout: int = 30) -> Dict[str, str]:
    """
    Extract main content from HTML page using trafilatura.
    
    Args:
        url: HTML page URL to scrape
        timeout: Request timeout in seconds
        
    Returns:
        Dict with 'text', 'title', 'url', 'content_type'
        
    Raises:
        URLNotFoundError: If URL returns 404
        NetworkError: If network request fails
        ContentExtractionError: If content extraction fails
    """
    try:
        logger.info(f"Fetching HTML from: {url}")
        response = requests.get(
            url,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; WandAI/1.0)'}
        )
        
        if response.status_code == 404:
            raise URLNotFoundError(f"Page not found: {url}")
        
        response.raise_for_status()
        
        # Extract main content with trafilatura
        html_content = response.text
        
        # Extract text (removes ads, nav, footers, etc.)
        text = trafilatura.extract(
            html_content,
            include_comments=False,
            include_tables=True,
            no_fallback=False
        )
        
        if not text:
            raise ContentExtractionError(
                "Failed to extract meaningful content. Page may be JavaScript-heavy or paywalled."
            )
        
        # Extract title
        metadata = trafilatura.extract_metadata(html_content)
        title = metadata.title if metadata and metadata.title else url.split('/')[-1]
        
        logger.info(f"✓ Extracted {len(text)} characters from HTML")
        
        return {
            'text': text,
            'title': title,
            'url': url,
            'content_type': 'text/html'
        }
        
    except requests.exceptions.Timeout:
        raise NetworkError(f"Timeout fetching page: {url}")
    except requests.exceptions.ConnectionError:
        raise NetworkError(f"Connection failed: {url}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise URLNotFoundError(f"Page not found: {url}")
        raise NetworkError(f"HTTP error {e.response.status_code}: {url}")
    except ContentExtractionError:
        raise
    except Exception as e:
        raise ContentExtractionError(f"Failed to extract HTML content: {str(e)}")


def scrape_webpage(url: str, timeout: int = 30, s3_service=None, user_id: Optional[str] = None) -> Dict[str, str]:
    """
    Scrape content from URL (auto-detects PDF vs HTML).
    For PDFs, optionally uploads to S3.
    
    Args:
        url: URL to scrape
        timeout: Request timeout in seconds
        s3_service: Optional S3Service instance for uploading PDFs
        user_id: Optional user ID for S3 path isolation
        
    Returns:
        Dict with 'text', 'title', 'url', 'content_type', plus 's3_key' for PDFs
        
    Raises:
        WebScraperError: For various scraping failures
    """
    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        raise WebScraperError(f"Invalid URL format: {url}")
    
    # Detect content type and scrape accordingly
    if is_pdf_url(url, timeout=5):
        return scrape_pdf(url, timeout=timeout, s3_service=s3_service, user_id=user_id)
    else:
        return scrape_html(url, timeout=timeout)
