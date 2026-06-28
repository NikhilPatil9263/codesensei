from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Optional
from agents.ingestion import run_ingestion_agent
from agents.bug_hunter import run_bug_hunter_agent
from agents.architecture import run_architecture_agent
from agents.quality import run_quality_agent
from agents.report import run_report_agent


class ReviewState(TypedDict):
    repo_url: str
    github_token: Optional[str]
    status: str
    metadata: Optional[Dict]
    file_count: Optional[int]
    chunk_count: Optional[int]
    collection_name: Optional[str]
    file_paths: Optional[List[str]]
    bugs: Optional[List[Dict]]
    arch_issues: Optional[List[Dict]]
    quality: Optional[Dict]
    report_markdown: Optional[str]
    score: Optional[int]
    critical_count: Optional[int]
    high_count: Optional[int]
    error: Optional[str]


def safe_ingestion(state: ReviewState) -> ReviewState:
    try:
        return run_ingestion_agent(state)
    except Exception as e:
        state["error"] = f"Ingestion failed: {str(e)}"
        state["status"] = "error"
        return state


def safe_bug_hunter(state: ReviewState) -> ReviewState:
    if state.get("error"): return state
    try:
        return run_bug_hunter_agent(state)
    except Exception as e:
        print(f"[Agent 02] Error (non-fatal): {e}")
        state["bugs"] = []
        return state


def safe_architecture(state: ReviewState) -> ReviewState:
    if state.get("error"): return state
    try:
        return run_architecture_agent(state)
    except Exception as e:
        print(f"[Agent 03] Error (non-fatal): {e}")
        state["arch_issues"] = []
        return state


def safe_quality(state: ReviewState) -> ReviewState:
    if state.get("error"): return state
    try:
        return run_quality_agent(state)
    except Exception as e:
        print(f"[Agent 05] Error (non-fatal): {e}")
        state["quality"] = {"quality_score": 0}
        return state


def safe_report(state: ReviewState) -> ReviewState:
    if state.get("error"): return state
    try:
        return run_report_agent(state)
    except Exception as e:
        state["error"] = f"Report generation failed: {str(e)}"
        state["status"] = "error"
        return state


def should_continue(state: ReviewState) -> str:
    if state.get("error"):
        return END
    return "continue"


def build_review_graph():
    graph = StateGraph(ReviewState)

    graph.add_node("ingest", safe_ingestion)
    graph.add_node("bug_hunt", safe_bug_hunter)
    graph.add_node("arch_review", safe_architecture)
    graph.add_node("quality_check", safe_quality)
    graph.add_node("report", safe_report)

    graph.set_entry_point("ingest")

    graph.add_conditional_edges(
        "ingest",
        should_continue,
        {"continue": "bug_hunt", END: END}
    )
    graph.add_edge("bug_hunt", "arch_review")
    graph.add_edge("arch_review", "quality_check")
    graph.add_edge("quality_check", "report")
    graph.add_edge("report", END)

    return graph.compile()


review_graph = build_review_graph()


def run_review(repo_url: str, github_token: str = "") -> Dict:
    initial_state: ReviewState = {
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
    final_state = review_graph.invoke(initial_state)
    return final_state