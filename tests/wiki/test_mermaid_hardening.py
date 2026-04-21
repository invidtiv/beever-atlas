"""Tests for mermaid sanitization additions targeting v10 render failures.

- `--x|label|` / `--o|label|` → `-->|label|` (mermaid 11.x rejects pipe
  labels on cross/circle arrow endings).
- Dots and slashes inside `[label]` are stripped (e.g. `app.example.com`,
  `CI/CD pipeline`).
"""

from beever_atlas.wiki.compiler import WikiCompiler


def _run(raw: str) -> str:
    return WikiCompiler._postprocess_content(raw)


def test_cross_arrow_pipe_label_normalized():
    src = "```mermaid\ngraph TD\nA[Node A] --x|poor performance| B[Node B]\n```\n"
    out = _run(src)
    assert "--x|" not in out
    assert "A[Node A] -->|poor performance| B[Node B]" in out


def test_circle_arrow_pipe_label_normalized():
    src = "```mermaid\ngraph TD\nA[Node] --o|rel| B[Other]\n```\n"
    out = _run(src)
    assert "--o|" not in out
    assert "-->|rel|" in out


def test_label_dots_stripped():
    src = "```mermaid\ngraph TD\nSA[app.example.com] -->|uses| X[X]\n```\n"
    out = _run(src)
    assert "app.example.com" not in out
    assert "app example com" in out


def test_label_slashes_stripped():
    src = "```mermaid\ngraph TD\nCI[CI/CD pipeline] -->|deploys| P[Prod]\n```\n"
    out = _run(src)
    assert "CI/CD" not in out
    assert "CI CD pipeline" in out


def test_sanitizer_does_not_break_clean_blocks():
    src = (
        "```mermaid\ngraph TD\n"
        "TC[Thomas] -->|uses| B[Beever]\n"
        "B -->|features| CG[Context Graphs]\n"
        "```\n"
    )
    out = _run(src)
    assert "TC[Thomas] -->|uses| B[Beever]" in out
    assert "B -->|features| CG[Context Graphs]" in out
