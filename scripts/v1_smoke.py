#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.request


def default_url(service_host: str, port: int) -> str:
    if os.path.exists("/.dockerenv"):
        return f"http://{service_host}:{port}"
    return f"http://localhost:{port}"


CHROMA_URL = os.environ.get("CHROMA_URL", default_url("chromadb", 8000))
EMBED_URL = os.environ.get(
    "EMBED_URL",
    os.environ.get("EMBEDDINGS_URL", default_url("embeddings-cpu", 8003)),
)
LLM_INSTRUCT_URL = os.environ.get(
    "LLM_INSTRUCT_URL",
    os.environ.get("LLAMA_URL", default_url("llama-cpp-cpu", 8002)),
)
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "v1-smoke")
CHROMA_TENANT = os.environ.get("CHROMA_TENANT", "default_tenant")
CHROMA_DATABASE = os.environ.get("CHROMA_DATABASE", "default_database")


def log(message):
    print(message)


def request_json(method, url, payload=None, headers=None):
    headers = headers or {}
    data = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        data = body
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8") if err.fp else ""
        return err.code, body
    except Exception as err:
        raise SystemExit(f"Request failed: {method} {url}: {err}")


def chroma_urls(path):
    if CHROMA_TENANT and CHROMA_DATABASE:
        base = (
            f"{CHROMA_URL}/api/v2/tenants/{CHROMA_TENANT}"
            f"/databases/{CHROMA_DATABASE}{path}"
        )
        return [base]
    return [f"{CHROMA_URL}{path}"]


def chroma_request(method, path, payload=None):
    last = (None, "")
    for url in chroma_urls(path):
        last = request_json(method, url, payload)
        status, _ = last
        if 200 <= status < 300:
            return last
    return last


def wait_for_health(url, retries=10, delay=1):
    for _ in range(retries):
        status, _ = request_json("GET", url)
        if 200 <= status < 300:
            return True
        time.sleep(delay)
    return False


def pick_first_healthy(urls, path="/health", retries=5, delay=1):
    for url in urls:
        if wait_for_health(f"{url}{path}", retries=retries, delay=delay):
            return url
    return None


def parse_json(body, context):
    try:
        return json.loads(body)
    except json.JSONDecodeError as err:
        raise SystemExit(f"Invalid JSON from {context}: {err}")


def extract_embedding(data):
    if isinstance(data, dict):
        items = data.get("data")
        if items:
            emb = items[0].get("embedding")
            if emb:
                return emb
        embeddings = data.get("embeddings")
        if embeddings:
            return embeddings[0]
    raise SystemExit("No embeddings returned from embeddings service")


def main():
    log("Chroma heartbeat...")
    status, _ = request_json("GET", f"{CHROMA_URL}/api/v2/heartbeat")
    if not (200 <= status < 300):
        raise SystemExit("Chroma heartbeat failed")

    embed_urls = [EMBED_URL]
    embed_urls.append(default_url("embeddings-cpu", 8003))
    embed_urls.append(default_url("embeddings-gpu", 8003))
    embed_urls = list(dict.fromkeys(embed_urls))

    log("Wait for embeddings health...")
    embed_url = pick_first_healthy(embed_urls)
    if not embed_url:
        raise SystemExit("Embeddings service not healthy")

    log("Embedding request...")
    status, body = request_json("POST", f"{embed_url}/v1/embeddings", {"input": "smoke test"})
    if not (200 <= status < 300):
        log(f"Embeddings /v1/embeddings failed ({status}); trying /embed...")
        status, body = request_json("POST", f"{embed_url}/embed", {"inputs": "smoke test"})
    if not (200 <= status < 300):
        raise SystemExit(f"Embeddings request failed ({status})")
    if not body:
        raise SystemExit(f"Embeddings response was empty (status {status})")
    embedding = extract_embedding(parse_json(body, "embeddings"))

    log("Create or fetch collection...")
    status, body = chroma_request(
        "POST", "/collections", {"name": COLLECTION_NAME}
    )
    collection_id = ""
    if 200 <= status < 300 and body:
        data = parse_json(body, "create collection")
        collection_id = data.get("id", "")

    if not collection_id:
        status, body = chroma_request("GET", "/collections")
        if not (200 <= status < 300):
            raise SystemExit(
                f"Failed to list Chroma collections (status {status}): {body}"
            )
        data = parse_json(body, "list collections")
        if isinstance(data, list):
            items = data
        else:
            items = data.get("collections", [])
        for item in items:
            if item.get("name") == COLLECTION_NAME:
                collection_id = item.get("id", "")
                break

    if not collection_id:
        raise SystemExit("Failed to resolve collection id")

    log("Add document...")
    status, _ = chroma_request(
        "POST",
        f"/collections/{collection_id}/add",
        {"ids": ["doc-1"], "embeddings": [embedding], "documents": ["smoke test doc"]},
    )
    if not (200 <= status < 300):
        raise SystemExit("Failed to add document to Chroma")

    log("Query collection...")
    status, _ = chroma_request(
        "POST",
        f"/collections/{collection_id}/query",
        {"query_embeddings": [embedding], "n_results": 1},
    )
    if not (200 <= status < 300):
        raise SystemExit("Failed to query Chroma collection")

    llm_urls = [LLM_INSTRUCT_URL]
    llm_urls.append(default_url("llama-cpp-cpu", 8002))
    llm_urls.append(default_url("llm-instruct", 8002))
    llm_urls = list(dict.fromkeys(llm_urls))

    log("Llama.cpp health...")
    llm_url = pick_first_healthy(llm_urls)
    if not llm_url:
        # Fall back to /v1/models probe for OpenAI-compatible servers
        for url in llm_urls:
            status, _ = request_json("GET", f"{url}/v1/models")
            if 200 <= status < 300:
                llm_url = url
                break
    if not llm_url:
        raise SystemExit("Llama.cpp health check failed")

    log("Llama.cpp chat completion...")
    status, _ = request_json(
        "POST",
        f"{llm_url}/v1/chat/completions",
        {"model": "local", "messages": [{"role": "user", "content": "say ok"}], "max_tokens": 5},
    )
    if not (200 <= status < 300):
        raise SystemExit("Llama.cpp chat completion failed")

    log("V1 smoke test OK")


if __name__ == "__main__":
    main()
