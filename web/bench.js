// llmbench: CatBench bring-your-own-key image generation runner.
// The user pastes a Gemini or OpenAI API key, picks a model, and generates
// an image against a shared prompt. Keys stay in memory only; requests go
// straight from the browser to the provider, no proxy, no logging.

(function () {
  "use strict";

  const panel = document.getElementById("bench-panel");
  if (!panel) return;

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

  // ─── Render ──────────────────────────────────────────────────────────────

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
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
    panel.replaceChildren();
    panel.appendChild(renderGallery({ manifestUrl: MANIFEST_URL }));
    panel.appendChild(renderByok());
  }

  // Initial paint.
  render();
})();
