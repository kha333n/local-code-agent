from __future__ import annotations

from pathlib import Path

from app.services.chunker import chunk_text


def test_chunker_overlap_and_bounds(tmp_path: Path):
    file_path = tmp_path / "sample.py"
    lines = [f"line {i}" for i in range(1, 121)]
    file_path.write_text("\n".join(lines), encoding="utf-8")

    chunks = chunk_text(file_path.read_text(encoding="utf-8"), "sample.py", 1000.0, chunk_lines=40, overlap_lines=10)

    assert len(chunks) >= 3
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 40
    assert chunks[1].start_line == 31
    assert chunks[1].end_line == 70
    assert chunks[-1].end_line == 120