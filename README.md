<div align="center">

<img src="https://img.shields.io/badge/CodeSensei-AI%20Code%20Review-00e5ff?style=for-the-badge&logo=github&logoColor=white" alt="CodeSensei"/>

# 🧠 CodeSensei — AI Code Review Agent

### *Review any GitHub repository like a senior engineer. In under 90 seconds.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1-FF6B35?style=flat-square&logo=chainlink&logoColor=white)](https://langchain-ai.github.io/langgraph)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-E75480?style=flat-square&logo=databricks&logoColor=white)](https://trychroma.com)
[![Groq](https://img.shields.io/badge/Groq-Llama3-F55036?style=flat-square&logo=meta&logoColor=white)](https://groq.com)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Transformers-FFD21E?style=flat-square&logo=huggingface&logoColor=black)](https://huggingface.co)
[![License](https://img.shields.io/badge/License-MIT-00f0a0?style=flat-square)](LICENSE)

<br/>

**Paste any public GitHub URL.**
**5 autonomous AI agents review the entire codebase — bugs, security, architecture, quality.**
**Get exact file names, line numbers, and fixes. Free. No GPU needed.**

<br/>

[🚀 Quick Start](#-quick-start) · [📊 Demo Results](#-demo-results) · [🤖 How It Works](#-how-it-works) · [🏗️ Architecture](#️-architecture) · [👤 Built By](#-built-by)

</div>

---

<!-- ============================================================ -->
<!-- SCREENSHOT 1 — PASTE YOUR SCORE DASHBOARD IMAGE HERE        -->
<!-- Save as: assets/dashboard.png                               -->
<!-- This is the dark theme dashboard showing 89/100, 148 files  -->
<!-- It is the FIRST thing visitors see — most important image   -->
<!-- ============================================================ -->

<div align="center">

![CodeSensei Score Dashboard](assets/dashboard.png)

*CodeSensei reviewing Textualize/rich — 148 files, 826 chunks, 171 seconds*

</div>

---

## 📊 Demo Results

> Tested on real production repos used by millions of developers worldwide.
> These are not cherry-picked results — run it yourself and see.

| Repo | Stars | Score | Critical Bugs | Key Finding |
|------|-------|-------|---------------|-------------|
| `pallets/flask` | 67K ⭐ | 27/100 🔴 | 5 | Monolithic structure, tight coupling |
| `Textualize/rich` | 56K ⭐ | 78/100 🟡 | 1 | Security vulnerability in `traceback.py` line 353 |
| `psf/requests` | 52K ⭐ | 100/100 🟢 | 0 | One of the cleanest Python codebases ever reviewed |

<!-- ============================================================ -->
<!-- SCREENSHOT 2 — PASTE YOUR BUG REPORT IMAGE HERE            -->
<!-- Save as: assets/bugs.png                                    -->
<!-- This is the image showing HIGH/MEDIUM bugs in traceback.py  -->
<!-- Place it right after the demo results table                 -->
<!-- ============================================================ -->

<div align="center">

![Security vulnerability found in Textualize/rich](assets/bugs.png)

*Real security vulnerability detected — `rich/traceback.py` line 353 — with exact fix*

</div>

<!-- ============================================================ -->
<!-- SCREENSHOT 3 — PASTE YOUR ARCHITECTURE IMAGE HERE          -->
<!-- Save as: assets/architecture.png                           -->
<!-- This shows DESIGN/COUPLING/COMPLEXITY/MAINTAINABILITY tags  -->
<!-- Place it right after screenshot 2                          -->
<!-- ============================================================ -->

<div align="center">

![Architecture issues found in Textualize/rich](assets/architecture.png)

*Architecture analysis — God Object, Tight Coupling, High Complexity, Magic Numbers — all in one file*

</div>

---

## ⚡ What Problem Does This Solve

ChatGPT and Gemini can review code — but they have a **context window limit**.

A real production repo has millions of tokens across hundreds of files. You cannot paste that into any LLM. You can only show it a tiny slice and hope it finds something.

**CodeSensei solves this with RAG over code.**

It embeds every function and class into ChromaDB using sentence embeddings, then uses semantic search to find the riskiest chunks and sends only those to the LLM. The LLM never sees more than 1,500 tokens at once — but reviews the **entire codebase**.

This is how real production AI systems work. Not one big prompt. Intelligent retrieval.

---

## 🤖 How It Works

```
GitHub URL
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                  LangGraph Orchestrator                  │
│                                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │Agent 01 │→ │Agent 02 │→ │Agent 03 │→ │Agent 04 │→ │Agent 05 │ │
│  │ Ingest  │  │  Bugs   │  │  Arch   │  │ Quality │  │ Report  │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────┘
         │                   │                   │
         ▼                   ▼                   ▼
    ChromaDB             Groq LLM          Markdown Report
   (vector store)      (Llama 3 70B)        + Score /100
```

| Agent | Job | Tech used |
|-------|-----|-----------|
| **01 — Repo Ingestion** | Fetches all files via GitHub API, chunks by function/class boundary, embeds into ChromaDB | GitHub API · HuggingFace · ChromaDB |
| **02 — Bug Hunter** | Queries vector store for risky patterns, sends suspicious chunks to LLM, extracts structured bugs with severity and line numbers | ChromaDB · LangChain · Groq |
| **03 — Architecture** | Detects God Objects, tight coupling, high complexity, magic numbers, missing abstractions | ChromaDB · LangChain · Groq |
| **04 — Code Quality** | Measures documentation coverage, type hint coverage, test file ratio, readability score | Regex · Groq |
| **05 — Report** | Synthesises all findings into a scored markdown report with executive summary and concrete fixes | Groq · LangGraph |

---

## 🚀 Quick Start

### What you need
- Python 3.11+
- Free [Groq API key](https://console.groq.com) — 2 minutes to get
- Free [GitHub token](https://github.com/settings/tokens) — read:public_repo scope only

### 1. Clone

```bash
git clone https://github.com/NikhilPa/codesensei
cd codesensei/backend
```

### 2. Install

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### 3. Add your keys

```bash
cp .env.example .env
```

Open `.env` and add:

```env
GROQ_API_KEY=gsk_your_key_here
GITHUB_TOKEN=ghp_your_token_here
CHROMA_PERSIST_DIR=./chroma_db
MAX_FILES_PER_REPO=150
```

### 4. Run

```bash
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` — paste any public GitHub URL — hit Review.

### 🎯 Try these repos first

| Repo | Why it's interesting |
|------|---------------------|
| `Textualize/rich` | Has a real security finding in traceback.py |
| `pallets/flask` | Surprisingly low score — see why |
| `psf/requests` | Perfect 100/100 — understand what clean code looks like |
| **your own repo** | The most honest feedback you will ever get |

---

## 🏗️ Architecture

```
codesensei/
├── backend/
│   ├── main.py                     # FastAPI — async REST API with background jobs
│   ├── agents/
│   │   ├── graph.py                # LangGraph StateGraph — orchestrates all 5 agents
│   │   ├── ingestion.py            # Agent 01 — GitHub fetch + embed pipeline
│   │   ├── bug_hunter.py           # Agent 02 — semantic bug detection
│   │   ├── architecture.py         # Agent 03 — structural analysis
│   │   ├── quality.py              # Agent 04 — code quality scoring
│   │   └── report.py               # Agent 05 — report synthesis
│   ├── vectorstore/
│   │   ├── embed.py                # HuggingFace sentence embeddings
│   │   └── store.py                # ChromaDB vector store operations
│   ├── utils/
│   │   ├── github_fetcher.py       # GitHub REST API client
│   │   └── chunker.py              # AST-based code chunker
│   └── requirements.txt
├── frontend/
│   └── index.html                  # Single-file dark theme UI
├── assets/
│   ├── dashboard.png               # Score dashboard screenshot
│   ├── bugs.png                    # Bug report screenshot
│   └── architecture.png            # Architecture issues screenshot
└── README.md
```

### Why these design decisions

**Why ChromaDB?**
Repos have hundreds of files. LLMs have small context windows. ChromaDB lets us embed the entire codebase and retrieve only the most semantically relevant chunks for each query — bugs, architecture, quality — separately. This is the core insight that makes CodeSensei work.

**Why async job tracking?**
Code review takes 60-170 seconds. Blocking the HTTP request would time out. The `/api/review` endpoint starts a background task and returns a `job_id` instantly. The frontend polls `/api/status/{job_id}` every 2 seconds. This is how production APIs are built.

**Why LangGraph?**
Each agent passes its output as typed state to the next. LangGraph's `StateGraph` handles this cleanly with conditional edges and graceful error handling per node. If one agent fails, the rest still run.

**Why Groq?**
Free tier with Llama 3 70B — a genuinely capable model. Fast enough for production demos. No GPU needed. One environment variable to switch to any other LLM.

---

## 🌐 Supported Languages

Python · JavaScript · TypeScript · Java · Go · C · C++ · C# · Ruby · PHP · Rust · Kotlin · Swift

---

## 🔌 API Reference

### Start a review

```bash
POST /api/review
Content-Type: application/json

{
  "repo_url": "https://github.com/Textualize/rich"
}
```

Response:
```json
{
  "job_id": "abc-123-def",
  "message": "Review started. Poll /api/status/{job_id} for progress."
}
```

### Poll for results

```bash
GET /api/status/{job_id}
```

Response when complete:
```json
{
  "status": "complete",
  "result": {
    "score": 78,
    "quality_score": 100,
    "critical_count": 1,
    "bug_count": 3,
    "file_count": 148,
    "chunks_analysed": 826,
    "bugs": [...],
    "arch_issues": [...],
    "quality": {
      "docstring_coverage": 68.2,
      "type_hint_coverage": 86.4,
      "test_coverage_ratio": 7.4,
      "avg_readability": 95
    },
    "report_markdown": "# CodeSensei Review...",
    "processing_time_sec": 171.3
  }
}
```

---

## 🛠️ Full Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Agent orchestration | LangGraph | Typed state, conditional edges, graceful failures |
| Vector store | ChromaDB | Semantic search across entire codebase |
| Embeddings | HuggingFace Transformers | Code-aware sentence embeddings, runs locally |
| LLM | Groq + Llama 3 70B | Free tier, fast, no GPU needed |
| LLM framework | LangChain | Prompt management and LLM interaction |
| Backend API | FastAPI | Async REST with background task processing |
| Code parsing | Python AST | Function and class boundary detection |
| GitHub access | GitHub REST API | File fetching from any public repository |
| Frontend | Vanilla HTML/CSS/JS | Single-file dark theme UI, no framework |

---

## 🔮 What's Next

- [ ] GitHub Actions integration — auto-review every PR before merge
- [ ] Private repo support with OAuth
- [ ] Side-by-side diff view with suggested fixes inline
- [ ] Historical score tracking — watch your codebase improve over time
- [ ] Slack and Discord bot integration

---

## 👤 Built By

**Nikhil Manoj Patil**

Final year AI/ML student from Dhule, Maharashtra.
No IIT. No research lab. Just built this in 7 days
using skills I already had.

If you're building something in Agentic AI or RAG
and want someone who ships — let's talk.

📧 nikhilpatil9263@gmail.com

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=flat-square&logo=linkedin&logoColor=white)](https://linkedin.com/in/nikhil-patil-2013a0282)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/NikhilPa)

---

<div align="center">

**If CodeSensei found something interesting in a repo you care about — drop a ⭐**

*Built in 7 days · LangGraph · RAG · ChromaDB · Groq · FastAPI*

</div>