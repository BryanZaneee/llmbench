"""Self-contained HTML gallery: side-by-side model outputs per prompt.

Shows text completions, generated images, and quality scores in one page so a
human can scroll through and compare models for the same prompt.
"""

from __future__ import annotations

import html
import os
from collections import defaultdict
from pathlib import Path

from ..schema import BenchmarkResult, RunManifest


CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #0f0f12; color: #e6e6e6; margin: 0; padding: 24px; }
h1 { margin: 0 0 4px; font-size: 20px; }
.meta { color: #888; font-size: 13px; margin-bottom: 32px; }
.prompt-section { margin-bottom: 48px; border-top: 1px solid #2a2a30; padding-top: 24px; }
.prompt-text { background: #1a1a20; border-left: 3px solid #5566ff; padding: 12px 16px;
               border-radius: 4px; margin-bottom: 16px; white-space: pre-wrap; font-size: 14px; }
.prompt-id { color: #5566ff; font-weight: 600; margin-right: 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 16px; }
.card { background: #17171d; border: 1px solid #2a2a30; border-radius: 6px; padding: 14px;
        display: flex; flex-direction: column; }
.card h3 { margin: 0 0 8px; font-size: 14px; color: #c8c8d0; }
.stats { font-size: 12px; color: #888; margin-bottom: 10px; }
.stats span { margin-right: 12px; }
.stats .score { color: #77dd77; font-weight: 600; }
.stats .score.low { color: #ff7777; }
.output { background: #0b0b0f; border-radius: 4px; padding: 10px;
          font-family: "SF Mono", Menlo, monospace; font-size: 12px;
          white-space: pre-wrap; max-height: 320px; overflow: auto;
          color: #d4d4d8; }
.img-card img { max-width: 100%; border-radius: 4px; display: block; }
.reasoning { margin-top: 8px; font-size: 12px; color: #aaa; font-style: italic; }
.error { color: #ff7777; font-size: 12px; padding: 10px; background: #1a0f0f; border-radius: 4px; }
.summary { background: #17171d; border: 1px solid #2a2a30; border-radius: 6px;
           padding: 16px; margin-bottom: 32px; }
.summary table { width: 100%; border-collapse: collapse; font-size: 13px; }
.summary th, .summary td { text-align: left; padding: 6px 12px; border-bottom: 1px solid #2a2a30; }
.summary th { color: #888; font-weight: 500; }
"""


def _rel(path: str, base: Path) -> str:
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return path


def _fmt(n: float | int | None, decimals: int = 1) -> str:
    if n is None:
        return "—"
    if isinstance(n, int) or decimals == 0:
        return f"{int(n)}"
    return f"{n:.{decimals}f}"


def _stats_line(r: BenchmarkResult) -> str:
    parts = []
    if r.throughput:
        if r.throughput.ttft_ms:
            parts.append(f'<span>TTFT {_fmt(r.throughput.ttft_ms, 0)} ms</span>')
        if r.throughput.tokens_per_second:
            parts.append(f'<span>{_fmt(r.throughput.tokens_per_second)} tok/s</span>')
    if r.score is not None:
        cls = "score" if r.score >= 5 else "score low"
        parts.append(f'<span class="{cls}">score {_fmt(r.score, 1)}</span>')
    parts.append(f'<span>{_fmt(r.duration_ms, 0)} ms</span>')
    if r.usage.output_tokens:
        parts.append(f'<span>{r.usage.output_tokens} out tok</span>')
    return "".join(parts)


def _card_html(r: BenchmarkResult, base_dir: Path) -> str:
    head = f"<h3>{html.escape(r.model.display)} · {html.escape(r.benchmark)}</h3>"
    stats = f'<div class="stats">{_stats_line(r)}</div>'
    if not r.success:
        body = f'<div class="error">{html.escape(r.error or "failed")}</div>'
        return f'<div class="card">{head}{stats}{body}</div>'

    body_parts: list[str] = []
    for img_path in r.image_paths:
        body_parts.append(f'<div class="img-card"><img src="{_rel(img_path, base_dir)}" /></div>')
    if r.sample_output:
        body_parts.append(f'<div class="output">{html.escape(r.sample_output)}</div>')
    if r.score_reasoning:
        body_parts.append(f'<div class="reasoning">{html.escape(r.score_reasoning)}</div>')
    return f'<div class="card">{head}{stats}{"".join(body_parts)}</div>'


def _summary_table(results: list[BenchmarkResult]) -> str:
    rows: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: {"tok_s": [], "ttft": [], "score": []}
    )
    for r in results:
        if not r.success:
            continue
        key = (r.model.display, r.benchmark)
        if r.throughput and r.throughput.tokens_per_second:
            rows[key]["tok_s"].append(r.throughput.tokens_per_second)
        if r.throughput and r.throughput.ttft_ms:
            rows[key]["ttft"].append(r.throughput.ttft_ms)
        if r.score is not None:
            rows[key]["score"].append(r.score)

    def avg(xs: list[float]) -> str:
        return _fmt(sum(xs) / len(xs)) if xs else "—"

    body = "".join(
        f"<tr><td>{html.escape(m)}</td><td>{html.escape(b)}</td>"
        f"<td>{avg(v['tok_s'])}</td><td>{avg(v['ttft'])}</td>"
        f"<td>{avg(v['score'])}</td></tr>"
        for (m, b), v in sorted(rows.items())
    )
    return f"""
    <div class="summary">
      <table>
        <tr><th>Model</th><th>Benchmark</th><th>Avg tok/s</th><th>Avg TTFT ms</th><th>Avg score</th></tr>
        {body}
      </table>
    </div>
    """


def render_gallery(
    manifest: RunManifest, results: list[BenchmarkResult], out_path: Path
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base_dir = out_path.parent

    by_prompt: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for r in results:
        if r.prompt_id:
            by_prompt[r.prompt_id].append(r)

    prompt_text_by_id = {p.id: p.prompt for p in manifest.prompts}

    sections: list[str] = []
    for prompt_id, group in by_prompt.items():
        prompt_text = prompt_text_by_id.get(prompt_id, "")
        prompt_line = (
            f'<div class="prompt-text"><span class="prompt-id">{html.escape(prompt_id)}</span>'
            f"{html.escape(prompt_text)}</div>"
        )
        first_per_cell: dict[tuple[str, str], BenchmarkResult] = {}
        for r in group:
            key = (r.model.display, r.benchmark)
            if key not in first_per_cell or r.metadata.get("repetition", 0) == 0:
                first_per_cell[key] = r
        cards = "".join(_card_html(r, base_dir) for r in first_per_cell.values())
        sections.append(
            f'<section class="prompt-section">{prompt_line}'
            f'<div class="grid">{cards}</div></section>'
        )

    head = (
        f"<h1>ai-eval-suite — run {html.escape(manifest.run_id[:12])}</h1>"
        f'<div class="meta">{html.escape(manifest.created_at.isoformat(timespec="seconds"))} · '
        f"{len(manifest.models)} models · {len(manifest.benchmarks)} benchmarks · "
        f"{len(results)} results</div>"
    )
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>ai-eval run {manifest.run_id[:8]}</title>"
        f"<style>{CSS}</style></head><body>"
        f"{head}{_summary_table(results)}{''.join(sections)}"
        "</body></html>"
    )
    out_path.write_text(page)
    return out_path
