# AI Novel Writer

A multi-agent system designed to write long-form coherent novels by maintaining a structured, multi-tier memory of the world, characters, and plot.

Many thanks to Gemini and GPT for their help!

> [!NOTE]
> The project is currently in a very early stage.

[👉 Project Architecture](docs/Architecture.md), [👉 Flowchart](docs/Flowchart.md), [👉 Document](docs/)

## Key Features

* **Long-Term Consistency:** Uses a hybrid database (SQLite + FAISS) to track "hard" facts (rules, relationships) vs. "soft" details (descriptions, atmosphere).
* **Multi-Agent Collaboration:** Specialized AI roles (Architect, Writer, Critic, Scanner) work together to plan, write, review, and archive the story.
* **Dual Model Support:** Supports **Google Gemini** and **OpenAI Compatible APIs**.
* **Dedicated Embedding Service:** Decoupled architecture allowing separate endpoints for Generation (LLM) and Embeddings (Vector DB), optimizing performance for local deployments.
* **Continuous Writing:** Automated loop to generate multiple chapters in sequence.
* **Two-Stage Plot Planning:** Builds both a high-level Novel Plot Outline and a Detailed Plot Outline before chapter planning.
* **Unified Discussion Template:** World/plot/guide/chapter-text discussions now share one normalized template and title format.
* **Discussion Index:** All discussion entries are mirrored into `novel/process/discussions/discussion_index.jsonl` for audit/search.
* **Intent-Gated Retrieval Chain:** Planning/writing now enforce `Intent Classifier -> SQLite Prefilter -> FAISS Retrieval -> Cross-Tier Alignment`.
* **Retriever-Augmented Planning:** Chapter planning now injects Tier-3 semantic details by running intent-gated vector retrieval before guide generation.
* **Multi-Language Support:** Native support for Chinese and English prompts.
* **Chapter Review Loop:** Every chapter can be reviewed by Critic and revised by Writer for 0-2 rounds.
* **Role-Specific Models:** Architect/Planner/Writer/Critic/Scanner can each use different model providers and model names.
* **Audit-Aware Memory:** Chapter scans create commit records, write fact revision logs, and queue hard conflicts for follow-up.
* **Conflict Severity Levels:** Conflicts are classified as `BLOCKING` or `NON_BLOCKING`, and workflow gating only blocks on unresolved `BLOCKING` items.
* **Configurable Blocking Governance:** `BLOCKING_CONFLICT_MODE` supports `auto_keep_existing` (low-touch strict mode) or `manual_block` (human-gated strict mode).
* **Conflict Triage Metadata:** Pending conflicts include `priority` and `suggested_action` for faster operator decisions.

## Project Structure

```text
.
├── docs/           # Documentation
├── novel/          # The project data (created at runtime)
│   ├── frame/
│   │   ├── world/          # world_bible.md
│   │   ├── plot/           # plot_outline.md + detailed_plot_outline.md
│   │   ├── chapter_guides/ # chapter_001_guide.md...
│   │   └── archives/       # compact character/rule snapshots
│   ├── main_text/
│   │   └── chapters/       # chapter_001.md...
│   └── process/
│       ├── critiques/      # critique.md
│       ├── discussions/    # normalized world/plot/guide/chapter-text logs + discussion_index.jsonl
│       ├── reviews/        # chapter_001_review.md...
│       ├── revisions/      # chapter_001_revision_round_001.md...
│       └── facts/          # chapter_001_facts.json/summary/raw
├── src/            # Source code
│   └── prompts/    # Markdown prompt templates (zh/en)
│   └── workflow_components/ # Workflow helper modules (prompts/parsing/discussion)
└── reports/        # Metrics & logs
```

## Installation

1. **Prerequisites:**
   * Python 3.10+
   * (Optional) A supported local LLM model (GGUF format) for Llama.cpp or an OpenAI-compatible server.
   * (Optional) A dedicated local Embedding server (e.g., Ollama running `nomic-embed-text`).

2. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration:**
   * Open `src/config.py`.
   * Set `LANGUAGE = "Chinese"` or `"English"`.
   * Configure role model routing (provider + model name) and workflow controls (discussion/revision rounds).

## Usage

### 1. Initialize Workspace

Initialize only the `novel/` workspace and create `novel/Novel_Overview.md`.

```bash
python src/main.py --init
```

Then fill `novel/Novel_Overview.md` with your high-level setup and start generation:

```bash
python src/main.py --start
```

### 2. Manual Workflow

* **Plan:** `python src/main.py --plan 1`
* **Write:** `python src/main.py --write 1` (now enforces `write -> review/revise -> scan`)
* **Scan:** `python src/main.py --scan 1`
* **List conflicts:** `python src/main.py --conflicts`
* **List conflicts (JSON diagnostics):** `python src/main.py --conflicts-json`
* **List conflicts (triage):** `python src/main.py --conflicts-triage`
* **Filter conflicts by level:** append `--level BLOCKING` or `--level NON_BLOCKING`
* **Resolve conflict:** `python src/main.py --resolve-conflict 3 keep_existing --resolve-note "manual decision"`
* **Batch triage non-blocking conflicts:** `python src/main.py --triage-batch 50`
* **List failed commit batches:** `python src/main.py --failed-commits`
* **Replay failed batch:** `python src/main.py --replay-commit <COMMIT_ID>`
* **Rebuild vectors from metadata:** `python src/main.py --rebuild-vectors`

### 3. Continuous Writing (Auto Mode)

Generate multiple chapters automatically. The system will Plan -> Write -> Scan for each chapter in sequence.

```bash
# Generate 5 chapters starting from Chapter 1
python src/main.py --auto 1 5
```

Auto mode is resumable. If interrupted, rerun the same `--auto START_CHAPTER COUNT` command:

* Chapters that already have scanned facts (`chapter_{n}_facts_summary.md` / `chapter_{n}_facts.json`) are skipped.
* Resume runs strict integrity checks across all generated runtime artifacts under `novel/` (Markdown/text logs, JSON, JSONL).
* JSON/JSONL syntax is validated; chapter facts JSON also passes schema validation.
* Chapter completion additionally requires chapter text, facts summary, and latest `scan_chapter` commit status/payload integrity.
* If a chapter is incomplete or corrupted, its chapter-scoped artifacts are discarded and that chapter is regenerated from Plan -> Write -> Review -> Scan.
* If a critical global frame file is corrupted (e.g., `world_bible.md`), resume is blocked after discard and requires regenerating project frames before continuing.

Detailed mechanism specification: `docs/INTERRUPTION_RESUME.md`.

## GPU Acceleration & Model Configuration

The system now supports separating the **Generation Model** from the **Embedding Model** for optimal local performance.
