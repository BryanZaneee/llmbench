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
