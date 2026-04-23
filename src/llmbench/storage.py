"""Persists results to SQLite (queryable) and JSONL (archival).

The `payload_json` column holds the full pydantic dump of each result, so new
benchmark fields never require a DB migration — the top-level columns are only
there to make common queries (filter by model, aggregate tok/s) fast.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .schema import BenchmarkResult, RunManifest


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    suite_version TEXT NOT NULL,
    manifest_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
    result_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    benchmark TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    started_at TEXT NOT NULL,
    success INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    ttft_ms REAL,
    tokens_per_second REAL,
    output_tokens INTEGER,
    input_tokens INTEGER,
    score REAL,
    error TEXT,
    payload_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_model ON results(provider, model);
"""


class Store:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def save_run(self, manifest: RunManifest, results: list[BenchmarkResult]) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO runs
               (run_id, created_at, suite_version, manifest_json)
               VALUES (:run_id, :created_at, :suite_version, :manifest_json)""",
            {
                "run_id": manifest.run_id,
                "created_at": manifest.created_at.isoformat(),
                "suite_version": manifest.suite_version,
                "manifest_json": manifest.model_dump_json(),
            },
        )
        for r in results:
            cur.execute(
                """INSERT OR REPLACE INTO results (
                    result_id, run_id, benchmark, provider, model, started_at,
                    success, duration_ms, ttft_ms, tokens_per_second,
                    output_tokens, input_tokens, score, error, payload_json
                ) VALUES (
                    :result_id, :run_id, :benchmark, :provider, :model, :started_at,
                    :success, :duration_ms, :ttft_ms, :tokens_per_second,
                    :output_tokens, :input_tokens, :score, :error, :payload_json
                )""",
                {
                    "result_id": r.run_id,
                    "run_id": manifest.run_id,
                    "benchmark": r.benchmark,
                    "provider": r.model.provider,
                    "model": r.model.model,
                    "started_at": r.started_at.isoformat(),
                    "success": 1 if r.success else 0,
                    "duration_ms": r.duration_ms,
                    "ttft_ms": r.throughput.ttft_ms if r.throughput else None,
                    "tokens_per_second": (
                        r.throughput.tokens_per_second if r.throughput else None
                    ),
                    "output_tokens": r.usage.output_tokens,
                    "input_tokens": r.usage.input_tokens,
                    "score": r.score,
                    "error": r.error,
                    "payload_json": r.model_dump_json(),
                },
            )
        self._conn.commit()

    def load_run(self, run_id: str) -> tuple[RunManifest, list[BenchmarkResult]]:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT manifest_json FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"run {run_id!r} not found")
        manifest = RunManifest.model_validate_json(row[0])
        rows = cur.execute(
            "SELECT payload_json FROM results WHERE run_id = ? ORDER BY started_at",
            (run_id,),
        ).fetchall()
        results = [BenchmarkResult.model_validate_json(r[0]) for r in rows]
        return manifest, results

    def latest_run_id(self) -> str | None:
        row = self._conn.execute(
            "SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def close(self) -> None:
        self._conn.close()


def write_jsonl(results: list[BenchmarkResult], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        for r in results:
            f.write(json.dumps(r.model_dump(mode="json")) + "\n")
