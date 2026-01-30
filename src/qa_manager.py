from __future__ import annotations

from pathlib import Path

from agents import Runner
from agents.mcp import MCPServer

from .agents.qa_agent import create_qa_agent
from .agents.schemas import ResearchInfo
from .config import get_config

SMOKE_DOC_PATH = Path("test_files/smoke_local_doc.md")


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
    ) -> None:
        if vector_mcp_server is None:
            raise ValueError("vector_mcp_server is required for qa_manager")

        if not SMOKE_DOC_PATH.exists():
            raise FileNotFoundError(f"Smoke document not found: {SMOKE_DOC_PATH}")

        await dataprep_server.call_tool(
            "upload_files_to_vectorstore_tool",
            {
                "inputs": [str(SMOKE_DOC_PATH)],
                "vectorstore_name": research_info.vector_store_name,
            },
        )

        qa_agent = create_qa_agent([vector_mcp_server])
        result = await Runner.run(
            qa_agent,
            query,
            context=research_info,
            max_turns=5,
        )

        answer = result.final_output_as(str, raise_if_incorrect_type=False)
        print("\n\n=====QA ANSWER=====\n")
        print(answer)
