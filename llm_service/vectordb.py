from typing import List ,Dict, Tuple
from fastapi import HTTPException
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from config import settings
from collections import defaultdict
import re

import logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=settings.EMBEDDINGS_MODEL,
        model_kwargs={'device': "cpu"}
    )

def get_qdrant_client():
    return QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

def add_urls_to_vectorstore(urls: List[str], vector_store: QdrantVectorStore = None) -> Tuple[int, List[str]]:
    errors = []
    total_added_chunks = 0
    
    try:
        if vector_store is None:
            embeddings = get_embeddings()
            client = get_qdrant_client()
            vector_store = QdrantVectorStore(
                client=client,
                collection_name=settings.COLLECTION_NAME,
                embedding=embeddings,
            )
    except Exception as e:
        logger.error(f"Vector store initialization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Vector store initialization failed: {str(e)}")

    for a_url in urls:
        try:
            print(f"Processing URL: {a_url}")
            docs = WebBaseLoader(a_url).load()
            docs_list = [docs] if not isinstance(docs, list) else docs

            for doc in docs_list:
                doc.page_content = re.sub(r'\s+', ' ', doc.page_content.strip())

            text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                chunk_size=200, chunk_overlap=50
            )
            doc_splits = text_splitter.split_documents(docs_list)
            
            for doc in doc_splits:
                doc.metadata.pop("description", None)  # Safely remove description

            print(f"Created {len(doc_splits)} chunks from URL: {a_url}")

            vector_store.add_documents(
                documents=doc_splits, 
                wait=True
            )
            total_added_chunks += len(doc_splits)
            print(f"Added {len(doc_splits)} documents to vector store")

        except Exception as e:
            error_msg = f"Failed processing URL {a_url}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            continue  # Continue with next URL

    return total_added_chunks, errors


def initialize_vectorstore():
    embeddings = get_embeddings()
    client = get_qdrant_client()

    if not client.collection_exists(settings.COLLECTION_NAME):
        vector_size = len(embeddings.embed_query("sample text"))

        client.create_collection(
            collection_name=settings.COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=settings.COLLECTION_NAME,
        embedding=embeddings,
    )
                
    return vector_store.as_retriever()


def get_metadata_counts() -> Dict[str, int]:
    """Get counts of chunks by metadata"""
    client = get_qdrant_client()
    counts = defaultdict(int)
    
    # Scroll through all points to collect metadata counts
    next_offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=settings.COLLECTION_NAME,
            limit=1000,
            offset=next_offset,
            with_payload=True
        )
        
        if not points:
            break
            
        for point in points:
            # Check different possible ways metadata might be stored
            if point.payload:
                # Try direct source field
                if 'source' in point.payload:
                    source = point.payload['source']
                    counts[source] += 1
                # Try metadata.source field
                elif 'metadata' in point.payload and isinstance(point.payload['metadata'], dict):
                    metadata = point.payload['metadata']
                    if 'source' in metadata:
                        source = metadata['source']
                        counts[source] += 1
        
        if next_offset is None:
            break
            
    return dict(counts)

def delete_by_metadata(metadata_value: str) -> int:
    """Delete vectors by metadata value using a more direct approach
    
       There are better ways , but i prefer with  more control
    """
    client = get_qdrant_client()
    
    # Scroll through all points to find those with matching metadata
    points_to_delete = []
    next_offset = None
    
    while True:
        points, next_offset = client.scroll(
            collection_name=settings.COLLECTION_NAME,
            limit=1000,
            offset=next_offset,
            with_payload=True
        )
        
        if not points:
            break
            
        for point in points:
            # Check different possible ways metadata might be stored
            payload = point.payload
            if payload:
                # Check direct source field
                if "source" in payload and payload["source"] == metadata_value:
                    points_to_delete.append(point.id)
                # Check nested metadata.source field
                elif ("metadata" in payload and 
                      isinstance(payload["metadata"], dict) and 
                      "source" in payload["metadata"] and 
                      payload["metadata"]["source"] == metadata_value):
                    points_to_delete.append(point.id)
        
        if next_offset is None:
            break
    
    print(f"Found {len(points_to_delete)} points to delete")
    
    # Delete the points by their IDs
    if points_to_delete:
        client.delete(
            collection_name=settings.COLLECTION_NAME,
            points_selector=points_to_delete
        )
    
    return len(points_to_delete)

