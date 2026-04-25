// llmbench — leaderboard explorer.
// Fetches data/all.json (pre-merged across sources), renders a sortable/
// filterable table.  Top 10 by default; "Load 50 more" or "Show all" reveal
// the rest.  Filter state is reflected in the URL so links are shareable.

const DATA_URL = "data/all.json";
const PRIMARY = {
  huggingface: { key: "average",            label: "avg" },
  lmarena:     { key: "elo",                label: "elo" },
  aider:       { key: "polyglot_pass_rate", label: "polyglot %" },
  bundled:     { key: "average",            label: "avg" },
};
const ALL_SOURCES = ["huggingface", "lmarena", "aider", "bundled"];
const INITIAL_LIMIT = 10;
const PAGE_INCREMENT = 50;

const state = {
  rows: [],
  query: "",
  sources: new Set(ALL_SOURCES),
  sortKey: "primary_score",
  sortDir: "desc",
  limit: INITIAL_LIMIT,
};

const $ = (sel) => document.querySelector(sel);

function primaryFor(entry) {
  const spec = PRIMARY[entry.source];
  if (!spec) return { score: null, label: "" };
  const score = entry.metrics?.[spec.key];
  return { score: typeof score === "number" ? score : null, label: spec.label };
}

function normalize(raw) {
  return raw.map((e) => {
    const { score, label } = primaryFor(e);
    return {
      model_id: e.model_id,
      display_name: e.display_name,
      organization: e.organization,
      source: e.source,
      source_url: e.source_url,
      rank: e.rank ?? null,
      metrics: e.metrics || {},
      primary_score: score,
      primary_label: label,
    };
  });
}

function applyFilters() {
  const q = state.query.trim().toLowerCase();
  let rows = state.rows.filter((r) => state.sources.has(r.source));
  if (q) {
    rows = rows.filter(
      (r) =>
        r.display_name.toLowerCase().includes(q) ||
        r.model_id.toLowerCase().includes(q) ||
        r.organization.toLowerCase().includes(q),
    );
  }
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

function render() {
  const filtered = applyFilters();
  const visible = filtered.slice(0, state.limit);
  const tbody = $("#lb-tbody");
  const empty = $("#lb-empty");

  tbody.innerHTML = "";
  empty.hidden = filtered.length > 0;

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

  $("#lb-meta").innerHTML =
    `<strong>${visible.length}</strong> of ${filtered.length} matching · ` +
    `${state.rows.length} total across ${state.sources.size} source${state.sources.size === 1 ? "" : "s"}`;

  document.querySelectorAll(".lb-table thead th").forEach((th) => {
    th.dataset.sortDir =
      th.dataset.key === state.sortKey ? state.sortDir : "";
  });

  // Pagination buttons: hide both when nothing more to reveal.
  const hidden = filtered.length - visible.length;
  const loadBtn = $("#lb-loadmore");
  const allBtn = $("#lb-showall");
  const wrap = $("#lb-loadmore-wrap");
  if (hidden > 0) {
    wrap.hidden = false;
    loadBtn.hidden = false;
    allBtn.hidden = false;
    loadBtn.textContent = `Load ${Math.min(PAGE_INCREMENT, hidden)} more`;
    allBtn.textContent = `Show all ${filtered.length}`;
  } else {
    wrap.hidden = true;
    loadBtn.hidden = true;
    allBtn.hidden = true;
  }
}

function writeURL() {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.sources.size !== ALL_SOURCES.length) {
    params.set("source", [...state.sources].join(","));
  }
  if (state.sortKey !== "primary_score" || state.sortDir !== "desc") {
    params.set("sort", `${state.sortKey}:${state.sortDir}`);
  }
  if (state.limit !== INITIAL_LIMIT) params.set("n", String(state.limit));
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
    state.sources = new Set(ALL_SOURCES.filter((s) => wanted.has(s)));
    document.querySelectorAll("#lb-source-filter input").forEach((cb) => {
      cb.checked = state.sources.has(cb.value);
    });
  }
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
    state.limit = INITIAL_LIMIT;
    writeURL();
    render();
  });

  document.querySelectorAll("#lb-source-filter input").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) state.sources.add(cb.value);
      else state.sources.delete(cb.value);
      state.limit = INITIAL_LIMIT;
      writeURL();
      render();
    });
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
      state.limit = INITIAL_LIMIT;
      writeURL();
      render();
    });
  });

  $("#lb-loadmore").addEventListener("click", () => {
    state.limit += PAGE_INCREMENT;
    writeURL();
    render();
  });

  $("#lb-showall").addEventListener("click", () => {
    state.limit = state.rows.length;
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
