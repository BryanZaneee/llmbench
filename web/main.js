// llmbench — leaderboard explorer.
// Fetches data/all.json (pre-merged across sources), renders a sortable/filterable
// table. Filter state is reflected in the URL so links are shareable.

const DATA_URL = "data/all.json";
const PRIMARY = {
  huggingface: { key: "average", label: "avg" },
  lmarena:     { key: "elo",     label: "elo" },
  bundled:     { key: "average", label: "avg" },
};

const state = {
  rows: [],
  query: "",
  sources: new Set(["huggingface", "lmarena", "bundled"]),
  sortKey: "primary_score",
  sortDir: "desc",
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
  const rows = applyFilters();
  const tbody = $("#lb-tbody");
  const empty = $("#lb-empty");

  tbody.innerHTML = "";
  empty.hidden = rows.length > 0;

  for (const r of rows) {
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
    `<strong>${rows.length}</strong> of ${state.rows.length} models · ` +
    `filtered across ${state.sources.size} source${state.sources.size === 1 ? "" : "s"}`;

  document.querySelectorAll(".lb-table thead th").forEach((th) => {
    th.dataset.sortDir =
      th.dataset.key === state.sortKey ? state.sortDir : "";
  });
}

function writeURL() {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  const allSources = ["huggingface", "lmarena", "bundled"];
  if (state.sources.size !== allSources.length) {
    params.set("source", [...state.sources].join(","));
  }
  if (state.sortKey !== "primary_score" || state.sortDir !== "desc") {
    params.set("sort", `${state.sortKey}:${state.sortDir}`);
  }
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
    state.sources = new Set(
      ["huggingface", "lmarena", "bundled"].filter((s) => wanted.has(s)),
    );
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
}

function wireEvents() {
  $("#lb-search").addEventListener("input", (e) => {
    state.query = e.target.value;
    writeURL();
    render();
  });

  document.querySelectorAll("#lb-source-filter input").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) state.sources.add(cb.value);
      else state.sources.delete(cb.value);
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
      writeURL();
      render();
    });
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
        // Clipboard API blocked — fall back to selection.
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
