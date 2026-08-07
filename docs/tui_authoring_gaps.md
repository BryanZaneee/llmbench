# TUI authoring gaps

Scoping document. No implementation plan, no code. Audited 2026-08-07 against
`src/llmbench/tui.py` and `src/llmbench/config.py` as they stand in the
working tree (both have uncommitted changes as of this audit).

## Stated intent vs. what exists

Project owner's description of llmbench:

> An easy way to benchmark LLMs. You configure the models and add your API
> keys in the TUI, then easily run benchmarks that you either author
> yourself through the TUI, or pull from leading sources like HuggingFace
> and LMArena.

| Claim | Status | Section |
|---|---|---|
| Configure models in the TUI | Holds | n/a, see below |
| Add API keys in the TUI | Holds, with gaps | Key storage location and coverage |
| Author benchmarks yourself in the TUI | Partial | Authoring benchmarks in the TUI |
| Pull benchmarks from HuggingFace and LMArena | Absent | Pulling benchmarks from HuggingFace |

**Configuring models holds outright.** `_flow_add_model` (`tui.py:328-383`)
reaches all 10 registered adapters by reading `adapters._REGISTRY` directly
(`tui.py:330-332`, registry at `adapters/__init__.py:10-21`), and persists
via `save_user_model` (`config.py:70-82`) to `~/.llmbench/models.yaml`. No
gaps worth a section; the sub-gaps below (add-only, two catalogs) are about
what happens after a model is added, not about adding one.

**Adding API keys holds, but the storage layer under it has real gaps.**
See "Key storage location and coverage" below.

The other two claims each get their own section, ordered by how central
they are to the pitch.

## Pulling benchmarks from HuggingFace and LMArena

**Status: does not exist.** `llmbench leaderboard` fetches published
*scores*, not runnable datasets, and there is no code path connecting it to
the benchmark runner.

Evidence:
- `LeaderboardSnapshot` (`leaderboards/base.py:33-37`) carries a list of
  `LeaderboardEntry` (`leaderboards/base.py:22-30`): a model id, display
  name, organization, and a `metrics: dict[str, float]`. There is no prompt
  field anywhere in the shape.
- No import or call anywhere under `leaderboards/` references `runner.py`
  or `benchmarks/`; the two subsystems are disjoint at the code level.
- `pyproject.toml` declares no `datasets` or `huggingface_hub` dependency,
  and neither name appears anywhere under `src/`.
- The four registered sources (`leaderboards/__init__.py:9-14`) are
  `huggingface` (HF's Open LLM Leaderboard v2 results table via the
  datasets-server rows API, `leaderboards/huggingface.py`), `lmarena`
  (chatbot-arena ELO ratings from a parquet file on the HF Hub,
  `leaderboards/lmarena.py`), `aider` (Aider Polyglot pass rates from a
  YAML file, `leaderboards/aider.py`), and `bundled` (a static offline
  snapshot, `leaderboards/bundled.py`).

**This is a deliberate decision, not an oversight.** `history.md:264-276`
(2026-04-23, "Published leaderboards") records the split explicitly: keep
published and locally-measured numbers in separate commands (`leaderboard`
vs. `run`) rather than mixing them in one table, because they are not
directly comparable (different environments, prompts, and scoring).
Closing this gap means reversing that recorded decision. This document
should not be read as recommending the reversal, only as flagging that the
stated intent and the recorded decision are in tension and someone should
pick one on purpose.

**LMArena specifically can never satisfy this claim.** Its leaderboard is
human-preference ELO from pairwise votes (`leaderboards/lmarena.py:30`,
"ELO ratings from human preference voting"). There is no underlying prompt
set to pull; the data structurally cannot become a runnable benchmark. Any
future work here is a HuggingFace-only question.

**HuggingFace is a real, if large, candidate.** The `huggingface` source
today pulls the *results* dataset (`open-llm-leaderboard/contents`), not
the underlying benchmark items. But the benchmarks it scores (IFEval, BBH,
MATH Lvl 5, GPQA, MUSR, MMLU-PRO) do have their source item sets published
as separate HF datasets, reachable via `huggingface_hub` / the
datasets-server API. Making this real would require, at minimum: a new
dependency, a mapping from an HF dataset's row schema to `Prompt`
(`schema.py:48-55`, which assumes a single prompt string plus an optional
expected answer or rubric, not multiple-choice or structured-answer
formats), a decision on how pulled items interact with the existing
`quality_exact` / `quality_judge` scoring (`benchmarks/quality_exact.py`,
`benchmarks/quality_judge.py`), and a decision on caching (mirroring the
existing `~/.cache/.../leaderboards/<source>.json` pattern, or something
new). Rough size: large. This is the biggest single item in this document.

## Authoring benchmarks in the TUI

**Status: partial.** `_build_custom_suite` (`tui.py:261-325`) lets a user
compose a run interactively: model checkbox (`tui.py:279`), benchmark
checkbox (`tui.py:289`), repetitions (`tui.py:299`), and a prompts-file path
(`tui.py:308`). It builds a real `SuiteConfig` (`config.py:27-34`) and hands
it straight to `_execute_run` (`tui.py:385-402`). Two distinct gaps sit
under "author benchmarks yourself," worth sizing separately.

### Gap A: the composed suite is never persisted to YAML

`_build_custom_suite` returns a `SuiteConfig` that lives only in memory for
the duration of one run (`tui.py:318-325`). Nothing under `src/` ever
writes a `SuiteConfig` back out as a suite YAML; `load_suite`
(`config.py:37-39`) is read-only. A user who builds a good ad hoc run in
the TUI cannot save it as a `suite.<name>.yaml` to reuse or hand to someone
else; they have to rebuild it by hand in YAML from scratch, or re-click
through the same TUI flow.

Two fields never even reach the in-memory object: `SuiteConfig.judge` is
never set by the TUI (`tui.py:318-325` omits it entirely, so it stays
`None`, the schema default at `config.py:34`), and sampling is hardcoded to
`SamplingParams()` defaults at `tui.py:324`, meaning `max_tokens`,
`temperature`, and `top_p` are not TUI-adjustable for benchmark runs.
(Contrast the agentic-task flow, which does expose temperature at
`tui.py:639-645`.) `suite.example.yaml:11-21` shows both fields in active
use: per-suite sampling and a pinned judge model, neither reachable from
the TUI today.

Rough size: small. `SuiteConfig` already round-trips through
`load_suite`/YAML; this needs a "save this suite?" prompt plus a
`yaml.safe_dump` call following the same pattern `save_user_model`
(`config.py:70-82`) already uses, and, to be a complete save, exposing
judge and sampling as new prompts in `_build_custom_suite`.

### Gap B: prompts cannot be authored in the TUI, only pointed at

The prompts step (`tui.py:307-316`) accepts only a path to an *existing*
file:

```
prompts_file = questionary.text(...).ask()
prompts_file = prompts_file.strip() or None
if prompts_file and not Path(prompts_file).exists():
    console.print(f"[yellow]Prompts file {prompts_file!r} not found; using built-in[/]")
    prompts_file = None
```

If the path is missing, it falls back to `runner.DEFAULT_PROMPTS`
(`runner.py:23-29`, three hardcoded prompts) after printing a yellow
warning. That fallback is not silent, but it is easy to miss in a
scrolling terminal session, and either way there is no path in the TUI
that lets a user type in a new prompt (id, prompt text, optional expected
answer, check mode, optional rubric per `Prompt` at `schema.py:48-55`)
without leaving the TUI to hand-write a YAML file first. "Author yourself
through the TUI" currently means "point the TUI at a file you authored
elsewhere."

Rough size: medium to large. Needs a repeatable add-a-prompt sub-flow
(one `questionary` round trip per `Prompt` field), a review/remove step
before confirming, and a decision on where authored prompts get written
(most naturally a new `prompts/<name>.yaml`, the same shape `load_prompts`
already parses at `runner.py:31-37`). Doing this well overlaps with Gap A:
an authored prompt set is most useful paired with a savable suite.

## Key storage location and coverage

Two separate problems live here: where keys get written and read, and
which keys the TUI knows about at all.

### Reads and writes do not use the same resolution rule

Writing a key goes through `_write_env_var` (`tui.py:497-511`), called
from `_flow_configure_keys` (`tui.py:470-494`), targeting
`ENV_PATH = Path(".env")` (`tui.py:103`). That path is a relative
`pathlib.Path`, so it resolves against the process's current working
directory at write time: run `llmbench` from two different directories and
you get two different `.env` files.

Reading a key goes through `load_dotenv()`, called with no arguments at
module import time (`config.py:18`). This is *not* CWD-relative. Verified
against the installed `python-dotenv` (`.venv/lib/python3.14/site-packages/dotenv/main.py:332-380`):
with no explicit path and outside a REPL/debugger, `find_dotenv()` walks
up from the directory containing the *calling frame's file*, i.e. wherever
`config.py` itself sits on disk, not the process's working directory. For
an editable dev install that resolves to the repo root (one level above
`src/llmbench/`), which happens to contain `.env.example`. For a real
`pipx`/`uvx` install, `config.py` lives inside that tool's isolated
site-packages, and the walk starts there, climbing through the venv and
home directory, never touching the terminal's current directory.

The practical effect: the two mechanisms are not merely "both CWD-relative
and therefore fragile," they use two different resolution strategies that
do not agree with each other. A key saved via "Configure API keys" writes
to whatever directory the shell was in at that moment; reading it back
depends on where the installed package physically lives, which for a
global install is unrelated to any directory the user ever visits. The
visible symptom, keys that appear to save but are not seen on the next
launch, can occur even without changing directories.

Fix direction: anchor both operations to the same, explicitly-passed path,
most naturally a user-scoped location like `~/.llmbench/.env`, mirroring
`USER_MODELS_PATH` (`config.py:50-51`), which is already correctly
user-scoped and has no such split.

### Coverage is incomplete, and there is no way to inspect or remove a key

`PROVIDER_KEYS` (`tui.py:87-92`) offers exactly four entries: Anthropic,
OpenAI, Gemini, Moonshot. Two more env vars are read elsewhere in the
codebase and are not settable from the TUI at all: `BFL_API_KEY`
(`adapters/flux.py:25-27`) and `HF_TOKEN` (`leaderboards/huggingface.py:80`,
`leaderboards/lmarena.py:66`). `_flow_configure_keys` only supports
setting a value; there is no way to view, reveal, or delete a stored key
once written.

A concrete illustration of coverage drift: `MOONSHOT_API_KEY` is settable
in the TUI and shown in the status line (`tui.py:201-208`), but it is
wired into exactly one place, the agentic-task engine's provider factory
(`agent/providers/__init__.py:40`). "moonshot" is not one of the 10 keys in
`adapters._REGISTRY` (`adapters/__init__.py:10-21`), so there is no
dedicated benchmark adapter for it. The only way to benchmark a
Moonshot-compatible endpoint is `adapter="openai_compat"` pointed at it via
`base_url`, and that adapter's key resolution
(`adapters/openai_compat.py:34-38`) only ever reads `OPENAI_API_KEY`,
falling back to the literal string `"local"` otherwise. A user who sets
`MOONSHOT_API_KEY` through the TUI and then benchmarks Moonshot via
`openai_compat` gets a key that works for agentic tasks and is silently
ignored for benchmarks.

Rough size: medium. Extending `PROVIDER_KEYS` to cover `BFL_API_KEY` and
`HF_TOKEN`, and adding view/reveal/delete, are each mechanical. Reconciling
which adapter reads which env var (the Moonshot case above) is a smaller
but separate fix inside the adapter layer, not the TUI.

## Model config is add-only, and split across two catalogs

`config.py` exposes exactly two functions for user models:
`load_user_models` and `save_user_model` (`config.py:60-82`). There is no
edit and no delete. `save_user_model` overwrites only when the new spec's
`(provider, model, base_url)` triple exactly matches an existing one
(`config.py:75`); anything else, including a typo, becomes a new entry
with no way to remove the old one short of hand-editing
`~/.llmbench/models.yaml`. The per-model `benchmarks` filter
(`schema.py:38`, consumed by `runner.py` to skip mismatched
model/benchmark pairs) has no TUI prompt to set it; a model added through
the TUI always runs every benchmark in the suite.

Separately, there are two catalogs that do not talk to each other.
Benchmarks read `~/.llmbench/models.yaml` via `load_user_models`
(`tui.py:262`, inside `_build_custom_suite`). Agentic tasks read a
different, hardcoded, priced catalog via `agent.pricing.list_models`
(`tui.py:592`, called at `tui.py:608`). A model added through "Add a
model" is invisible to "Run agentic task," and vice versa. This split is
recorded as deliberate in `history.md:11` (2026-05-05: "the user-models
file only feeds the 'Build a custom run' flow"), so it should be flagged
to the project owner as a UX consequence to confirm rather than treated as
an unintended bug to silently fix.

Rough size: medium. Add-only plus no `benchmarks` filter exposure is a
self-contained TUI change. Reconciling the two catalogs is a design
decision first (merge them, or make the split visible to the user) and an
implementation second.

## The missing-key pre-flight is unsound

`_confirm_provider_key` (`tui.py:113-126`) is meant to warn before a run
that will fail for lack of a key. It maps against `_PROVIDER_KEY_BY_ID`
(`tui.py:96-101`), a four-entry, lowercase dict: `anthropic`, `openai`,
`gemini`, `moonshot`. The value it matches against, `spec.provider`, is
free text the user typed at `tui.py:341-348`, defaulted to the adapter
name but otherwise unconstrained. The TUI's own key-configuration labels
(`tui.py:88-91`) train the user to type the capitalized form ("Anthropic",
"OpenAI", ...), which does not match the lowercase dict either.

Any model whose adapter is `google`, `flux`, `bfl`, `openai_compat`,
`vllm`, or `lmstudio`, or whose provider text is capitalized, misspelled,
or otherwise not one of the four exact lowercase strings, silently passes
the guard with `needed` empty (`tui.py:115`) and the run proceeds. It then
fails mid-flight in the adapter (e.g. `RuntimeError("BFL_API_KEY is not
set")` at `adapters/flux.py:27`) instead of being caught by the
pre-flight meant to catch exactly this. Given `PROVIDER_KEYS`'s own
labeling trains users toward the capitalized form, this is a failure mode
a first-time user is likely to hit directly, not an edge case.

Rough size: small to medium as a mechanical fix, the harder part is
picking the right key: `spec.adapter` is a closed, registered set
(`adapters/__init__.py:10-21`) and a better match than free-text
`spec.provider`, but the check would then need a mapping from adapter to
the actual env var each adapter class reads, which is currently scattered
across adapter files rather than centralized anywhere.

## Registry duplication: benchmark choices

`BENCHMARK_CHOICES` (`tui.py:71-77`) is a hand-maintained list of five
strings that must stay in sync with `benchmarks._REGISTRY`
(`benchmarks/__init__.py:11-17`). Verified in sync today, five entries in
each, same names. There is no user-visible symptom yet; this is pure drift
hazard. A sixth benchmark registered in `benchmarks/__init__.py` alone
would be invisible in the TUI's "Run benchmarks" checkbox until
`tui.py:71-77` is also hand-edited. `_flow_add_model` already shows the
fix pattern in the same file: it reads `adapters._REGISTRY` directly
(`tui.py:330-332`) rather than hand-listing adapters. `BENCHMARK_CHOICES`
could do the same, `sorted(_REGISTRY)` from `benchmarks/__init__.py`.

Rough size: small.

## Not a gap: new scoring types stay code-only

New *benchmark types* (as opposed to benchmark *content*, i.e. prompt
sets) are deliberately code-only. `AGENTS.md` states the extension
contract directly: subclass `Benchmark` in `benchmarks/base.py:13-29`,
mirror an existing sibling, register in `benchmarks/__init__.py`. This
matches the project's stated code style ("Don't invent abstractions... new
benchmarks/adapters/sources should look like siblings of the existing
ones"). None of the gaps above propose changing this; a TUI cannot and
should not let a user define a new scoring strategy without writing
Python. The gaps above are all about *content* (prompts, suites, keys,
models), which is data, not about *scoring logic*, which is code.
