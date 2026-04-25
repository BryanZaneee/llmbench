// llmbench — leaderboard explorer.
// Fetches data/all.json (pre-merged across sources), renders a sortable / chip-
// filterable table with top-25 + load-more pagination. Filter state is mirrored
// to the URL so links are shareable.

const DATA_URL = "data/all.json";

// Per-source default "primary" metric used when the user hasn't picked one.
// Each source publishes different columns; this keeps a single Score column
// meaningful in mixed-source views.
const PRIMARY = {
  huggingface: { key: "average",            label: "avg" },
  lmarena:     { key: "elo",                label: "elo" },
  bundled:     { key: "average",            label: "avg" },
  aider:       { key: "polyglot_pass_rate", label: "polyglot %" },
};

// Friendly labels for known metric keys. Anything missing falls back to a
// titlecased version of the key.
const METRIC_LABELS = {
  average:               "Average",
  elo:                   "LMArena ELO",
  ifeval:                "IFEval",
  bbh:                   "BBH",
  math_lvl_5:            "MATH Lvl 5",
  gpqa:                  "GPQA",
  musr:                  "MUSR",
  mmlu_pro:              "MMLU-PRO",
  polyglot_pass_rate:    "Aider Polyglot",
  polyglot_correct_edits:"Aider Edit Format",
};

// Provider chip allowlist — display name -> set of organization-string
// fragments to match (case-insensitive). Entries without a match fall under
// "Other" (which is opt-in via the chip).
const PROVIDERS = [
  { id: "anthropic", label: "Anthropic", match: ["anthropic"] },
  { id: "openai",    label: "OpenAI",    match: ["openai"] },
  { id: "google",    label: "Google",    match: ["google", "deepmind"] },
  { id: "meta",      label: "Meta",      match: ["meta", "meta-llama"] },
  { id: "mistral",   label: "Mistral",   match: ["mistral"] },
  { id: "deepseek",  label: "DeepSeek",  match: ["deepseek"] },
  { id: "qwen",      label: "Qwen",      match: ["qwen", "alibaba"] },
  { id: "xai",       label: "xAI",       match: ["xai", "x-ai", "grok"] },
];

const ALL_SOURCE_IDS = ["huggingface", "lmarena", "aider", "bundled"];
const PAGE_SIZE = 25;

const state = {
  rows: [],
  query: "",
  sources: new Set(ALL_SOURCE_IDS),
  orgs: new Set(),         // empty set = all providers (no filter)
  metric: "auto",          // "auto" uses PRIMARY per source; otherwise a metric key
  sortKey: "primary_score",
  sortDir: "desc",
  limit: PAGE_SIZE,
};

const $ = (sel) => document.querySelector(sel);

function metricLabel(key) {
  if (METRIC_LABELS[key]) return METRIC_LABELS[key];
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function providerFor(org) {
  const o = (org || "").toLowerCase();
  for (const p of PROVIDERS) {
    if (p.match.some((m) => o.includes(m))) return p.id;
  }
  return "other";
}

function scoreFor(entry) {
  // When metric="auto", pick the source's primary key. Otherwise return the
  // selected metric (or null if this row doesn't have it).
  if (state.metric === "auto") {
    const spec = PRIMARY[entry.source];
    if (!spec) return { score: null, label: "" };
    const v = entry.metrics?.[spec.key];
    return { score: typeof v === "number" ? v : null, label: spec.label };
  }
  const v = entry.metrics?.[state.metric];
  return {
    score: typeof v === "number" ? v : null,
    label: metricLabel(state.metric),
  };
}

function normalize(raw) {
  return raw.map((e) => ({
    model_id: e.model_id,
    display_name: e.display_name,
    organization: e.organization || "unknown",
    provider_id: providerFor(e.organization),
    source: e.source,
    source_url: e.source_url,
    rank: e.rank ?? null,
    metrics: e.metrics || {},
  }));
}

function applyFilters() {
  const q = state.query.trim().toLowerCase();

  let rows = state.rows.filter((r) => {
    if (!state.sources.has(r.source)) return false;
    if (state.orgs.size && !state.orgs.has(r.provider_id)) return false;
    if (q) {
      const hay =
        r.display_name.toLowerCase() +
        " " +
        r.model_id.toLowerCase() +
        " " +
        r.organization.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (state.metric !== "auto" && typeof r.metrics?.[state.metric] !== "number") {
      return false;
    }
    return true;
  });

  // Decorate each row with the active score / label.
  rows = rows.map((r) => {
    const { score, label } = scoreFor(r);
    return { ...r, primary_score: score, primary_label: label };
  });

  rows.sort((a, b) => {
    const av = a[state.sortKey];
    const bv = b[state.sortKey];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "number" && typeof bv === "number") {
      return state.sortDir === "asc" ? av - bv : bv - av;
    }
    const cmp = String(av).localeCompare(String(bv));
    return state.sortDir === "asc" ? cmp : -cmp;
  });
  return rows;
}

function makeChip(label, active, onClick, opts = {}) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "lb-chip";
  btn.dataset.active = active ? "true" : "false";
  if (opts.title) btn.title = opts.title;
  btn.textContent = label;
  if (opts.count != null) {
    const c = document.createElement("span");
    c.className = "lb-chip-count";
    c.textContent = opts.count;
    btn.appendChild(c);
  }
  btn.addEventListener("click", onClick);
  return btn;
}

function renderChips() {
  // Source chips — multi-select toggle. Only render sources that actually
  // appear in the loaded data (so an unfetched source isn't shown).
  const sourceCounts = {};
  for (const r of state.rows) sourceCounts[r.source] = (sourceCounts[r.source] || 0) + 1;
  const sourceBox = $("#lb-chips-source");
  sourceBox.innerHTML = "";
  for (const id of ALL_SOURCE_IDS) {
    if (!sourceCounts[id]) continue;
    sourceBox.appendChild(
      makeChip(id, state.sources.has(id), () => {
        if (state.sources.has(id)) state.sources.delete(id);
        else state.sources.add(id);
        state.limit = PAGE_SIZE;
        writeURL();
        render();
      }, { count: sourceCounts[id] }),
    );
  }

  // Provider chips — multi-select toggle. Empty selection means "all".
  const orgCounts = {};
  for (const r of state.rows) orgCounts[r.provider_id] = (orgCounts[r.provider_id] || 0) + 1;
  const orgBox = $("#lb-chips-org");
  orgBox.innerHTML = "";
  const allActive = state.orgs.size === 0;
  orgBox.appendChild(
    makeChip("All", allActive, () => {
      state.orgs.clear();
      state.limit = PAGE_SIZE;
      writeURL();
      render();
    }),
  );
  for (const p of PROVIDERS) {
    const n = orgCounts[p.id] || 0;
    if (!n) continue;
    orgBox.appendChild(
      makeChip(p.label, state.orgs.has(p.id), () => {
        if (state.orgs.has(p.id)) state.orgs.delete(p.id);
        else state.orgs.add(p.id);
        state.limit = PAGE_SIZE;
        writeURL();
        render();
      }, { count: n }),
    );
  }
  if (orgCounts.other) {
    orgBox.appendChild(
      makeChip("Other", state.orgs.has("other"), () => {
        if (state.orgs.has("other")) state.orgs.delete("other");
        else state.orgs.add("other");
        state.limit = PAGE_SIZE;
        writeURL();
        render();
      }, { count: orgCounts.other }),
    );
  }

  // Metric chips — single-select. "Auto" means each row uses its source's
  // primary metric; explicit metrics filter to rows that publish that key.
  const metricCounts = {};
  for (const r of state.rows) {
    for (const k of Object.keys(r.metrics || {})) {
      if (k === "elo_lower" || k === "elo_upper") continue; // CIs, not scores
      metricCounts[k] = (metricCounts[k] || 0) + 1;
    }
  }
  const metricBox = $("#lb-chips-metric");
  metricBox.innerHTML = "";
  metricBox.appendChild(
    makeChip("Auto", state.metric === "auto", () => {
      state.metric = "auto";
      state.limit = PAGE_SIZE;
      writeURL();
      render();
    }, { title: "Each source's primary metric" }),
  );
  const metricKeys = Object.keys(metricCounts).sort(
    (a, b) => metricCounts[b] - metricCounts[a],
  );
  for (const k of metricKeys) {
    metricBox.appendChild(
      makeChip(metricLabel(k), state.metric === k, () => {
        state.metric = state.metric === k ? "auto" : k;
        // Switching metric resets sort to score desc — most useful default.
        state.sortKey = "primary_score";
        state.sortDir = "desc";
        state.limit = PAGE_SIZE;
        writeURL();
        render();
      }, { count: metricCounts[k] }),
    );
  }

  // Sort chips — single-select with direction toggle on re-click.
  const sortOptions = [
    { key: "rank",          label: "Rank",   defaultDir: "asc"  },
    { key: "primary_score", label: "Score",  defaultDir: "desc" },
    { key: "display_name",  label: "Name",   defaultDir: "asc"  },
    { key: "organization",  label: "Org",    defaultDir: "asc"  },
  ];
  const sortBox = $("#lb-chips-sort");
  sortBox.innerHTML = "";
  for (const o of sortOptions) {
    const active = state.sortKey === o.key;
    const arrow = active ? (state.sortDir === "asc" ? " ↑" : " ↓") : "";
    sortBox.appendChild(
      makeChip(o.label + arrow, active, () => {
        if (state.sortKey === o.key) {
          state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
        } else {
          state.sortKey = o.key;
          state.sortDir = o.defaultDir;
        }
        state.limit = PAGE_SIZE;
        writeURL();
        render();
      }),
    );
  }
}

function renderTable(filtered) {
  const tbody = $("#lb-tbody");
  const empty = $("#lb-empty");
  tbody.innerHTML = "";
  empty.hidden = filtered.length > 0;

  const visible = filtered.slice(0, state.limit);
  for (const r of visible) {
    const tr = document.createElement("tr");

    const rank = document.createElement("td");
    rank.className = "lb-td-rank lb-td-num";
    rank.textContent = r.rank ?? "—";
    tr.appendChild(rank);

    const model = document.createElement("td");
    model.className = "lb-td-model";
    if (r.source_url) {
      const a = document.createElement("a");
      a.href = r.source_url;
      a.rel = "noopener";
      a.target = "_blank";
      a.textContent = r.display_name;
      model.appendChild(a);
    } else {
      model.textContent = r.display_name;
    }
    tr.appendChild(model);

    const org = document.createElement("td");
    org.className = "lb-td-org";
    org.textContent = r.organization;
    tr.appendChild(org);

    const src = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "lb-source-badge";
    badge.dataset.source = r.source;
    badge.textContent = r.source;
    src.appendChild(badge);
    tr.appendChild(src);

    const score = document.createElement("td");
    score.className = "lb-td-num";
    score.textContent = r.primary_score == null ? "—" : r.primary_score.toFixed(2);
    tr.appendChild(score);

    const label = document.createElement("td");
    label.className = "lb-td-num";
    label.textContent = r.primary_label || "—";
    tr.appendChild(label);

    tbody.appendChild(tr);
  }

  // Reflect sort-key in column header arrows so column-click sort still works.
  document.querySelectorAll(".lb-table thead th").forEach((th) => {
    th.dataset.sortDir =
      th.dataset.key === state.sortKey ? state.sortDir : "";
  });

  // Score column header reflects active metric.
  const scoreTh = $("#lb-th-score");
  if (scoreTh) {
    scoreTh.textContent =
      state.metric === "auto" ? "Score" : metricLabel(state.metric);
  }

  // Pagination: show "Load more" only when there are hidden rows.
  const loadBtn = $("#lb-loadmore");
  const hidden = filtered.length - visible.length;
  if (hidden > 0) {
    loadBtn.hidden = false;
    loadBtn.textContent = `Load ${Math.min(PAGE_SIZE, hidden)} more · ${hidden} hidden`;
  } else {
    loadBtn.hidden = true;
  }

  $("#lb-meta").innerHTML =
    `<strong>${visible.length}</strong> of ${filtered.length} matching · ` +
    `${state.rows.length} total across ${state.sources.size} source${state.sources.size === 1 ? "" : "s"}`;
}

function render() {
  renderChips();
  renderTable(applyFilters());
}

function writeURL() {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.sources.size !== ALL_SOURCE_IDS.length) {
    params.set("source", [...state.sources].join(","));
  }
  if (state.orgs.size) {
    params.set("org", [...state.orgs].join(","));
  }
  if (state.metric !== "auto") params.set("metric", state.metric);
  if (state.sortKey !== "primary_score" || state.sortDir !== "desc") {
    params.set("sort", `${state.sortKey}:${state.sortDir}`);
  }
  if (state.limit !== PAGE_SIZE) params.set("n", String(state.limit));
  const qs = params.toString();
  const url = qs ? `?${qs}` : window.location.pathname;
  history.replaceState(null, "", url);
}

function readURL() {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");
  if (q) {
    state.query = q;
    $("#lb-search").value = q;
  }
  const srcCsv = params.get("source");
  if (srcCsv) {
    const wanted = new Set(srcCsv.split(",").filter(Boolean));
    state.sources = new Set(ALL_SOURCE_IDS.filter((s) => wanted.has(s)));
  }
  const orgCsv = params.get("org");
  if (orgCsv) {
    state.orgs = new Set(orgCsv.split(",").filter(Boolean));
  }
  const metric = params.get("metric");
  if (metric) state.metric = metric;
  const sort = params.get("sort");
  if (sort && sort.includes(":")) {
    const [k, d] = sort.split(":");
    state.sortKey = k;
    state.sortDir = d === "asc" ? "asc" : "desc";
  }
  const n = parseInt(params.get("n") || "", 10);
  if (Number.isFinite(n) && n > 0) state.limit = n;
}

function wireEvents() {
  $("#lb-search").addEventListener("input", (e) => {
    state.query = e.target.value;
    state.limit = PAGE_SIZE;
    writeURL();
    render();
  });

  document.querySelectorAll(".lb-table thead th").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (!key) return;
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDir = key === "display_name" || key === "organization" || key === "source"
          ? "asc"
          : "desc";
      }
      state.limit = PAGE_SIZE;
      writeURL();
      render();
    });
  });

  $("#lb-loadmore").addEventListener("click", () => {
    state.limit += PAGE_SIZE;
    writeURL();
    render();
  });

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = btn.dataset.copy;
      try {
        await navigator.clipboard.writeText(text);
        btn.dataset.copied = "true";
        const prev = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(() => {
          btn.textContent = prev;
          delete btn.dataset.copied;
        }, 1200);
      } catch {
        const range = document.createRange();
        const code = btn.previousElementSibling;
        if (code) {
          range.selectNodeContents(code);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        }
      }
    });
  });
}

async function boot() {
  try {
    const res = await fetch(DATA_URL, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const raw = await res.json();
    state.rows = normalize(raw.entries || []);
  } catch (err) {
    $("#lb-meta").textContent = `Failed to load leaderboard data: ${err.message}`;
    return;
  }
  readURL();
  wireEvents();
  render();
}

boot();
