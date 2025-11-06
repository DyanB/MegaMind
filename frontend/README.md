# MegaMind Frontend

Next.js 15 frontend for the MegaMind document Q&A system.

### Pages
- **Login/Signup** (`/auth/login`, `/auth/signup`) - User authentication
- **Home** (`/`) - Main page with document upload, URL ingestion, and Q&A interface
- **Knowledge Base** (`/knowledge-base`) - View and manage all your documents

### Key Features
- JWT authentication with token stored in localStorage
- Protected routes - redirects to login if not authenticated
- File upload with drag-and-drop support
- We go to the URL and do ingestion for web content
- Q&A interface with complete answer generation
- Source citations showing which documents were used
- Answer rating system (thumbs up/down)
- Completeness indicators (green/yellow/red)
- External KB enrichment with "Add to KB" button
- Document management with delete functionality
- Clean document names (hash prefixes automatically removed)

### Components
- `Header.tsx` - Navigation with user info and logout
- `ProtectedRoute.tsx` - Wraps pages that require authentication
- `AnswerCard.tsx` - Displays Q&A results with sources
- `DocumentCard.tsx` - Shows document info in knowledge base

### Tech Stack
- Next.js 15 (App Router)
- React 18
- TypeScript
- Tailwind CSS
- Axios for API calls

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Environment Variables

Create `.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure
```
frontend/
├── app/
│   ├── auth/          # Login and signup pages
│   ├── knowledge-base/ # Document management page
│   ├── page.tsx       # Home page (main Q&A interface)
│   └── layout.tsx     # Root layout
├── components/        # Reusable React components
├── lib/              # Utilities and helpers
└── public/           # Static assets
```

## How It Works

1. **Auth Flow**: User signs up or logs in, gets JWT token stored in localStorage
2. **Protected Routes**: ProtectedRoute component checks for token and redirects if needed
3. **API Calls**: All requests include JWT token in Authorization header
4. **Document Upload**: Send file to `/documents/upload` endpoint
5. **URL Ingestion**: Send URL to `/documents/ingest-url` endpoint
6. **Ask Questions**: POST to `/search/ask` with question and get answer + sources
7. **Rate Answers**: POST to `/search/rate` with query_id and rating

## UI Features

### Home Page
- File upload area
- URL input for web content
- Question input with Ask button
- Answer display with:
  - Generated answer text
  - Completeness score with color coding
  - Source documents used
  - Rating buttons (thumbs up/down)
  - External sources (if enrichment triggered)

### Knowledge Base
- Grid of document cards
- Each card shows:
  - Document name (cleaned, no hash)
  - Source type (PDF/DOCX/URL)
  - Upload date
  - Delete button

### Auth Pages
- Clean, centered design
- Form validation
- Error messages
- Redirect to home after successful login


