import contextlib
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from schemas import QuestionRequest, AnswerResponse ,UrlInjectionRequest , MetadataQueryResponse, DeleteRequest
from vectordb import  add_urls_to_vectorstore ,get_metadata_counts, delete_by_metadata ,get_qdrant_client
from graph import GraphBuilder
from tools import get_retriever_tool, refresh_retriever
from config import settings
from typing import  Any

import os
import time
import io
import logging


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("agentic_rag_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    _init_locks()
    logger.info("Starting Agentic RAG API...")
    try:
        _compile_global_graph(refresh_tools=False)
        logger.info("Startup complete.")
    except Exception as e:
        logger.exception("Failed to build initial graph: %s", e)
        # Optionally re-raise if you want to fail fast
        # raise

    yield  # App runs here

    # Shutdown logic
    logger.info("Shutting down Agentic RAG API.")


app = FastAPI(title="Agentic RAG API" , lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:80"],  #  uncomment when using embedded dist 
    # allow_origins=["*"],                  #  comment when using embedded dist
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------------------
# Global Graph State (hot-swappable)
# ------------------------------------------------------------------------------
_graph_lock = None
_graph = None
_tools = None
_last_refresh_ts = 0.0
_refresh_cooldown_sec = 5.0  # Debounce to avoid frequent recompiles


def _init_locks():
    global _graph_lock
    import threading

    if _graph_lock is None:
        _graph_lock = threading.RLock()


def _build_graph(tools) -> Any:
    """
    Compile and return a graph using the provided tools and selected LLM.
    """
    graph_builder = GraphBuilder(tools, llm_model=settings.LLM_MODEL)
    return graph_builder.compile()


def _ensure_graph_visualization(graph) -> None:
    """
    Generate and persist a visualization image of the graph.
    Best-effort; errors are logged but not raised.
    """
    try:
        os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
        graph_image_path = os.path.join(settings.DOCUMENTS_DIR, "graph.png")
        png_bytes = graph.get_graph(xray=True).draw_mermaid_png()
        with open(graph_image_path, "wb") as f:
            f.write(png_bytes)
        logger.info("Saved graph visualization to %s", graph_image_path)
    except Exception as e:
        logger.warning("Failed to generate graph visualization: %s", e)


def _compile_global_graph(refresh_tools: bool = False) -> None:
    """
    Build or rebuild the global tools and graph. Optionally refresh tools first.
    """
    global _graph, _tools

    if refresh_tools:
        _tools = get_retriever_tool(refresh=True)
    else:
        _tools = _tools or get_retriever_tool(refresh=False)

    _graph = _build_graph(_tools)
    _ensure_graph_visualization(_graph)
    logger.info("Graph compiled with model=%s", settings.LLM_MODEL)


def _maybe_refresh_graph_debounced(force: bool = False) -> bool:
    """
    Recompile the graph if enough time has elapsed since the last refresh, or if forced.
    Returns True if a refresh occurred.
    """
    global _last_refresh_ts
    now = time.perf_counter()
    if not force and (now - _last_refresh_ts) < _refresh_cooldown_sec:
        return False

    _compile_global_graph(refresh_tools=True)
    _last_refresh_ts = now
    return True



# ------------------------------------------------------------------------------
# Background tasks
# ------------------------------------------------------------------------------
def refresh_retriever_background(force_graph_refresh: bool = True):
    """
    Refresh retriever and optionally recompile the graph.
    Safe to call from a background thread.
    """
    try:
        logger.info("Refreshing retriever in background...")
        refresh_retriever()
        if force_graph_refresh:
            _maybe_refresh_graph_debounced(force=True)
        logger.info("Retriever refresh complete.")
    except Exception as e:
        logger.exception("Background retriever refresh failed: %s", e)


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _stream_graph_answer(graph, user_question: str) -> str:
    """
    Streams LangGraph updates to a buffer and returns the full formatted text.
    This preserves your existing UX (pretty_print) while returning as text.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for chunk in graph.stream(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": user_question,
                    }
                ]
            }
        ):
            for node, update in chunk.items():
                print("Update from node", node)
                # Guard in case structure changes
                try:
                    update["messages"][-1].pretty_print()
                except Exception:
                    print(update)
                print("\n\n")
    return buf.getvalue()


# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """
    Ask a question to the Agentic RAG pipeline.
    Returns the pretty-printed execution trace as the answer for transparency.
    """
    start = time.perf_counter()
    try:
        # Defensive: build once if not available (e.g., lazy import scenarios)
        global _graph
        if _graph is None:
            _compile_global_graph(refresh_tools=False)

        answer_text = _stream_graph_answer(_graph, request.question)
        elapsed = time.perf_counter() - start
        return AnswerResponse(answer=answer_text, processing_time=f"{elapsed:.2f}")
    except Exception as e:
        logger.exception("Error in /ask: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/inject")
async def inject_urls(request: UrlInjectionRequest, background_tasks: BackgroundTasks):
    """
    Inject URLs into the vector store, then schedule a retriever refresh in the background.
    Returns partial success info if some URLs fail.
    """
    try:
        if not request.urls:
            raise HTTPException(status_code=400, detail="No URLs provided")

        added_count, errors = add_urls_to_vectorstore(request.urls)

        # Schedule refresh even if partial failures occurred
        background_tasks.add_task(refresh_retriever_background, True)

        if errors:
            return {
                "message": f"Added {added_count} chunks with {len(errors)} errors",
                "errors": errors,
                "status": "partial_success",
                "added_count": added_count,
            }

        return {
            "message": f"Successfully added {added_count} chunks",
            "status": "success",
            "added_count": added_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in /inject: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/delete_by_metadata")
async def delete_by_metadata_endpoint(request: DeleteRequest, background_tasks: BackgroundTasks):
    """
    Delete vectors by metadata value (e.g., URL).
    Always schedules a retriever refresh in the background.
    """
    try:
        if not request.url:
            raise HTTPException(status_code=400, detail="Missing 'url' in request")

        deleted_count = delete_by_metadata(request.url)

        # Refresh retriever in background
        background_tasks.add_task(refresh_retriever_background, True)

        if deleted_count > 0:
            return {
                "message": f"Successfully deleted {deleted_count} chunks with metadata '{request.url}'",
                "deleted_count": deleted_count,
                "status": "success",
            }
        else:
            return {
                "message": f"No chunks found with metadata '{request.url}'",
                "deleted_count": 0,
                "status": "no_match",
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /delete_by_metadata: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/metadata/counts", response_model=MetadataQueryResponse)
async def get_metadata_counts_endpoint():
    """Get counts of chunks by metadata"""
    try:
        counts = get_metadata_counts()
        return MetadataQueryResponse(metadata_counts=counts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@app.get("/debug/points")
async def debug_points(limit: int = 1000):
    """Debug endpoint to see what's stored in the database"""
    try:
        client = get_qdrant_client()
        points, _ = client.scroll(
            collection_name=settings.COLLECTION_NAME,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        debug_points = []
        for point in points:
            debug_points.append({
                "id": str(point.id),
                "payload": point.payload,
                # "vector": point.vector[:5] if point.vector else []  # First 5 elements
            })
            
        return points
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/api/config")
async def get_config():
    ss = settings.EMBEDDINGS_MODEL
    return {
        "llm_model": settings.LLM_MODEL,
        "embeddings_model": ss.rsplit("/", 1)[-1]
    }


app.mount("/", StaticFiles(directory="dist", html=True), name="static")  #  uncomment when using embedded dist 

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)