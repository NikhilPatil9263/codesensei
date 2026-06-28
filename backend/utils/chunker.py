import ast
import re
from typing import List, Dict


MAX_CHUNK_LINES = 60
MIN_CHUNK_LINES = 5


def chunk_files(files: List[Dict]) -> List[Dict]:
    all_chunks = []
    for file in files:
        path = file["path"]
        content = file["content"]
        if path.endswith(".py"):
            chunks = chunk_python(path, content)
        else:
            chunks = chunk_generic(path, content)
        all_chunks.extend(chunks)
    return all_chunks


def chunk_python(path: str, content: str) -> List[Dict]:
    chunks = []
    try:
        tree = ast.parse(content)
        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", start + MAX_CHUNK_LINES)
                chunk_lines = lines[start:end]

                if len(chunk_lines) < MIN_CHUNK_LINES:
                    continue

                chunks.append({
                    "id": f"{path}::{node.name}::{start}",
                    "path": path,
                    "name": node.name,
                    "type": type(node).__name__,
                    "start_line": start + 1,
                    "end_line": end,
                    "code": "\n".join(chunk_lines),
                    "language": "python"
                })

        if not chunks:
            chunks = chunk_generic(path, content)

    except SyntaxError:
        chunks = chunk_generic(path, content)

    return chunks


def chunk_generic(path: str, content: str) -> List[Dict]:
    chunks = []
    lines = content.splitlines()

    func_pattern = re.compile(
        r"^\s*(async\s+)?(function\s+\w+|def\s+\w+|public\s+\w+|private\s+\w+|"
        r"protected\s+\w+|func\s+\w+|fn\s+\w+|sub\s+\w+)",
        re.IGNORECASE
    )

    boundaries = [0]
    for i, line in enumerate(lines):
        if func_pattern.match(line) and i > 0:
            boundaries.append(i)
    boundaries.append(len(lines))

    ext = path.split(".")[-1] if "." in path else "txt"

    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = min(boundaries[i + 1], start + MAX_CHUNK_LINES)
        chunk_lines = lines[start:end]

        if len(chunk_lines) < MIN_CHUNK_LINES:
            continue

        name = chunk_lines[0].strip()[:60] if chunk_lines else f"chunk_{i}"

        chunks.append({
            "id": f"{path}::chunk_{i}::{start}",
            "path": path,
            "name": name,
            "type": "function",
            "start_line": start + 1,
            "end_line": end,
            "code": "\n".join(chunk_lines),
            "language": ext
        })

    return chunks
