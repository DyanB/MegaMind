from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from app.routes import documents, search, auth
from app.database import MongoDB

# Load environment variables from .env file
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Connect to MongoDB
    await MongoDB.connect_db()
    yield
    # Shutdown: Close MongoDB connection
    await MongoDB.close_db()


app = FastAPI(
    title="AI Knowledge Base API",
    description="RAG-powered document search with completeness detection and user authentication",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)  # Auth routes first
app.include_router(documents.router)
app.include_router(search.router)


@app.get("/")
async def root():
    return {
        "message": "AI Knowledge Base API",
        "docs": "/docs",
        "health": "/healthz"
    }


@app.get("/healthz")
async def health_check():
    return {"status": "healthy"}
