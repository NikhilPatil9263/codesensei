import os
import uuid
import time
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict
from agents.graph import run_review

app = FastAPI(
    title="CodeSensei API",
    description="AI-powered GitHub repo code review using 5 autonomous agents",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

jobs: Dict[str, Dict] = {}


class ReviewRequest(BaseModel):
    repo_url: str
    github_token: Optional[str] = ""


class ReviewResponse(BaseModel):
    job_id: str
    message: str


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
            "processing_time_sec": round(time.time() - jobs[job_id]["started_at"], 1)
        }

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.post("/api/review", response_model=ReviewResponse)
async def start_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    if not request.repo_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="URL must be a valid GitHub repository URL.")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "repo_url": request.repo_url,
        "status": "queued",
        "created_at": time.time(),
        "result": None,
        "error": None
    }

    background_tasks.add_task(
        run_review_job,
        job_id,
        request.repo_url,
        request.github_token or ""
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
        "active_jobs": len([j for j in jobs.values() if j["status"] == "running"])
    }


@app.get("/")
async def serve_frontend():
    frontend_path = "../frontend/index.html"
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "CodeSensei API v2.0 — 5 agents running."}