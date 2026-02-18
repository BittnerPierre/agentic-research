from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from agents import Runner
from agents.mcp import MCPServer

from .agents.qa_agent import create_qa_agent
from .agents.schemas import ResearchInfo
from .config import get_config

SMOKE_DOC_PATH = Path("test_files/smoke_local_doc.md")
logger = logging.getLogger(__name__)


class QAManager:
    def __init__(self):
        self._config = get_config()

    async def run(
        self,
        fs_server: MCPServer,
        dataprep_server: MCPServer,
        vector_mcp_server: MCPServer | None,
        query: str,
        research_info: ResearchInfo,
        progress_callback: (
            Callable[[float, float | None, str | None], Awaitable[None]] | None
        ) = None,
    ) -> None:
        logger.info("QA manager starting")
        logger.info(f"QA query: {query}")
        logger.info(f"QA vector store: {research_info.vector_store_name}")
        logger.info(f"QA smoke doc path: {SMOKE_DOC_PATH.resolve()}")

        if not SMOKE_DOC_PATH.exists():
            raise FileNotFoundError(f"Smoke document not found: {SMOKE_DOC_PATH}")
        logger.info(f"QA smoke doc size: {SMOKE_DOC_PATH.stat().st_size} bytes")

        upload_result = await dataprep_server.call_tool(
            "upload_files_to_vectorstore_tool",
            {
                "inputs": [str(SMOKE_DOC_PATH)],
                "vectorstore_name": research_info.vector_store_name,
            },
        )
        logger.info(f"QA dataprep upload result: {upload_result}")

        qa_agent = create_qa_agent()
        result = await Runner.run(
            qa_agent,
            query,
            context=research_info,
            max_turns=5,
        )

        answer = result.final_output_as(str, raise_if_incorrect_type=False)
        logger.info(f"QA final output: {answer}")
        print("\n\n=====QA ANSWER=====\n")
        print(answer)
