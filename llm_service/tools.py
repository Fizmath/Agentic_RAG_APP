import threading
from typing import Optional

from langchain.tools.retriever import create_retriever_tool
from vectordb import initialize_vectorstore


class RetrieverToolManager:
    """
    Thread-safe manager for a singleton retriever tool and its underlying retriever.
    Supports hot-refreshing the retriever instance while readers continue to use
    the most recent stable instance.

    It uses a reader-writer pattern with a single lock (coarse-grained),
    which is sufficient for most FastAPI workloads.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._retriever = None
        self._tool = None

    def _build_tool(self):
        """
        Build and return a langchain retriever tool from the current retriever.
        """
        if self._retriever is None:
            raise RuntimeError("Retriever is not initialized")
        return create_retriever_tool(
            self._retriever,
            "retrieve_blog_posts",
            "Search and return information about Lilian Weng blog posts.",
        )

    def get_tool(self):
        """
        Get the current retriever tool, initializing on first access.
        """
        with self._lock:
            if self._tool is None:
                # Initialize underlying retriever and tool
                self._retriever = initialize_vectorstore()
                self._tool = self._build_tool()
            return self._tool

    def refresh(self):
        """
        Refresh the underlying vectorstore/retriever and recreate the tool.
        Returns the new tool instance.
        """
        with self._lock:
            self._retriever = initialize_vectorstore()
            self._tool = self._build_tool()
            return self._tool


# Module-level singleton manager
_manager: Optional[RetrieverToolManager] = None
_manager_lock = threading.Lock()


def _get_manager() -> RetrieverToolManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = RetrieverToolManager()
    return _manager


def get_retriever_tool(refresh: bool = False):
    """
    Public accessor for the retriever tool.
    - If refresh=True, rebuild the retriever and tool.
    - Else, return the current (lazy-initialized) tool.
    """
    mgr = _get_manager()
    if refresh:
        return mgr.refresh()
    return mgr.get_tool()


def refresh_retriever():
    """
    Force a refresh of the retriever tool.
    """
    mgr = _get_manager()
    return mgr.refresh()