import os
import uuid
import time
import json
import queue
import asyncio
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import Optional, Dict
from agents.graph import run_review, review_graph

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="CodeSensei API",
    description="5-agent AI code review system",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ── Storage ───────────────────────────────────────────────────────────────────
jobs: Dict[str, Dict] = {}
streams: Dict[str, queue.Queue] = {}


# ── Startup — preload embedding model ─────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    print("[Startup] Preloading embedding model...")
    try:
        from vectorstore.embed import load_model
        load_model()
        print("[Startup] Embedding model ready.")
    except Exception as e:
        print(f"[Startup] Model preload warning: {e}")


# ── Models ────────────────────────────────────────────────────────────────────
class ReviewRequest(BaseModel):
    repo_url: str
    github_token: Optional[str] = ""


class ReviewResponse(BaseModel):
    job_id: str
    message: str


# ── Background job — uses review_graph.stream() ───────────────────────────────
def run_review_job(job_id: str, repo_url: str, github_token: str):
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = time.time()
    q = streams.get(job_id)

    def emit(event: dict):
        """Push SSE event to queue if a stream client is connected."""
        if q:
            q.put(event)

    try:
        initial_state = {
            "repo_url": repo_url,
            "github_token": github_token,
            "status": "starting",
            "metadata": None,
            "file_count": None,
            "chunk_count": None,
            "collection_name": None,
            "file_paths": [],
            "bugs": [],
            "arch_issues": [],
            "quality": None,
            "report_markdown": None,
            "score": None,
            "critical_count": 0,
            "high_count": 0,
            "error": None
        }

        final_state = None

        # Stream through each agent node — yields state after each node completes
        for chunk in review_graph.stream(initial_state):
            node_name = list(chunk.keys())[0]
            state = chunk[node_name]
            final_state = state

            # Update polling status
            jobs[job_id]["status"] = state.get("status", "running")

            # Emit per-agent SSE event
            if node_name == "ingest":
                emit({
                    "type": "agent_complete",
                    "agent": 1,
                    "name": "Repo ingestion",
                    "file_count": state.get("file_count", 0),
                    "chunk_count": state.get("chunk_count", 0)
                })

            elif node_name == "bug_hunt":
                emit({
                    "type": "agent_complete",
                    "agent": 2,
                    "name": "Bug hunter",
                    "bug_count": len(state.get("bugs") or []),
                    "bugs": state.get("bugs") or []
                })

            elif node_name == "arch_review":
                emit({
                    "type": "agent_complete",
                    "agent": 3,
                    "name": "Architecture",
                    "arch_issue_count": len(state.get("arch_issues") or [])
                })

            elif node_name == "quality_check":
                q_data = state.get("quality") or {}
                emit({
                    "type": "agent_complete",
                    "agent": 4,
                    "name": "Code quality",
                    "quality_score": q_data.get("quality_score", 0)
                })

            elif node_name == "report":
                if state.get("error"):
                    jobs[job_id]["status"] = "error"
                    jobs[job_id]["error"] = state["error"]
                    emit({"type": "error", "error": state["error"]})
                    emit({"type": "done"})
                    return

        # Build final result from last state
        if final_state:
            quality = final_state.get("quality") or {}
            result = {
                "repo": final_state.get("metadata", {}),
                "score": final_state.get("score", 0),
                "quality_score": quality.get("quality_score", 0),
                "file_count": final_state.get("file_count", 0),
                "chunk_count": final_state.get("chunk_count", 0),
                "critical_count": final_state.get("critical_count", 0),
                "high_count": final_state.get("high_count", 0),
                "bug_count": len(final_state.get("bugs") or []),
                "arch_issue_count": len(final_state.get("arch_issues") or []),
                "bugs": final_state.get("bugs") or [],
                "arch_issues": final_state.get("arch_issues") or [],
                "quality": quality,
                "report_markdown": final_state.get("report_markdown", ""),
                "processing_time_sec": round(
                    time.time() - jobs[job_id]["started_at"], 1
                )
            }

            jobs[job_id]["status"] = "complete"
            jobs[job_id]["result"] = result

            # Emit full result to SSE stream
            emit({"type": "complete", "result": result})

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        emit({"type": "error", "error": str(e)})

    finally:
        # Always send sentinel so SSE generator closes cleanly
        emit({"type": "done"})
        streams.pop(job_id, None)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/review", response_model=ReviewResponse)
@limiter.limit("5/hour")
async def start_review(
    request: Request,
    review_request: ReviewRequest,
    background_tasks: BackgroundTasks
):
    if not review_request.repo_url.startswith("https://github.com/"):
        raise HTTPException(
            status_code=400,
            detail="URL must be a valid public GitHub repository URL."
        )

    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "job_id": job_id,
        "repo_url": review_request.repo_url,
        "status": "queued",
        "created_at": time.time(),
        "result": None,
        "error": None
    }

    # Create SSE queue before starting background task
    streams[job_id] = queue.Queue()

    background_tasks.add_task(
        run_review_job,
        job_id,
        review_request.repo_url,
        review_request.github_token or ""
    )

    return ReviewResponse(
        job_id=job_id,
        message="Review started. Connect to /api/stream/{job_id} for real-time events."
    )


@app.get("/api/stream/{job_id}")
async def stream_review(job_id: str, request: Request):
    """
    SSE endpoint — streams agent progress events in real time.
    Events: agent_complete | complete | error | done
    Falls back gracefully if job already finished before client connected.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    async def event_generator():
        loop = asyncio.get_event_loop()
        q = streams.get(job_id)

        if q is None:
            # Job already finished before client connected
            # Send final state immediately
            job = jobs.get(job_id, {})
            if job.get("status") == "complete":
                yield {"data": json.dumps({
                    "type": "complete",
                    "result": job["result"]
                })}
            elif job.get("status") == "error":
                yield {"data": json.dumps({
                    "type": "error",
                    "error": job.get("error", "Unknown error")
                })}
            yield {"data": json.dumps({"type": "done"})}
            return

        while True:
            # Check client disconnected
            if await request.is_disconnected():
                break

            try:
                # Read from thread-safe queue without blocking the async event loop
                event = await loop.run_in_executor(
                    None, q.get, True, 1.0  # blocking=True, timeout=1s
                )
                yield {"data": json.dumps(event)}

                # Close stream after sentinel
                if event.get("type") == "done":
                    break

            except queue.Empty:
                # No event in 1 second — send keep-alive so connection stays open
                yield {"comment": "keep-alive"}

    return EventSourceResponse(event_generator())


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """
    Polling fallback endpoint — unchanged.
    Works for clients that don't support SSE.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs[job_id]
    response = {
        "job_id": job_id,
        "status": job["status"],
        "repo_url": job["repo_url"]
    }

    if job["status"] == "complete":
        response["result"] = job["result"]
    elif job["status"] == "error":
        response["error"] = job.get("error", "Unknown error")

    return response


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "agents": 5,
        "active_jobs": len([j for j in jobs.values() if j["status"] == "running"]),
        "total_reviews": len(jobs),
        "streaming": "sse"
    }


@app.get("/")
async def serve_frontend():
    frontend_path = "../frontend/index.html"
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "CodeSensei API v1.0 — 5 agents ready."}