from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o-mini"
    
    # Pinecone
    pinecone_api_key: str = Field(..., env="PINECONE_API_KEY")
    pinecone_index_name: str = Field(..., env="PINECONE_INDEX_NAME")
    pinecone_namespace: str = Field("kb-mvp", env="PINECONE_NAMESPACE")  # Default namespace
    
    def get_user_namespace(self, user_id: str) -> str:
        """Get Pinecone namespace for a specific user"""
        return f"user-{user_id}"
    
    # Exa (optional - will fallback to Wikipedia if not set)
    exa_api_key: str | None = None
    
    # MongoDB
    mongodb_uri: str
    mongodb_db_name: str = "wand-ai-project"
    
    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7
    
    # AWS S3
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_s3_bucket: str
    aws_region: str = "us-east-1"
    
    # App
    upload_dir: str = "./data/uploads"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k: int = 24
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
