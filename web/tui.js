// llmbench — interactive TUI clone.
// A faithful, navigable web mirror of src/llmbench/tui.py (questionary menu).
// Keyboard: ↑↓ to move cursor, Enter to descend, Esc / Backspace / q to back out.
// Click also works. The arrow-key handler only fires when the frame is focused
// so the page still scrolls normally otherwise.
//
// No deps; one render pass per state change. Screen objects are pure data.

(function () {
  "use strict";

  const SECTION_RULE_WIDTH = 69;

  // ─── Screen catalog ──────────────────────────────────────────────────────
  // Each screen has: optional question, optional instruction, an items list,
  // and optional panel/table/note/empty blocks rendered in order.
  // Items: { label, meta?, to?, action?, back?, section? }.
  // - to:     pushes that screen onto the stack
  // - action: a special verb ("main", "quit", "noop")
  // - back:   pops the stack
  // - section: renders a "── Label ──" separator (non-selectable)

  const SCREENS = {
    main: {
      breadcrumb: null,
      items: [
        { section: "Run" },
        { label: "Run agentic task", to: "task_pick" },
        { label: "Run benchmarks",   to: "bench_style" },
        { section: "Browse" },
        { label: "View LLM leaderboards",      to: "lb_source" },
        { label: "View past benchmark runs",   to: "past_runs" },
        { label: "View past task traces",      to: "past_traces" },
        { section: "Config" },
        { label: "Configure API keys", to: "config_keys" },
        { label: "Quit",               action: "quit" },
      ],
    },

    // ─── Run agentic task ────────────────────────────────────────────────
    task_pick: {
      breadcrumb: ["llmbench", "Run agentic task"],
      question: "Pick a task:",
      instruction: "(Use arrow keys, press Enter to select)",
      items: [
        { label: "file-refactor",       meta: "Rename a function across a 5-file mock project.",       to: "task_model" },
        { label: "api-orchestration",   meta: "GET → transform each row → POST audit with field rename.", to: "task_model" },
        { label: "multi-step-research", meta: "Synthesize 4 canned search results into a brief.",      to: "task_model" },
        { label: "recovery",            meta: "Retry a transient transactional failure.",              to: "task_model" },
        { label: "long-horizon",        meta: "Parse config, fetch sources, write a sectioned report.", to: "task_model" },
        { label: "Back", back: true },
      ],
    },
    task_model: {
      breadcrumb: ["llmbench", "Run agentic task", "Pick model"],
      question: "Pick a model:",
      instruction: "(pricing surfaced inline; cached input column omitted)",
      items: [
        { label: "anthropic/claude-opus-4-7",          meta: "$15/$75 per 1M in/out",   to: "task_confirm" },
        { label: "anthropic/claude-sonnet-4-6",        meta: "$3/$15 per 1M in/out",    to: "task_confirm" },
        { label: "anthropic/claude-haiku-4-5",         meta: "$0.8/$4 per 1M in/out",   to: "task_confirm" },
        { label: "openai/gpt-5",                       meta: "$1.25/$10 per 1M in/out", to: "task_confirm" },
        { label: "openai/gpt-4o",                      meta: "$2.5/$10 per 1M in/out",  to: "task_confirm" },
        { label: "openai/gpt-4o-mini",                 meta: "$0.15/$0.6 per 1M in/out", to: "task_confirm" },
        { label: "gemini/gemini-2.5-pro",              meta: "$1.25/$10 per 1M in/out", to: "task_confirm" },
        { label: "gemini/gemini-2.5-flash",            meta: "$0.3/$2.5 per 1M in/out", to: "task_confirm" },
        { label: "moonshot/kimi-k2-0905-preview",      meta: "$0.6/$2.5 per 1M in/out", to: "task_confirm" },
        { label: "Back", back: true },
      ],
    },
    task_confirm: {
      breadcrumb: ["llmbench", "Run agentic task", "Confirm"],
      panel: {
        title: "Run plan",
        rows: [
          { key: "task",     val: "file-refactor@1.0.0" },
          { key: "model",    val: "anthropic/claude-opus-4-7" },
          { key: "reps",     val: "1" },
          { key: "temp",     val: "0.0" },
          { key: "budget",   val: "max_steps=30" },
          { key: "trace",    val: "runs/<run_id>.json" },
        ],
      },
      note: "<strong>demo</strong> install llmbench and run <code>llmbench task file-refactor</code> to execute for real.",
      items: [
        { label: "Back to main menu", action: "main" },
      ],
    },

    // ─── Run benchmarks ──────────────────────────────────────────────────
    bench_style: {
      breadcrumb: ["llmbench", "Run benchmarks"],
      question: "How do you want to run?",
      items: [
        { label: "Build a custom run interactively", to: "bench_models" },
        { label: "Load a suite YAML file",           to: "bench_yaml" },
        { label: "CatBench",                         meta: "image_gen · suite.cat_bench.yaml", to: "bench_catbench" },
        { label: "Back",                             back: true },
      ],
    },
    bench_models: {
      breadcrumb: ["llmbench", "Run benchmarks", "Custom"],
      question: "Select models (space to toggle, enter to confirm):",
      instruction: "(showing preset model list; multi-select preview)",
      items: [
        { label: "Claude Opus 4.7",          meta: "[ ]", to: "bench_metrics" },
        { label: "Claude Sonnet 4.6",        meta: "[✓]", to: "bench_metrics" },
        { label: "Claude Haiku 4.5",         meta: "[ ]", to: "bench_metrics" },
        { label: "GPT-4o",                   meta: "[✓]", to: "bench_metrics" },
        { label: "GPT-4o mini",              meta: "[ ]", to: "bench_metrics" },
        { label: "GPT Image 1",              meta: "[ ] image_gen only", to: "bench_metrics" },
        { label: "Llama 3.2 (local Ollama)", meta: "[ ]", to: "bench_metrics" },
        { label: "Back", back: true },
      ],
    },
    bench_metrics: {
      breadcrumb: ["llmbench", "Run benchmarks", "Custom", "Benchmarks"],
      question: "Select benchmarks:",
      items: [
        { label: "throughput",     meta: "[✓]", to: "bench_confirm" },
        { label: "quality_exact",  meta: "[✓]", to: "bench_confirm" },
        { label: "quality_judge",  meta: "[ ]", to: "bench_confirm" },
        { label: "image_gen",      meta: "[ ]", to: "bench_confirm" },
        { label: "Back", back: true },
      ],
    },
    bench_yaml: {
      breadcrumb: ["llmbench", "Run benchmarks", "YAML"],
      input: { prompt: "Path to suite YAML:", value: "suite.example.yaml" },
      panel: {
        title: "Loaded suite (preview)",
        rows: [
          { key: "models",     val: "2 (claude-opus-4-7, gpt-4o-mini)" },
          { key: "benchmarks", val: "throughput, quality_exact, quality_judge" },
          { key: "reps",       val: "3" },
          { key: "concurrency", val: "2" },
          { key: "judge",      val: "anthropic/claude-opus-4-7" },
        ],
      },
      items: [
        { label: "Back", back: true },
      ],
    },
    bench_confirm: {
      breadcrumb: ["llmbench", "Run benchmarks", "Confirm"],
      panel: {
        title: "Suite plan",
        rows: [
          { key: "models",     val: "Claude Sonnet 4.6, GPT-4o" },
          { key: "benchmarks", val: "throughput, quality_exact" },
          { key: "reps",       val: "3" },
          { key: "open html",  val: "yes" },
        ],
      },
      note: "<strong>demo</strong> would write to <code>results/&lt;run_id&gt;/gallery.html</code> + <code>results.db</code>.",
      items: [
        { label: "Back to main menu", action: "main" },
      ],
    },

    // ─── CatBench (image_gen preset) ─────────────────────────────────────
    // One prompt, side-by-side gallery of pre-made runs from suite.cat_bench
    // .yaml, plus a bring-your-own-key generator that calls the provider
    // direct from the browser (Gemini works; OpenAI is CORS-blocked and
    // surfaces a hint to use the CLI).
    bench_catbench: {
      breadcrumb: ["llmbench", "Run benchmarks", "CatBench"],
      panel: {
        title: "Prompt",
        rows: [
          { key: "id",     val: "cat_bench" },
          { key: "prompt", val: "A photorealistic tabby cat playing with a ball of red yarn, natural window light." },
          { key: "metric", val: "image_gen · latency_ms · saved PNG" },
          { key: "suite",  val: "suite.cat_bench.yaml" },
        ],
      },
      gallery: { manifestUrl: "data/catbench/manifest.json" },
      byok: true,
      items: [
        { label: "Back",              back: true },
        { label: "Back to main menu", action: "main" },
      ],
    },

    // ─── Leaderboards ────────────────────────────────────────────────────
    lb_source: {
      breadcrumb: ["llmbench", "View LLM leaderboards"],
      question: "Pick a source:",
      items: [
        { label: "huggingface", meta: "Open LLM Leaderboard v2 (IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO)", to: "lb_view" },
        { label: "lmarena",     meta: "LMArena ELO from human preference voting",                          to: "lb_view" },
        { label: "aider",       meta: "Aider Polyglot — multi-language code-editing pass rate",            to: "lb_view" },
        { label: "bundled",     meta: "Snapshot shipped with llmbench (works offline)",                    to: "lb_view" },
        { label: "Back", back: true },
      ],
    },
    lb_view: {
      breadcrumb: ["llmbench", "View LLM leaderboards", "lmarena"],
      table: {
        title: "Leaderboard · lmarena (top 5)",
        headers: ["#", "Model", "Org", "ELO"],
        rows: [
          ["1", "claude-opus-4-7",      "Anthropic", "1421"],
          ["2", "gemini-2.5-pro",       "Google",    "1404"],
          ["3", "gpt-5",                "OpenAI",    "1397"],
          ["4", "claude-sonnet-4-6",    "Anthropic", "1372"],
          ["5", "deepseek-v3.5",        "DeepSeek",  "1359"],
        ],
        note: "fetched: cache (24h TTL) · 187 total entries",
      },
      items: [
        { label: "Back to sources", back: true },
        { label: "Back to main menu", action: "main" },
      ],
    },

    // ─── Past benchmark runs ─────────────────────────────────────────────
    past_runs: {
      breadcrumb: ["llmbench", "View past benchmark runs"],
      question: "Pick a run to view:",
      items: [
        { label: "9a192cf4e8d4  2026-04-27T19:42  (v1)", to: "past_runs_action" },
        { label: "16be27129b7b  2026-04-26T11:18  (v1)", to: "past_runs_action" },
        { label: "8c4f10d5a829  2026-04-25T22:03  (v1)", to: "past_runs_action" },
        { label: "Back", back: true },
      ],
    },
    past_runs_action: {
      breadcrumb: ["llmbench", "View past benchmark runs", "9a192cf4"],
      question: "What would you like to do?",
      items: [
        { label: "Open the gallery in browser",  to: "past_runs_open" },
        { label: "Print summary in terminal",    to: "past_runs_summary" },
        { label: "Back", back: true },
      ],
    },
    past_runs_open: {
      breadcrumb: ["llmbench", "View past benchmark runs", "9a192cf4", "Open"],
      note: "<strong>demo</strong> would open <code>results/9a192cf4e8d4…/gallery.html</code> in your default browser.",
      items: [
        { label: "Back", back: true },
      ],
    },
    past_runs_summary: {
      breadcrumb: ["llmbench", "View past benchmark runs", "9a192cf4", "Summary"],
      table: {
        title: "Benchmark Results",
        headers: ["Model", "Benchmark", "OK", "TTFT", "tok/s", "Score", "ms"],
        rows: [
          ["claude-sonnet-4-6", "throughput",    "OK", "412",  "78.3",  "—",   "1840"],
          ["claude-sonnet-4-6", "quality_exact", "OK", "—",    "—",     "1.0", "1102"],
          ["claude-sonnet-4-6", "quality_judge", "OK", "—",    "—",     "8.5", "1244"],
          ["gpt-4o",            "throughput",    "OK", "356",  "92.1",  "—",   "1610"],
          ["gpt-4o",            "quality_exact", "OK", "—",    "—",     "1.0", "880"],
          ["gpt-4o",            "quality_judge", "OK", "—",    "—",     "7.5", "1018"],
        ],
      },
      panel: {
        title: "Run details",
        rows: [
          { key: "run_id",     val: "9a192cf4e8d44601a849f6fc02653048" },
          { key: "created",    val: "2026-04-27T19:42:01Z" },
          { key: "models",     val: "Claude Sonnet 4.6, GPT-4o" },
          { key: "benchmarks", val: "throughput, quality_exact, quality_judge" },
        ],
      },
      items: [
        { label: "Back", back: true },
      ],
    },

    // ─── Past task traces ────────────────────────────────────────────────
    past_traces: {
      breadcrumb: ["llmbench", "View past task traces"],
      question: "Pick a trace:",
      items: [
        { label: "2026-04-28T03:12:44   file-refactor         success",      to: "trace_view_a" },
        { label: "2026-04-28T01:55:09   api-orchestration     success",      to: "trace_view_b" },
        { label: "2026-04-27T22:48:17   recovery              budget_exceeded", to: "trace_view_c" },
        { label: "Back", back: true },
      ],
    },
    trace_view_a: {
      breadcrumb: ["llmbench", "View past task traces", "file-refactor"],
      panel: {
        title: "Trace summary",
        rows: [
          { key: "task",    val: "file-refactor@1.0.0" },
          { key: "run_id",  val: "0e9c12a3b4f5..." },
          { key: "model",   val: "anthropic/claude-opus-4-7" },
          { key: "when",    val: "2026-04-28T03:12:44Z" },
          { key: "status",  val: "success", style: "success" },
          { key: "verdict", val: "passed",  style: "success" },
          { key: "flags",   val: "—" },
          { key: "totals",  val: "8420 in / 1102 out · 14 tool calls · cost $0.2087 · wall 41.2s" },
        ],
      },
      items: [
        { label: "Show 14 step(s) in detail?", to: "trace_steps_a" },
        { label: "Back", back: true },
      ],
    },
    trace_steps_a: {
      breadcrumb: ["llmbench", "View past task traces", "file-refactor", "Steps"],
      tree: {
        title: "Steps (14)",
        lines: [
          "step 1  [assistant]  812+102t  ·  3220ms",
          "  └ list_dir  (4ms)  {\"path\":\"\"}",
          "step 2  [assistant]  933+78t  ·  2410ms",
          "  └ read_file  (3ms)  {\"path\":\"src/ingest.py\"}",
          "step 3  [assistant]  1010+96t  ·  2570ms",
          "  └ read_file  (3ms)  {\"path\":\"src/pipeline.py\"}",
          "step 4  [assistant]  1180+184t  ·  2944ms",
          "  └ write_file  (5ms)  {\"path\":\"src/ingest.py\",\"content\":\"def transform_data(rows)…",
          "step 5  [assistant]  1270+212t  ·  3122ms",
          "  └ write_file  (5ms)  {\"path\":\"src/pipeline.py\"}",
          "  └ write_file  (4ms)  {\"path\":\"src/cli.py\"}",
          "  ⋮ (9 more steps elided)",
        ],
      },
      items: [
        { label: "Back", back: true },
      ],
    },
    trace_view_b: {
      breadcrumb: ["llmbench", "View past task traces", "api-orchestration"],
      panel: {
        title: "Trace summary",
        rows: [
          { key: "task",    val: "api-orchestration@1.0.0" },
          { key: "model",   val: "openai/gpt-4o" },
          { key: "status",  val: "success", style: "success" },
          { key: "verdict", val: "passed", style: "success" },
          { key: "flags",   val: "—" },
          { key: "totals",  val: "2210 in / 484 out · 4 tool calls · cost $0.0103 · wall 12.8s" },
        ],
      },
      items: [
        { label: "Back", back: true },
      ],
    },
    trace_view_c: {
      breadcrumb: ["llmbench", "View past task traces", "recovery"],
      panel: {
        title: "Trace summary",
        rows: [
          { key: "task",    val: "recovery@1.0.0" },
          { key: "model",   val: "moonshot/kimi-k2-0905-preview" },
          { key: "status",  val: "budget_exceeded", style: "warn" },
          { key: "verdict", val: "—" },
          { key: "flags",   val: "recovered_from_transient_failure" },
          { key: "totals",  val: "5430 in / 880 out · 11 tool calls · cost $0.0055 · wall 28.4s" },
        ],
      },
      items: [
        { label: "Back", back: true },
      ],
    },

    // ─── Configure API keys ──────────────────────────────────────────────
    config_keys: {
      breadcrumb: ["llmbench", "Configure API keys"],
      question: "Which key do you want to set?",
      items: [
        { label: "Anthropic",    meta: "[set]",     to: "config_set" },
        { label: "OpenAI",       meta: "[not set]", to: "config_set" },
        { label: "Gemini",       meta: "[not set]", to: "config_set" },
        { label: "Moonshot",     meta: "[not set]", to: "config_set" },
        { label: "Back", back: true },
      ],
    },
    config_set: {
      breadcrumb: ["llmbench", "Configure API keys", "Set"],
      input: { prompt: "OPENAI_API_KEY:", value: "••••••••••••••••" },
      note: "<strong>demo</strong> in the real TUI this is a password prompt; the value is written to <code>.env</code> and exported into the running process.",
      items: [
        { label: "Back", back: true },
      ],
    },

    // ─── Quit ────────────────────────────────────────────────────────────
    quit: {
      breadcrumb: ["llmbench", "Goodbye"],
      empty: "bye",
      note: "<strong>demo</strong> in the real TUI this exits the process. Click below to restart.",
      items: [
        { label: "Restart demo", action: "main" },
      ],
    },
  };

  // ─── Controller ──────────────────────────────────────────────────────────

  const frame   = document.getElementById("tui-frame");
  const screenEl = document.getElementById("tui-content");
  const focusStatusEl = document.getElementById("tui-focus-status");
  if (!frame || !screenEl) return;

  const state = {
    stack: ["main"],
    cursor: 0,
  };

  // ─── CatBench state ──────────────────────────────────────────────────────
  // Manifest is fetched once per page load; the BYOK form lives in memory only
  // (key never leaves the browser, never persisted).

  const MANIFEST_URL = "data/catbench/manifest.json";
  const CATBENCH_PROMPT =
    "A photorealistic tabby cat playing with a ball of red yarn, natural window light.";

  // Gemini's REST endpoint allows direct browser fetch (CORS open with key in
  // query). OpenAI's /v1/images/generations does not; calls fail with a CORS
  // error and the catch path surfaces a "use a backend proxy" hint.
  const BYOK_PROVIDERS = [
    {
      id: "gemini",
      label: "Google Gemini",
      keyHint: "AIza... · GEMINI_API_KEY",
      models: [
        { id: "imagen-3.0-generate-002", label: "Imagen 3", pricing: "~$0.04 / image (1024)" },
      ],
    },
    {
      id: "openai",
      label: "OpenAI",
      keyHint: "sk-... · OPENAI_API_KEY",
      models: [
        { id: "dall-e-3",    label: "DALL-E 3",     pricing: "~$0.04 / image (1024)" },
        { id: "gpt-image-1", label: "GPT Image 1",  pricing: "~$0.19 / image (1024)" },
      ],
    },
  ];

  const manifestCache = { status: "idle", data: null, error: null };

  const byok = {
    providerId: "gemini",
    apiKey: "",
    modelId: "imagen-3.0-generate-002",
    status: "idle", // idle | running | done | error
    error: null,
    result: null,   // { dataUrl, durationMs, model }
  };

  function byokProvider() {
    return BYOK_PROVIDERS.find((p) => p.id === byok.providerId) ?? BYOK_PROVIDERS[0];
  }

  async function ensureManifest() {
    if (manifestCache.status === "ok" || manifestCache.status === "loading") return;
    manifestCache.status = "loading";
    render();
    try {
      const r = await fetch(MANIFEST_URL, { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      manifestCache.data = await r.json();
      manifestCache.status = "ok";
    } catch (err) {
      manifestCache.error = String(err && err.message ? err.message : err);
      manifestCache.status = "error";
    }
    render();
  }

  // OpenAI: POST /v1/images/generations. Modern endpoints CORS-allow direct
  // browser calls when an Authorization bearer is supplied. dall-e-3 accepts
  // response_format=b64_json; gpt-image-1 always returns b64 and rejects that
  // parameter, so we omit it for gpt-image-1.
  async function openaiGenerate(apiKey, modelId, prompt) {
    const body = { model: modelId, prompt, n: 1, size: "1024x1024" };
    if (modelId === "dall-e-3") body.response_format = "b64_json";
    const r = await fetch("https://api.openai.com/v1/images/generations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + apiKey,
      },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      let detail = "HTTP " + r.status;
      try {
        const j = await r.json();
        if (j && j.error && j.error.message) detail += " · " + j.error.message;
      } catch (_) { /* swallow */ }
      throw new Error(detail);
    }
    const j = await r.json();
    const datum = j.data && j.data[0];
    if (!datum) throw new Error("empty response");
    if (datum.b64_json) return "data:image/png;base64," + datum.b64_json;
    if (datum.url) return datum.url;
    throw new Error("no image in response");
  }

  // Gemini Imagen 3 via the public generative-language REST endpoint. Key
  // goes in the URL query, not in the body or a header. CORS is open for
  // GET and POST with key.
  async function geminiGenerate(apiKey, modelId, prompt) {
    const url =
      "https://generativelanguage.googleapis.com/v1beta/models/" +
      encodeURIComponent(modelId) +
      ":predict?key=" + encodeURIComponent(apiKey);
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instances: [{ prompt }],
        parameters: { sampleCount: 1 },
      }),
    });
    if (!r.ok) {
      let detail = "HTTP " + r.status;
      try {
        const j = await r.json();
        if (j && j.error && j.error.message) detail += " · " + j.error.message;
      } catch (_) { /* swallow */ }
      throw new Error(detail);
    }
    const j = await r.json();
    const pred = j.predictions && j.predictions[0];
    if (!pred || !pred.bytesBase64Encoded) throw new Error("empty response");
    return "data:image/png;base64," + pred.bytesBase64Encoded;
  }

  async function runByok() {
    if (byok.status === "running") return;
    if (!byok.apiKey || !byok.apiKey.trim()) {
      byok.status = "error";
      byok.error = "API key required";
      render();
      return;
    }
    byok.status = "running";
    byok.error = null;
    byok.result = null;
    render();
    const start = performance.now();
    try {
      const fn = byok.providerId === "gemini" ? geminiGenerate : openaiGenerate;
      const dataUrl = await fn(byok.apiKey.trim(), byok.modelId, CATBENCH_PROMPT);
      byok.result = {
        dataUrl,
        durationMs: Math.round(performance.now() - start),
        model: byok.providerId + "/" + byok.modelId,
      };
      byok.status = "done";
    } catch (err) {
      const msg = err && err.message ? err.message : String(err);
      // Surface the most common failure modes as actionable hints.
      let hint = msg;
      if (/Failed to fetch|NetworkError|CORS/i.test(msg)) {
        hint = msg + "  ·  the provider may be blocking direct browser calls; a backend proxy is needed";
      }
      byok.error = hint;
      byok.status = "error";
    }
    render();
  }

  function ruleString(width) {
    return "─".repeat(width);
  }

  function sectionLabel(label) {
    const head = `── ${label} `;
    return head + "─".repeat(Math.max(0, SECTION_RULE_WIDTH - head.length));
  }

  function currentScreen() {
    return SCREENS[state.stack[state.stack.length - 1]];
  }

  function selectableIndices(screen) {
    const out = [];
    screen.items.forEach((item, i) => {
      if (!item.section) out.push(i);
    });
    return out;
  }

  function clamp(n, lo, hi) {
    return Math.max(lo, Math.min(hi, n));
  }

  // Find the first selectable index when a screen first opens. Bias toward
  // the first non-Back row (skip "Back" if there is anything else available).
  function defaultCursor(screen) {
    const idxs = selectableIndices(screen);
    for (const i of idxs) {
      if (!screen.items[i].back) return i;
    }
    return idxs[0] ?? 0;
  }

  function setCursor(targetIdx) {
    const screen = currentScreen();
    const idxs = selectableIndices(screen);
    if (idxs.length === 0) return;
    const pos = idxs.indexOf(targetIdx);
    if (pos === -1) return;
    state.cursor = targetIdx;
    render();
  }

  function moveCursor(delta) {
    const screen = currentScreen();
    const idxs = selectableIndices(screen);
    if (idxs.length === 0) return;
    const pos = idxs.indexOf(state.cursor);
    const nextPos = pos === -1
      ? 0
      : (pos + delta + idxs.length) % idxs.length;
    state.cursor = idxs[nextPos];
    render();
  }

  function activateAt(idx) {
    const screen = currentScreen();
    const item = screen.items[idx];
    if (!item || item.section) return;
    if (item.back) {
      pop();
      return;
    }
    if (item.action === "main") {
      state.stack = ["main"];
      state.cursor = defaultCursor(SCREENS.main);
      render();
      return;
    }
    if (item.action === "quit") {
      state.stack = ["quit"];
      state.cursor = defaultCursor(SCREENS.quit);
      render();
      return;
    }
    if (item.to) {
      state.stack.push(item.to);
      state.cursor = defaultCursor(SCREENS[item.to]);
      render();
    }
  }

  function pop() {
    if (state.stack.length <= 1) return;
    state.stack.pop();
    state.cursor = defaultCursor(currentScreen());
    render();
  }

  // ─── Render ──────────────────────────────────────────────────────────────

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function renderBreadcrumb(crumbs) {
    if (!crumbs || !crumbs.length) return null;
    const wrap = el("div", "tui-section-head");
    wrap.textContent = "── " + crumbs.join(" · ") + " " +
      "─".repeat(Math.max(0, SECTION_RULE_WIDTH - 4 - crumbs.join(" · ").length));
    return wrap;
  }

  function renderQuestion(text, instruction) {
    const wrap = document.createDocumentFragment();
    const q = el("div", "tui-question");
    q.appendChild(el("span", "tui-qmark", "?"));
    q.appendChild(el("span", "tui-question-text", text));
    wrap.appendChild(q);
    if (instruction) wrap.appendChild(el("div", "tui-instruction", instruction));
    return wrap;
  }

  function renderItem(item, idx, isSelected) {
    if (item.section) {
      const sec = el("div", "tui-section-head");
      sec.textContent = sectionLabel(item.section);
      return sec;
    }
    const row = el("div", "tui-row" + (item.back ? " is-back" : "") + (isSelected ? " is-selected" : ""));
    row.dataset.idx = String(idx);
    row.setAttribute("role", "button");
    row.setAttribute("tabindex", "-1");
    const pointer = el("span", "tui-row-pointer", isSelected ? "▸" : " ");
    pointer.setAttribute("aria-hidden", "true");
    row.appendChild(pointer);
    row.appendChild(el("span", "tui-row-label", item.label));
    if (item.meta) row.appendChild(el("span", "tui-row-meta", item.meta));
    row.addEventListener("mouseenter", () => setCursor(idx));
    row.addEventListener("click", (e) => {
      e.preventDefault();
      frame.focus();
      activateAt(idx);
    });
    return row;
  }

  function renderInput(input) {
    const row = el("div", "tui-input-row");
    row.appendChild(el("span", "tui-qmark", "?"));
    row.appendChild(el("span", "tui-question-text", input.prompt));
    const val = el("span", "tui-input-value", " " + input.value);
    row.appendChild(val);
    return row;
  }

  function renderPanel(panel) {
    const wrap = el("div", "tui-panel");
    wrap.appendChild(el("div", "tui-panel-title", "┌─ " + panel.title + " ─"));
    panel.rows.forEach((row) => {
      const r = el("div", "tui-panel-row");
      r.appendChild(el("span", "tui-panel-key", row.key));
      const valCls = "tui-panel-val" + (row.style ? " is-" + row.style : "");
      r.appendChild(el("span", valCls, row.val));
      wrap.appendChild(r);
    });
    return wrap;
  }

  function renderTable(table) {
    const wrap = el("div");
    if (table.title) wrap.appendChild(el("div", "tui-table-title", table.title));
    const t = el("table", "tui-table");
    const thead = el("thead");
    const trh = el("tr");
    table.headers.forEach((h, i) => {
      const th = el("th", i === 0 ? "tui-num" : null, h);
      trh.appendChild(th);
    });
    thead.appendChild(trh);
    t.appendChild(thead);
    const tbody = el("tbody");
    table.rows.forEach((row) => {
      const tr = el("tr");
      row.forEach((cell, i) => {
        tr.appendChild(el("td", i === 0 || i === row.length - 1 ? "tui-num" : null, cell));
      });
      tbody.appendChild(tr);
    });
    t.appendChild(tbody);
    wrap.appendChild(t);
    if (table.note) {
      const note = el("div", "tui-instruction", table.note);
      note.style.marginTop = "8px";
      note.style.marginLeft = "0";
      wrap.appendChild(note);
    }
    return wrap;
  }

  function renderTree(tree) {
    const wrap = el("div");
    wrap.appendChild(el("div", "tui-table-title", tree.title));
    const pre = el("pre");
    pre.style.margin = "0";
    pre.style.fontFamily = "var(--mono)";
    pre.style.fontSize = "12px";
    pre.style.lineHeight = "1.55";
    pre.style.color = "var(--term-fg-dim)";
    pre.style.whiteSpace = "pre-wrap";
    pre.textContent = tree.lines.join("\n");
    wrap.appendChild(pre);
    return wrap;
  }

  function renderNote(html) {
    const note = el("div", "tui-note");
    note.innerHTML = html;
    return note;
  }

  function renderEmpty(text) {
    return el("div", "tui-empty", text);
  }

  function fmtMs(ms) {
    if (ms == null) return "—";
    if (ms < 1000) return ms + " ms";
    return (ms / 1000).toFixed(1) + " s";
  }

  function fmtCost(usd) {
    if (usd == null) return "—";
    return "$" + Number(usd).toFixed(3);
  }

  function renderGallery(spec) {
    ensureManifest();
    const wrap = el("div", "tui-cb-gallery");
    wrap.appendChild(el("div", "tui-table-title", "┌─ CatBench gallery ─"));

    if (manifestCache.status === "loading" || manifestCache.status === "idle") {
      wrap.appendChild(el("div", "tui-cb-status", "loading manifest..."));
      return wrap;
    }
    if (manifestCache.status === "error") {
      const err = el("div", "tui-cb-status is-error");
      err.textContent = "could not load " + (spec && spec.manifestUrl) +
        " · " + manifestCache.error;
      wrap.appendChild(err);
      return wrap;
    }
    const m = manifestCache.data || {};
    const runs = Array.isArray(m.runs) ? m.runs : [];
    if (!runs.length) {
      wrap.appendChild(el("div", "tui-cb-status", "no runs in manifest yet"));
      return wrap;
    }

    const meta = el("div", "tui-cb-meta");
    meta.appendChild(el("span", "tui-cb-meta-key", "prompt:"));
    meta.appendChild(el("span", "tui-cb-meta-val", " " + (m.prompt || "")));
    wrap.appendChild(meta);

    const grid = el("div", "tui-cb-grid");
    runs.forEach((run) => grid.appendChild(renderGalleryTile(run)));
    wrap.appendChild(grid);
    return wrap;
  }

  function renderGalleryTile(run) {
    const tile = el("div", "tui-cb-tile");
    const imgWrap = el("div", "tui-cb-tile-img");
    const img = el("img");
    img.alt = run.label || run.model || "model output";
    img.loading = "lazy";
    img.src = "data/catbench/" + run.image;
    img.addEventListener("error", () => {
      imgWrap.classList.add("is-missing");
      imgWrap.replaceChildren();
      const ph = el("div", "tui-cb-tile-missing");
      ph.appendChild(el("div", "tui-cb-tile-missing-mark", "[no image yet]"));
      ph.appendChild(el("div", "tui-cb-tile-missing-path", run.image));
      imgWrap.appendChild(ph);
    });
    imgWrap.appendChild(img);
    tile.appendChild(imgWrap);

    const head = el("div", "tui-cb-tile-head");
    head.appendChild(el("span", "tui-cb-tile-label", run.label || run.model));
    head.appendChild(el("span", "tui-cb-tile-provider", run.provider || ""));
    tile.appendChild(head);

    const stats = el("div", "tui-cb-tile-stats");
    const addStat = (k, v) => {
      const row = el("div", "tui-cb-tile-stat");
      row.appendChild(el("span", "tui-cb-tile-stat-k", k));
      row.appendChild(el("span", "tui-cb-tile-stat-v", v));
      stats.appendChild(row);
    };
    addStat("model", run.model || "—");
    addStat("size",  run.size || "—");
    addStat("latency", fmtMs(run.latency_ms));
    addStat("cost", fmtCost(run.cost_usd));
    tile.appendChild(stats);
    return tile;
  }

  function renderByok() {
    const wrap = el("div", "tui-cb-byok");
    wrap.appendChild(el("div", "tui-table-title", "┌─ Bring your own key ─"));

    const lede = el("div", "tui-cb-byok-lede");
    lede.textContent =
      "Your key never leaves the browser tab; the request goes from here straight to the provider. ";
    const sec = el("span", "tui-cb-byok-secure", "(no proxy, no logging)");
    lede.appendChild(sec);
    wrap.appendChild(lede);

    // Provider chips
    const provRow = el("div", "tui-cb-byok-row");
    provRow.appendChild(el("div", "tui-cb-byok-label", "provider"));
    const provChips = el("div", "tui-cb-byok-chips");
    BYOK_PROVIDERS.forEach((p) => {
      const chip = el("button",
        "tui-cb-byok-chip" + (p.id === byok.providerId ? " is-active" : ""), p.label);
      chip.type = "button";
      chip.addEventListener("click", () => {
        if (byok.status === "running") return;
        byok.providerId = p.id;
        byok.modelId = p.models[0].id;
        render();
      });
      provChips.appendChild(chip);
    });
    provRow.appendChild(provChips);
    wrap.appendChild(provRow);

    const provider = byokProvider();

    // Model chips
    const modelRow = el("div", "tui-cb-byok-row");
    modelRow.appendChild(el("div", "tui-cb-byok-label", "model"));
    const modelChips = el("div", "tui-cb-byok-chips");
    provider.models.forEach((m) => {
      const chip = el("button",
        "tui-cb-byok-chip" + (m.id === byok.modelId ? " is-active" : ""), m.label);
      chip.type = "button";
      chip.title = m.pricing;
      chip.addEventListener("click", () => {
        if (byok.status === "running") return;
        byok.modelId = m.id;
        render();
      });
      modelChips.appendChild(chip);
    });
    modelRow.appendChild(modelChips);
    wrap.appendChild(modelRow);

    // API key
    const keyRow = el("div", "tui-cb-byok-row");
    const keyLabel = el("div", "tui-cb-byok-label", "api key");
    keyRow.appendChild(keyLabel);
    const keyField = el("div", "tui-cb-byok-field");
    const input = document.createElement("input");
    input.type = "password";
    input.className = "tui-cb-byok-input";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.placeholder = provider.keyHint;
    input.value = byok.apiKey;
    input.addEventListener("input", (e) => { byok.apiKey = e.target.value; });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); runByok(); }
    });
    keyField.appendChild(input);
    keyRow.appendChild(keyField);
    wrap.appendChild(keyRow);

    // Prompt (read-only; the whole point of CatBench is one fixed prompt).
    const promptRow = el("div", "tui-cb-byok-row");
    promptRow.appendChild(el("div", "tui-cb-byok-label", "prompt"));
    const promptVal = el("div", "tui-cb-byok-prompt");
    promptVal.textContent = CATBENCH_PROMPT;
    promptRow.appendChild(promptVal);
    wrap.appendChild(promptRow);

    // Generate button + status line
    const actionRow = el("div", "tui-cb-byok-actions");
    const btn = el("button",
      "tui-cb-byok-go" + (byok.status === "running" ? " is-busy" : ""),
      byok.status === "running" ? "generating..." : "Generate");
    btn.type = "button";
    btn.disabled = byok.status === "running";
    btn.addEventListener("click", runByok);
    actionRow.appendChild(btn);

    const status = el("span", "tui-cb-byok-status");
    if (byok.status === "running") {
      status.textContent = "calling " + byok.providerId + "/" + byok.modelId + "...";
    } else if (byok.status === "done" && byok.result) {
      status.textContent = "ok · " + fmtMs(byok.result.durationMs);
      status.classList.add("is-ok");
    } else if (byok.status === "error") {
      status.textContent = "error · " + (byok.error || "");
      status.classList.add("is-error");
    } else {
      status.textContent = "ready";
    }
    actionRow.appendChild(status);
    wrap.appendChild(actionRow);

    // Result image (if any)
    if (byok.status === "done" && byok.result) {
      const resWrap = el("div", "tui-cb-byok-result");
      const resHead = el("div", "tui-cb-byok-result-head");
      resHead.textContent = byok.result.model + "  ·  " + fmtMs(byok.result.durationMs);
      resWrap.appendChild(resHead);
      const img = el("img", "tui-cb-byok-result-img");
      img.src = byok.result.dataUrl;
      img.alt = "CatBench result";
      resWrap.appendChild(img);
      wrap.appendChild(resWrap);
    }

    return wrap;
  }

  function render() {
    const screen = currentScreen();
    screenEl.replaceChildren();

    // breadcrumb
    if (screen.breadcrumb) {
      const bc = renderBreadcrumb(screen.breadcrumb);
      if (bc) screenEl.appendChild(bc);
    }

    // question + instruction
    if (screen.question) {
      screenEl.appendChild(renderQuestion(screen.question, screen.instruction));
    }

    // input echo (for screens that simulate text/password prompts)
    if (screen.input) {
      screenEl.appendChild(renderInput(screen.input));
    }

    // panel (e.g., trace summary, run plan)
    if (screen.panel) {
      screenEl.appendChild(renderPanel(screen.panel));
    }

    // table (e.g., leaderboard preview, results table)
    if (screen.table) {
      screenEl.appendChild(renderTable(screen.table));
    }

    // tree (e.g., trace step list)
    if (screen.tree) {
      screenEl.appendChild(renderTree(screen.tree));
    }

    // CatBench gallery (image grid sourced from data/catbench/manifest.json)
    if (screen.gallery) {
      screenEl.appendChild(renderGallery(screen.gallery));
    }

    // CatBench BYOK form (provider, key, model, real fetch + result image)
    if (screen.byok) {
      screenEl.appendChild(renderByok());
    }

    // empty / yellow message
    if (screen.empty) {
      screenEl.appendChild(renderEmpty(screen.empty));
    }

    // items
    if (screen.items && screen.items.length) {
      const list = el("div", "tui-items");
      screen.items.forEach((item, i) => {
        list.appendChild(renderItem(item, i, i === state.cursor));
      });
      screenEl.appendChild(list);
    }

    // note (the demo-mode disclaimer)
    if (screen.note) {
      screenEl.appendChild(renderNote(screen.note));
    }
  }

  // ─── Events ──────────────────────────────────────────────────────────────

  frame.addEventListener("keydown", (e) => {
    // Real <input> fields (API key) need to swallow keystrokes so typing
    // doesn't move the cursor or activate menu items. Esc still pops out.
    const tag = e.target && e.target.tagName;
    const isFormField = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    if (isFormField && e.key !== "Escape") return;

    const k = e.key;
    if (k === "ArrowDown" || k === "j") {
      e.preventDefault();
      moveCursor(1);
    } else if (k === "ArrowUp" || k === "k") {
      e.preventDefault();
      moveCursor(-1);
    } else if (k === "Enter" || k === " ") {
      e.preventDefault();
      activateAt(state.cursor);
    } else if (k === "Escape" || k === "Backspace" || k === "q") {
      // q only escapes when the demo is at a sub-screen
      if (k === "q" && state.stack.length === 1) return;
      // Backspace inside a form field is a delete; only treat it as "pop" when
      // we're not in a field. (Form fields short-circuit above for non-Esc.)
      e.preventDefault();
      pop();
    } else if (k === "Home") {
      e.preventDefault();
      const idxs = selectableIndices(currentScreen());
      if (idxs.length) { state.cursor = idxs[0]; render(); }
    } else if (k === "End") {
      e.preventDefault();
      const idxs = selectableIndices(currentScreen());
      if (idxs.length) { state.cursor = idxs[idxs.length - 1]; render(); }
    }
  });

  frame.addEventListener("focus", () => {
    frame.classList.add("is-focused");
    if (focusStatusEl) focusStatusEl.textContent = "live";
  });
  frame.addEventListener("blur", () => {
    frame.classList.remove("is-focused");
    if (focusStatusEl) focusStatusEl.textContent = "click to focus";
  });

  // Initial paint.
  state.cursor = defaultCursor(SCREENS.main);
  render();
})();
