# MegaMind - Document Q&A System

A RAG (Retrieval-Augmented Generation) system where users can upload documents or add web URLs, then ask questions and get answers with source citations.

### Core Features
- **User Authentication**: Signup/login with JWT tokens and bcrypt password hashing
- **Multi-tenant System**: Each user has their own isolated knowledge base
- **Document Upload**: Upload PDFs or DOCX files to your knowledge base
- **Web Content**: Add web pages by URL (using trafilatura for content extraction)
- **Ask Questions**: Get AI-generated answers based on your documents
- **Source Citations**: See which documents were used to answer your question
- **Quality Ratings**: Rate answers with thumbs up/down to improve future results
- **Document Management**: View, delete, and manage all your uploaded documents
- **Analytics Tracking**: Track queries, document usage, and user activity

### How It Works
1. **Upload Documents**: Users upload PDFs, DOCX, or add URLs
2. **Processing**: Documents are chunked and converted to embeddings
3. **Storage**: Vectors stored in Pinecone, metadata in MongoDB, files in S3
4. **Search**: When you ask a question, we search your knowledge base
5. **Answer**: GPT-4 generates an answer using the retrieved context
6. **Completeness Check**: We check if the answer is complete
7. **Enrichment**: If answer is incomplete, we search Exa and Wikipedia
8. **Rating**: You can rate the answer quality

### Tech Stack
- **Frontend**: Next.js 15, React, TypeScript, Tailwind CSS
- **Backend**: FastAPI, Python 3.11
- **Database**: MongoDB Atlas (users, ratings, analytics)
- **Vector DB**: Pinecone (document embeddings)
- **Storage**: AWS S3 (PDF files)
- **LLM**: OpenAI GPT-4o
- **Auth**: JWT tokens + bcrypt

### User Isolation (Multi-tenancy)
I built a 3-layer isolation system:
1. **Pinecone**: Each user has their own namespace (user-{user_id})
2. **MongoDB**: All queries filter by user_id
3. **S3**: Files stored under users/{user_id}/pdfs/

This means users can't see or access each other's data.

## System Architecture

### Overall Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Auth Pages   │  │  Home Page   │  │  Knowledge Base  │   │
│  │ Login/Signup │  │ Upload + Ask │  │  Doc Management  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │ JWT Token (Authorization Header)
                            ▼
┌────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   API Routes                         │  │
│  │  /auth/*  /documents/*  /search/*                    │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                    │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │               Services Layer                         │  │
│  │  • VectorStore    • DocumentProcessor                │  │
│  │  • LLMService     • EnrichmentService                │  │
│  │  • AnalyticsService • MongoRatingService             │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────┬──────────────┬──────────────┬──────────────────┘
            │              │              │
            ▼              ▼              ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  Pinecone   │  │  MongoDB    │  │   AWS S3    │
   │             │  │             │  │             │
   │ Namespaces: │  │ Filter by:  │  │ Prefix by:  │
   │ user-{id}   │  │ user_id     │  │ users/{id}/ │
   └─────────────┘  └─────────────┘  └─────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
   ┌─────────────┐              ┌─────────────┐
   │ OpenAI API  │              │ Exa + Wiki  │
   │ GPT-4o      │              │ Enrichment  │
   └─────────────┘              └─────────────┘
```

### Document Upload Flow
```
User Upload PDF/DOCX
        │
        ▼
┌───────────────────┐
│ Extract Text      │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Chunk Text        │ 
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Generate Embedding│
│ (OpenAI API)      │
└────────┬──────────┘
         │
         ├──────────────────────┐
         ▼                      ▼
┌─────────────────-┐    ┌────────────────┐
│ Store in Pinecone│    │ Save Metadata  │
│ Namespace:       │    │ in MongoDB     │
│ user-{user_id}   │    │ user_id field  │
└─────────────────-┘    └────────────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
            ┌─────────────┐
            │ Upload to S3│
            │ (Optional)  │
            └─────────────┘
```

### Question Answering Flow
```
User asks a Question
         │
         ▼
┌────────────────────┐
│ Generate 1 Query   │
│ Variation (LLM)    │
│ Total: 2 queries   │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Search Pinecone    │
│ In user namespace  │
│ user-{user_id}     │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Apply Quality      │
│ Scoring (0.9-1.1x) │
│ From user ratings  │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Deduplicate &      │
│ Merge Results      │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Generate Answer    │
│ GPT-4o with context│
│ & citations [1][2] │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Check Completeness │
│ LLM evaluates      │
│ Threshold: 85%     │
└─────────┬──────────┘
          │
     Is Complete?
     ├─ Yes → Return Answer
     └─ No ↓
          │
          ▼
┌────────────────────┐
│ Trigger Enrichment │
│ • Search Exa API   │
│ • Search Wikipedia │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Return Answer +    │
│ External Sources   │
│ "Add to KB" button │
└────────────────────┘
```

### Multi-Tenancy (3-Layer Isolation)
```
User A                           User B
  │                                │
  ▼                                ▼
┌─────────────────────────────────────────────┐
│         Layer 1: Pinecone Namespaces        │
│  ┌──────────────┐      ┌──────────────┐     │
│  │ user-alice   │      │  user-bob    │     │
│  │ (Vectors A)  │      │  (Vectors B) │     │
│  └──────────────┘      └──────────────┘     │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         Layer 2: MongoDB Filtering          │
│  ┌──────────────┐      ┌──────────────┐     │
│  │ user_id: A   │      │ user_id: B   │     │
│  │ (Metadata A) │      │ (Metadata B) │     │
│  └──────────────┘      └──────────────┘     │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         Layer 3: S3 Prefixes                │
│  ┌──────────────┐      ┌──────────────┐     │
│  │ users/A/pdfs/│      │ users/B/pdfs/│     │
│  │ (Files A)    │      │ (Files B)    │     │
│  └──────────────┘      └──────────────┘     │
└─────────────────────────────────────────────┘
```

## Getting Started

### Backend Setup
```bash
cd backend
python -m venv wand-env
source wand-env/bin/activate  # On Windows: wand-env\Scripts\activate
pip install -r requirements.txt

# Create .env file with your API keys
# Then run:
uvicorn app.main:app --reload
```

Backend runs on http://localhost:8000

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:3000

### Environment Variables

**Backend (.env)**:
- OPENAI_API_KEY
- PINECONE_API_KEY
- MONGODB_URI
- AWS credentials (if using S3)
- JWT_SECRET_KEY
- EXA_API_KEY (optional, for enrichment)

**Frontend (.env.local)**:
- NEXT_PUBLIC_API_URL=http://localhost:8000

## Project Structure
```
Project Root/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── routes/    # API endpoints
│   │   ├── services/  # Business logic
│   │   ├── models/    # Pydantic models
│   │   └── main.py    # App entry point
│   └── requirements.txt
├── frontend/          # Next.js frontend
│   ├── app/           # Pages (Next.js 15 App Router)
│   ├── components/    # React components
│   └── lib/           # Utilities
└── README.md          # This file
```

## API Endpoints

### Auth
- POST `/auth/signup` - Create account
- POST `/auth/login` - Login

### Documents
- POST `/documents/upload` - Upload PDF/DOCX
- POST `/documents/ingest-url` - Add web URL
- GET `/documents/list` - List all documents
- DELETE `/documents/{doc_id}` - Delete document

### Search
- POST `/search/ask` - Ask a question
- POST `/search/rate` - Rate an answer

## Design Decisions

### Why These Technologies?

**FastAPI + Next.js**
- FastAPI: Python ecosystem perfect for ML/AI integration, automatic API docs, async support
- Next.js 15: Modern React with App Router, great developer experience, easy deployment

**Multi-tenant Architecture (3-layer isolation)**
- **Pinecone namespaces**: Physical separation at vector DB level - fastest, most secure
- **MongoDB user_id filtering**: Logical separation for metadata and analytics
- **S3 user prefixes**: Organizational separation for file storage
- Why all three? Defense in depth - if one layer fails, others still protect data

**MongoDB over PostgreSQL**
- Flexible schema for analytics (different event types, metadata)
- Easy to evolve schema during rapid development
- Native JSON support perfect for nested data (citations, metadata)

**JWT over Sessions**
- Stateless authentication scales better
- Frontend can store token in localStorage
- Easy to implement in 24h constraint

**Multi-query Retrieval**
- Single query often misses relevant chunks
- Generate 1 variation (2 total queries) for better recall
- Faster than 3 variations while still improving results

**Completeness Detection + Enrichment**
- Users frustrated by incomplete answers
- 85% threshold based on testing (sweet spot)
- Exa + Wikipedia provide good external knowledge coverage

**Quality Scoring System**
- User feedback improves retrieval over time
- Simple upvote/downvote easy to implement
- 0.9-1.1x multiplier subtle but effective

### Architecture Choices

**Async/Await Throughout**
- FastAPI async endpoints handle concurrent users better
- MongoDB motor async driver prevents blocking
- Pinecone SDK already async-friendly

**Service Layer Pattern**
- Clean separation: routes → services → external APIs
- Easy to test, mock, and modify
- Each service has single responsibility

**Pydantic Models Everywhere**
- Type safety catches bugs early
- Automatic validation
- Great IDE autocomplete

## Trade-offs (24h Constraint)

### What I Prioritized

✅ **Core RAG pipeline** - Must work end-to-end
✅ **Multi-tenancy** - Critical for real-world use
✅ **User auth** - Can't demo without it
✅ **Completeness + enrichment** - Key differentiator
✅ **Quality ratings** - Shows system learns from feedback
✅ **Clean UI** - First impressions matter

### What I Simplified

**Authentication**
- Direct bcrypt in FastAPI (would use Auth0/Clerk in production)
- Basic JWT without refresh tokens
- No email verification or password reset

**Storage**
- S3 optional, falls back to local files
- No CDN for frontend assets
- Presigned URLs work but could be more sophisticated

**Error Handling**
- Basic try/catch, would add retry logic + circuit breakers
- No rate limiting (would use Redis + Nginx)
- Limited input validation (would add more edge case handling)

**Analytics**
- Simple MongoDB collections, no real-time dashboard
- Would use Elasticsearch + Kibana for production search/analytics
- No retention policies or data archival

**Testing**
- Manual testing only (no pytest, no Jest)
- Would add unit tests, integration tests, E2E tests
- No CI/CD pipeline (would use GitHub Actions)

**Performance**
- Single-region deployment
- No caching layer (would use Redis for embeddings, frequent queries)
- No connection pooling optimizations
- Chunking strategy could be more sophisticated (fixed 500 chars)

### What Worked Well

**Dependency injection for enrichment** - Abstract `SearchProvider` base class makes it trivial to add new search APIs (Tavily, Perplexity, etc.) without changing core logic

**Multi-query retrieval** - Big quality improvement, easy to implement

**MongoDB for analytics** - Flexible schema saved time vs. SQL migrations

**Service layer pattern** - Clean code structure, easy to debug

**Trafilatura for web scraping** - Fast, reliable content extraction without browser overhead

**Pinecone namespaces** - User isolation was trivial to implement

**Next.js App Router** - Fast development, good DX


## Future Scope

### Deployment
- Frontend: Deploy to Vercel
- Backend: Containerize and deploy to AWS EKS

### Observability
- Add Prometheus metrics
- Set up Grafana dashboards
- Monitor latency, errors, query patterns

### Features
- Re-ranking models for better retrieval
- Conversation history
- Admin dashboard

## Notes
- Hash prefixes are automatically removed from document names in UI
- Quality scoring kicks in after 3+ ratings
- Completeness threshold is 85%
