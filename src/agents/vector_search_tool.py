from agents import RunContextWrapper, function_tool

from ..config import get_config
from ..dataprep.mcp_functions import vector_search as _vector_search
from .schemas import ResearchInfo


@function_tool
async def vector_search(
    wrapper: RunContextWrapper[ResearchInfo],
    query: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> dict:
    config = get_config()
    if wrapper.context.vector_store_name:
        config.vector_search.index_name = wrapper.context.vector_store_name

    result = _vector_search(
        query=query, config=config, top_k=top_k, score_threshold=score_threshold
    )
    return {
        "query": result.query,
        "results": [
            {
                "document": hit.document,
                "metadata": hit.metadata,
                "score": hit.score,
            }
            for hit in result.results
        ],
    }
