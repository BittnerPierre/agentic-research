from __future__ import annotations

import os

import uvicorn
from restate.endpoint import Endpoint

from src.agents.file_writer_agent_restate import build_writer_restate_service


def main() -> None:
    host = os.environ.get("RESTATE_WRITER_HOST", "0.0.0.0")
    port = int(os.environ.get("RESTATE_WRITER_PORT", "9080"))

    config_file = os.environ.get("RESTATE_WRITER_CONFIG")

    endpoint = Endpoint()
    endpoint.bind(build_writer_restate_service(config_file=config_file))

    uvicorn.run(endpoint.app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
