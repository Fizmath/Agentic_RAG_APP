import os
from dataclasses import dataclass

@dataclass
class Settings:
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "qdrant")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", 6333))
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "my_collection")
    EMBEDDINGS_MODEL: str = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-mpnet-base-v2")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
    # LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen3:1.7b")
    DOCUMENTS_DIR: str = os.getenv("DOCUMENTS_DIR", "/app/documents")

settings = Settings()