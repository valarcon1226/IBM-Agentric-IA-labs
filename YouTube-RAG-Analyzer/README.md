# YouTube Knowledge Extractor

Turns YouTube videos into dense, fact-checked Markdown reference documents, filed by topic and browsable from a local web dashboard. Built to run entirely on free LLM tiers: a multi-provider fallback chain spreads the work across Gemini, Groq, NVIDIA, Mistral and OpenRouter and waits out quota limits instead of failing.

In daily use it has processed 70+ videos (tool reviews, agent tutorials, business talks), at roughly 2 to 8 minutes per video depending on length and which provider answers.

---

## How It Works

```
URL or search term
      │
      ▼
 Metadata + transcript (yt-dlp, youtube-transcript-api) ── cached in .cache/<video_id>.json
      │
      ▼
 Phase 1  Factual extraction   transcript split into ~20k-char chunks, atomic facts as JSON (Pydantic schema)
 Phase 2  Deduplication        merges facts repeated across chunks (skipped for single-chunk videos)
 Phase 3  Synthesis            Markdown document built only from the extracted facts, in the video's language
 Phase 4  Validation           LLM audit against the transcript + regex check of every URL and command
      │
      ▼
 Classification into a topic folder → Results/<Category>/<Title>.md + <Title>_transcript.txt
```

| Stage | What it guards against | Where |
|---|---|---|
| Chunked extraction | Long transcripts sent in one call lose content in the middle; ~5 minutes of speech per call keeps extraction complete | `phase1_extract`, `EXTRACT_CHUNK_CHARS` |
| Facts-only synthesis | The writer model adding outside knowledge: phase 3 sees the fact list, not the open web | `phase3_synthesize` |
| Two-layer validation | Hallucinated claims (LLM audit fixes or deletes them) and invented links or commands (regex flags any URL or code span missing from the transcript) | `phase4_validate` |
| Structured output | Malformed model answers: every JSON step is parsed into Pydantic models, and an empty or truncated answer stops the run instead of producing a partial report | `call_llm`, schemas at the top of `main.py` |
| Shared quota budget | Burning the daily free quota another project depends on: calls go through `jobHunter/llm_chain.py`, which keeps a rolling 24 h budget per provider and a 15-minute cooldown after a 429 or timeout | `call_llm`, `jobHunter/llm_chain.py` |

The report adapts to the video: sections such as *Tools & Technologies*, *Workflow / Steps*, *Commands & Code* or *Author's Opinions* appear only when the video has facts for them. Each report starts with front matter (`category`, `video_id`) that the dashboard reads.

---

## Dashboard

`dashboard.py` is a single-file local web app (standard library `http.server`, no framework) on `http://127.0.0.1:8765`:

- **Batch queue:** paste up to 50 links, one per line. A worker thread runs them one at a time through `main.py`, since free-tier quota is the bottleneck, not CPU.
- **Crash-safe queue:** pending links are written to `cola.json` (write-then-rename) on every change. On restart the queue resumes and skips any video that already has a report, so no quota is spent twice.
- **Report browser:** every report as a card, with search, category filter and a reader view.

---

## Quickstart

```bash
pip install -r requirements.txt
```

The LLM chain lives in the sibling `jobHunter/` folder (`jobHunter/llm_chain.py`). If it is elsewhere, set `JOBHUNTER_DIR`. API keys go in `jobHunter/.env`; any provider without a key is skipped:

| Variable | Provider |
|---|---|
| `GEMINI_API_KEY` | Google Gemini ([AI Studio](https://aistudio.google.com/apikey)) |
| `GROQ_API_KEY` | Groq |
| `OPENROUTER_API_KEY` | OpenRouter (free models) |
| `NVIDIA_API_KEY` | NVIDIA build.nvidia.com |
| `MISTRAL_API_KEY` | Mistral |

NVIDIA and Mistral's free tiers log or train on prompts, so `llm_chain.py` only uses them when the caller opts in. This project opts in (`LLM_ALLOW_LOGGED_PROVIDERS=1`) because its input is public transcripts; jobHunter, which sends CV data, does not.

```bash
# One video, by URL or by search term
python main.py "https://www.youtube.com/watch?v=VIDEO_ID"
python main.py "docker compose tutorial"

# Dashboard (opens in the browser)
python dashboard.py
```

---

## Project Layout

| File | Role |
|---|---|
| `main.py` | Pipeline: fetch, 4 phases, classification, output |
| `tools.py` | LangChain tools: video ID parsing, transcript and metadata fetch, YouTube search |
| `dashboard.py` / `dashboard.html` | Local dashboard, batch queue and report browser |
| `.cache/` | Metadata and transcript per video ID, so re-runs skip the download (not committed) |
| `Results/` | Generated reports by category (not committed) |

## Tech Stack

Python · LangChain Core · Pydantic · yt-dlp · youtube-transcript-api · Gemini, Groq, NVIDIA, Mistral, OpenRouter (free tiers) · standard library HTTP server

## Known Limits

- Needs captions on the video; videos without a transcript are reported as errors.
- The language detector is a word-frequency heuristic for Spanish and English; other languages come out as "mixed".
- Token counts in the run summary are estimates (characters / 4), not provider-reported usage.
- If the dashboard dies mid-video, that one video is processed again on restart.
