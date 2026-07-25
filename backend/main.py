import os
import uuid
import time
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from typing import Optional, Dict
from agents.graph import run_review

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

jobs: Dict[str, Dict] = {}


# ── Preload model at startup ───────────────────────────────────────────────────
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


# ── Background job ────────────────────────────────────────────────────────────
def run_review_job(job_id: str, repo_url: str, github_token: str):
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = time.time()

    try:
        result = run_review(repo_url, github_token)

        if result.get("error"):
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = result["error"]
            return

        quality = result.get("quality") or {}

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["result"] = {
            "repo": result.get("metadata", {}),
            "score": result.get("score", 0),
            "quality_score": quality.get("quality_score", 0),
            "file_count": result.get("file_count", 0),
            "chunk_count": result.get("chunk_count", 0),
            "critical_count": result.get("critical_count", 0),
            "high_count": result.get("high_count", 0),
            "bug_count": len(result.get("bugs", [])),
            "arch_issue_count": len(result.get("arch_issues", [])),
            "bugs": result.get("bugs", []),
            "arch_issues": result.get("arch_issues", []),
            "quality": quality,
            "report_markdown": result.get("report_markdown", ""),
            "processing_time_sec": round(
                time.time() - jobs[job_id]["started_at"], 1
            )
        }

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


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

    background_tasks.add_task(
        run_review_job,
        job_id,
        review_request.repo_url,
        review_request.github_token or ""
    )

    return ReviewResponse(
        job_id=job_id,
        message="Review started. Poll /api/status/{job_id} for progress."
    )


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
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
        "total_reviews": len(jobs)
    }


@app.get("/")
async def serve_frontend():
    frontend_path = "../frontend/index.html"
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "CodeSensei API v1.0 — 5 agents ready."}
