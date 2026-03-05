from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


IGNORED_DIRS = {
    ".git",
    "vendor",
    "node_modules",
    "storage",
    "bootstrap/cache",
    "dist",
    "build",
    "coverage",
    ".idea",
    ".vscode",
}

LANG_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".php": "php",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".json": "json",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".html": "html",
    ".css": "css",
    ".sh": "shell",
    ".ps1": "powershell",
}


@dataclass
class Chunk:
    path: str
    start_line: int
    end_line: int
    language: str
    chunk_hash: str
    file_mtime: float
    content: str


def detect_language(path: Path) -> str:
    return LANG_BY_SUFFIX.get(path.suffix.lower(), "text")


def chunk_text(
    content: str,
    path: str,
    file_mtime: float,
    chunk_lines: int | None = None,
    overlap_lines: int | None = None,
) -> list[Chunk]:
    chunk_lines = chunk_lines or settings.chunk_lines
    overlap_lines = overlap_lines or settings.chunk_overlap_lines
    lines = content.splitlines()
    if not lines:
        return []

    out: list[Chunk] = []
    step = max(1, chunk_lines - overlap_lines)
    line_idx = 0
    language = detect_language(Path(path))

    while line_idx < len(lines):
        end = min(len(lines), line_idx + chunk_lines)
        current_lines = lines[line_idx:end]
        text = "\n".join(current_lines)
        key = f"{path}:{line_idx + 1}:{end}:{text}".encode("utf-8")
        out.append(
            Chunk(
                path=path,
                start_line=line_idx + 1,
                end_line=end,
                language=language,
                chunk_hash=hashlib.sha1(key).hexdigest(),
                file_mtime=file_mtime,
                content=text,
            )
        )
        if end >= len(lines):
            break
        line_idx += step

    return out