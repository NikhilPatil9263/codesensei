import os
import json
from groq import Groq
from typing import Dict

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

REPORT_PROMPT = """You are a senior engineering lead writing a formal code review report.

Repository: {repo_name}
Stars: {stars}
Primary language: {language}
Files reviewed: {file_count}
Code chunks analysed: {chunk_count}

Bug findings ({bug_count} total):
{bugs_summary}

Architecture findings ({arch_count} total):
{arch_summary}

Write a professional senior engineer code review report in markdown.

Structure it exactly like this:

# CodeSensei Review — {repo_name}

## Executive summary
2-3 sentences summarising the overall code quality and the most important findings.

## Overall score
Score: {score}/100 — use exactly this score, do not invent a different number. Then write a one-line justification for this score.

## Critical bugs
List only the critical and high severity bugs. For each: filename, line number, issue, and a concrete fix with a code example.

## Architecture issues
List the top architecture problems found. For each: what the problem is, why it matters, and what to change.

## What this codebase does well
2-3 genuine positives. Be specific, not generic.

## Recommended next steps
A prioritised list of 3-5 concrete actions the team should take.

Be direct, specific, and professional. Use real file names and line numbers from the findings.
Do not pad with generic advice. Write like a senior engineer who has actually read this code.
IMPORTANT: The overall score is {score}/100 — do not change this number under any circumstances."""


def run_report_agent(state: Dict) -> Dict:
    state["status"] = "Agent 05 running: generating review report..."
    print("[Agent 05] Generating final report...")

    bugs = state.get("bugs", [])
    arch_issues = state.get("arch_issues", [])
    metadata = state.get("metadata", {})

    bugs_summary = format_bugs_for_prompt(bugs[:15])
    arch_summary = format_arch_for_prompt(arch_issues[:10])

    score = calculate_score(bugs, arch_issues)

    prompt = REPORT_PROMPT.format(
        repo_name=metadata.get("full_name", "Unknown Repo"),
        stars=metadata.get("stars", 0),
        language=metadata.get("language", "Unknown"),
        file_count=state.get("file_count", 0),
        chunk_count=state.get("chunk_count", 0),
        bug_count=len(bugs),
        bugs_summary=bugs_summary,
        arch_count=len(arch_issues),
        arch_summary=arch_summary,
        score=score
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000
        )
        report_markdown = response.choices[0].message.content.strip()

    except Exception as e:
        report_markdown = generate_fallback_report(state, bugs, arch_issues, metadata, score)
        print(f"[Agent 05] Used fallback report due to: {e}")

    state["report_markdown"] = report_markdown
    state["score"] = score
    state["critical_count"] = len([b for b in bugs if b.get("severity") == "critical"])
    state["high_count"] = len([b for b in bugs if b.get("severity") == "high"])
    state["status"] = "complete"

    print(f"[Agent 05] Report generated. Score: {score}/100")
    return state


def format_bugs_for_prompt(bugs: list) -> str:
    if not bugs:
        return "No bugs found."
    lines = []
    for b in bugs:
        lines.append(
            f"- [{b.get('severity','?').upper()}] {b.get('file','?')} "
            f"line ~{b.get('start_line','?')}: {b.get('issue','?')} — {b.get('description','')}"
        )
    return "\n".join(lines)


def format_arch_for_prompt(issues: list) -> str:
    if not issues:
        return "No architecture issues found."
    lines = []
    for i in issues:
        lines.append(
            f"- [{i.get('category','?').upper()}] {i.get('file','?')}: "
            f"{i.get('issue','?')} — {i.get('description','')}"
        )
    return "\n".join(lines)


def calculate_score(bugs: list, arch_issues: list) -> int:
    score = 100
    for bug in bugs:
        severity = bug.get("severity", "medium")
        if severity == "critical":
            score -= 12
        elif severity == "high":
            score -= 6
        elif severity == "medium":
            score -= 3
    score -= len(arch_issues) * 2
    return max(10, min(100, score))


def generate_fallback_report(state: Dict, bugs: list, arch_issues: list, metadata: Dict, score: int) -> str:
    repo = metadata.get("full_name", "Unknown")

    lines = [
        f"# CodeSensei Review — {repo}",
        "",
        "## Overall score",
        f"Score: {score}/100",
        "",
        f"**Files reviewed:** {state.get('file_count', 0)}  ",
        f"**Chunks analysed:** {state.get('chunk_count', 0)}",
        "",
        "## Bugs found",
    ]

    if bugs:
        for b in bugs[:10]:
            lines.append(
                f"- **[{b.get('severity','?').upper()}]** `{b.get('file','?')}` "
                f"line ~{b.get('start_line','?')}: {b.get('issue','?')}"
            )
            lines.append(f"  > {b.get('description','')}")
            lines.append(f"  **Fix:** {b.get('fix','')}")
            lines.append("")
    else:
        lines.append("No bugs detected in analysed chunks.")

    lines += ["", "## Architecture issues"]

    if arch_issues:
        for i in arch_issues[:8]:
            lines.append(f"- **[{i.get('category','?').upper()}]** `{i.get('file','?')}`: {i.get('issue','?')}")
            lines.append(f"  > {i.get('description','')}")
            lines.append(f"  **Recommendation:** {i.get('recommendation','')}")
            lines.append("")
    else:
        lines.append("No major architecture issues detected.")

    return "\n".join(lines)