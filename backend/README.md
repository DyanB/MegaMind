# MegaMind Backend

FastAPI backend for the MegaMind document Q&A system.

### Core Features
- User authentication with JWT tokens.
- Document upload (PDF, DOCX) with chunking and embedding
- Web URL ingestion with trafilatura (content extraction)
- Vector search with Pinecone (user-specific namespaces to handle multiple users' KB)
- MongoDB for user data, ratings, and analytics
- S3 for PDF storage
- Multi-query retrieval for better results
- Automatic completeness detection
- External enrichment with Exa Search and Wikipedia
- Document quality scoring based on user ratings
- Comprehensive analytics tracking using Mongo

### API Endpoints

#### Auth
- `POST /auth/signup` - Create new user account
- `POST /auth/login` - Login and get JWT token

#### Documents
- `POST /documents/upload` - Upload PDF or DOCX file
- `POST /documents/ingest-url` - Add web page content
- `GET /documents/list` - List all user's documents
- `DELETE /documents/{doc_id}` - Delete a document

#### Search
- `POST /search/ask` - Ask a question, get AI answer with sources
- `POST /search/rate` - Rate an answer (thumbs up/down)

### Tech Stack
- FastAPI (Python web framework)
- Python 3.11
- OpenAI GPT-4o (LLM)
- OpenAI text-embedding-3-small (embeddings)
- Pinecone (vector database)
- MongoDB Atlas (user data, analytics)
- AWS S3 (file storage)
- Trafilatura (web scraping)
- JWT (authentication)

## Project Structure
```
backend/
├── app/
│   ├── routes/
│   │   ├── auth.py         # Signup/login endpoints
│   │   ├── documents.py    # Upload/ingest/list/delete
│   │   └── search.py       # Ask questions, rate answers
│   ├── services/
│   │   ├── vector_store.py        # Pinecone operations
│   │   ├── document_processor.py  # Chunking, embedding
│   │   ├── llm_service.py         # OpenAI API calls
│   │   ├── enrichment_service.py  # Exa + Wikipedia
│   │   ├── analytics_service.py   # MongoDB analytics
│   │   ├── mongo_rating_service.py # Document ratings
│   │   └── s3_service.py          # S3 upload/download
│   ├── models/
│   │   ├── user.py        # User Pydantic models
│   │   ├── document.py    # Document models
│   │   └── analytics.py   # Analytics models
│   ├── middleware/
│   │   └── auth.py        # JWT verification
│   └── main.py            # FastAPI app
└── requirements.txt
```

## Getting Started

### Installation
```bash
cd backend
python -m venv wand-env
source wand-env/bin/activate  # Windows: wand-env\Scripts\activate
pip install -r requirements.txt
```

### Environment Variables

Create `.env` file:
```
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=wandai
PINECONE_NAMESPACE=default

# MongoDB
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DB_NAME=wand-ai-project

# AWS S3 (Optional)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET_NAME=wandai-pdfs

# JWT
JWT_SECRET_KEY=your-secret-key-at-least-32-characters
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# External APIs (Optional)
EXA_API_KEY=...

# Application
UPLOAD_DIR=./uploads
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K=10
```

### Run Server
```bash
uvicorn app.main:app --reload
```

Server runs on http://localhost:8000  
API docs at http://localhost:8000/docs

## How It Works

### 1. Document Upload Flow
1. User uploads PDF/DOCX via `/documents/upload`
2. Calculate MD5 hash to check for duplicates
3. Save file to S3 (or local uploads folder)
4. Extract text with PyMuPDF (fitz)/python-docx
5. Chunk text (500 chars, 50 overlap)
6. Generate embeddings with OpenAI
7. Store in Pinecone with user namespace
8. Save metadata to MongoDB
9. Return success

### 2. URL Ingestion Flow
1. User submits URL via `/documents/ingest-url`
2. Check URL hash for duplicates
3. Scrape with trafilatura (extracts main content)
4. Extract main content
5. Chunk, embed, store (same as upload)

### 3. Question Answering Flow
1. User asks question via `/search/ask`
2. Generate 1 query variation (2 total queries)
3. Search each in Pinecone (user namespace only)
4. Apply document quality scoring (from ratings)
5. Deduplicate and merge results
6. Send context + question to GPT-4o
7. Check answer completeness with LLM
8. If incomplete (<85%), trigger enrichment:
   - Search Exa API
   - Search Wikipedia
   - Return external sources
9. Log analytics to MongoDB
10. Return answer + sources + completeness

### 4. Rating Flow
1. User rates answer via `/search/rate`
2. Validate: were sources actually used?
3. Update document scores in MongoDB
4. Recalculate quality factor (0.9-1.1x)
5. Future searches use adjusted scores

## Key Services

### VectorStore (`vector_store.py`)
- Connects to Pinecone
- User-specific namespaces for isolation
- Multi-query search with deduplication
- Quality score adjustments

### DocumentProcessor (`document_processor.py`)
- Extracts text from PDF/DOCX
- Chunks with overlap
- Generates OpenAI embeddings
- Handles duplicates

### LLMService (`llm_service.py`)
- Calls OpenAI API
- Generates query variations
- Produces answers
- Checks completeness

### EnrichmentService (`enrichment_service.py`)
- Exa Search integration
- Wikipedia API calls
- Triggered on incomplete answers

### AnalyticsService (`analytics_service.py`)
- Tracks all queries to MongoDB
- Updates document usage stats
- Updates user activity stats

### MongoRatingService (`mongo_rating_service.py`)
- Stores upvotes/downvotes
- Calculates document quality scores
- Provides boost/penalty factors

## Multi-Tenant Isolation

We use 3 layers:
1. **Pinecone namespace**: `user-{user_id}`
2. **MongoDB filter**: `{"user_id": current_user.id}`
3. **S3 prefix**: `users/{user_id}/pdfs/`

This ensures users only see their own data.

## Security Features
- JWT tokens with expiration
- Protected routes with JWT middleware
- User-specific data isolation
- Input validation with Pydantic

