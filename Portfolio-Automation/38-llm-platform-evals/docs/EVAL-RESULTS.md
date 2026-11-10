# RAG Evaluation Results — Kubernetes Concepts Assistant

Run of 2026-11-09 and 2026-11-10 against the protocol in [`EVALS.md`](EVALS.md), which was frozen before any run.

**Outcome: the assistant meets three of the five pre-registered thresholds and misses two. By the protocol it does not pass the quality gate.**

## Result

| Metric | Threshold | Test split, 3 passes | Verdict | Dev split, 1 pass |
|---|---|---|---|---|
| Retrieval Hit@5 | ≥ 0.85 | 0.938 (90 of 96) | Pass | 0.95 (19 of 20) |
| Key-fact correctness | ≥ 0.75 | 0.708 (68 of 96) | **Fail** | 0.75 (15 of 20) |
| Refusal rate on unanswerable questions | ≥ 0.90 | 1.000 (24 of 24) | Pass | 1.00 (10 of 10) |
| False refusal rate on answerable questions | ≤ 0.10 | 0.125 (12 of 96) | **Fail** | 0.05 (1 of 20) |
| Citation validity | = 1.00 | 1.000 (120 of 120) | Pass, with the limit described below | 1.00 (30 of 30) |

- Mean, minimum and maximum are the same number for every metric: the three passes scored identically. 116 of the 120 questions got the same answer text in all three passes. The other four changed wording without changing a metric.
- 360 answers, none failed or timed out, all produced by the pinned model.
- Key-fact correctness missed the threshold by 4 questions (72 of 96 were needed). The false refusal rate exceeded it by 3 (at most 9 of 96 were allowed).
- Median answer time was 44 seconds, the slowest answer took 112 seconds, and the run lasted 4 hours 53 minutes.

Files: [`evals/baseline.json`](../evals/baseline.json) is the report of the test split. [`evals/baseline_answers.jsonl`](../evals/baseline_answers.jsonl) holds every answer with the chunks the server attached, the model that answered and the time it took. [`evals/dev.json`](../evals/dev.json) and [`evals/dev_answers.jsonl`](../evals/dev_answers.jsonl) are the same for the dev split.

## What Was Evaluated

| Part | Setting |
|---|---|
| Corpus | 187 Markdown files from `kubernetes/website`, `content/en/docs/concepts`, commit `7fde177e22dc98390a6d55d215dd0301b5f6d0bb` |
| Retrieval | Open WebUI `0.5.18`, collection `k8s-concepts`, chunks of 1,000 characters with 100 of overlap, embeddings `sentence-transformers/all-MiniLM-L6-v2`, top 5 chunks, no hybrid search, no reranker, default RAG template. The retrieval query is the question itself: query rewriting is off |
| Gateway | LiteLLM `main-v1.59.8`, model group `primary-model` |
| Model | Ollama `0.33.3`, `qwen3:4b-instruct-2507-q4_K_M` (digest `0edcdef34593`), temperature 0, seed 42, context of 4,096 tokens |
| Hardware | NVIDIA GTX 1050 with 4 GB, see [`HARDWARE.md`](HARDWARE.md) |
| Questions | 150 in [`evals/golden.jsonl`](../evals/golden.jsonl). Dev: 30 (20 answerable, 10 not). Test: 120 (96 answerable, 24 not) |

## Decisions Taken Before the Test Split Ran

All of them are in the commit that adds `evals/dev.json`, which was pushed before the test run started. The git history shows the order.

1. **System prompt.** "Answer only from the provided context, in at most three sentences. Cite the sources you use inline as [source_id], with the source_id values given in the context and no others. If the context does not contain the answer, reply exactly: I don't know based on the provided documentation." The three-sentence limit keeps an answer near 40 seconds on a 4 GB GPU. The dev run with this prompt met all five thresholds, so the prompt was frozen without further tuning.
2. **What a citation points to.** Open WebUI `0.5.18` gives one source id to each attached item, and the collection is one item ([FINDING-004](FINDINGS.md)). Every chunk reaches the model as source `0`. The runner maps `[0]` to the documents the server reported under that id and then applies the rule of the protocol: the citation is valid when the id exists and those documents are among the top 5 sources and in the corpus.
3. **How sources are read.** The API reports them only in a stream and only for a named item ([FINDING-005](FINDINGS.md)), so the runner streams the answer.
4. **Pinned-model guard.** The gateway has a fallback to a different model. An answer that comes from any model other than the pinned one is recorded as an error, not as an answer. None occurred.
5. **Gateway timeout.** 180 seconds instead of 30 for the Ollama deployments, because a RAG answer takes between 30 and 112 seconds on this hardware.
6. **No LLM judge.** Section 5 of the protocol allows a faithfulness judge only after calibration against 40 human labels. No judge was calibrated, so the scores rest on the regex key facts and the retrieval metrics alone.

### What citation validity measures here

Under the mapping above the metric can catch two things: a source id that the server never gave, and an answer that cites documents outside the ranking the evaluation scored. No answer did either. It cannot say whether an answer cites the right document, because this version does not let the model point at one.

81 of the 96 answerable questions were answered with `[0]` and 12 were refusals. The other 3 wrote the placeholder itself, `[source_id]` or `[source_id:0]`, which the runner does not read as a citation.

In 9 of the 120 questions the chat attached a document outside the top five documents of the evaluation's own query. Both use the same approximate search with a different k ([FINDING-006](FINDINGS.md)). All 9 answers were refusals, so they carried no citation to check.

## Why Two Thresholds Fail

This section was written after reading the test results. It changes no score.

[`scripts/retrieval_check.py`](../scripts/retrieval_check.py) repeats the retrieval query of each answerable test question with k=5 and with k=200, and compares both with the chunks the server attached during the run. Its output is [`evals/retrieval_check.json`](../evals/retrieval_check.json). The wide query returned the same first five chunks in all 96 questions on two separate restarts of the stack, so it is used as the reference.

| What reached the model | Questions | Correct | Incomplete | Refused |
|---|---|---|---|---|
| Every key fact was in the five chunks | 66 | 60 | 4 | 2 |
| The right document, but a key fact was not in the five chunks | 8 | 0 | 7 | 1 |
| No chunk of the gold document, and the wide query finds none in its top five either | 6 | 1 | 2 | 3 |
| No chunk of the gold document, although the wide query ranks one in its top five | 5 | 0 | 0 | 5 |
| A chunk of the gold document, next to chunks that differ from the wide query | 11 | 7 | 3 | 1 |
| **Total** | **96** | **68** | **16** | **12** |

"Incomplete" is an answer that misses at least one key fact and is not a refusal.

- **The model does its part when the context is right.** With every key fact in the five chunks it answered correctly 60 times out of 66.
- **Most misses start in retrieval.** In 18 of the 28 misses the passage with the answer did not reach the model: the right document without the key fact (8), no gold chunk at all (5), or a gold chunk that the search dropped (5).
- **Most false refusals are correct behaviour on a wrong context.** 9 of the 12 happened in those 18 questions. The model declined as instructed. The protocol counts them because the corpus does hold the answer.
- **The vector search is approximate and it costs answers.** The five chunks of the run matched the first five of the wide query in 79 of the 96 questions ([FINDING-006](FINDINGS.md)). In those 79, key-fact correctness was 61 of 79 (0.77) and the false refusal rate 5 of 79 (0.06). In the other 17 they were 7 of 17 (0.41) and 7 of 17 (0.41). This split was made after the fact and the second group is small. It points to the search as the main reason for both misses. It does not show that the assistant would pass with an exact search.
- **The key is strict, but not enough to change the verdict.** One incomplete answer is correct in other words: `GOLD-057` says "CRDs (Custom Resource Definitions)" and the key wants `CustomResourceDefinition`. Two more are arguable (`GOLD-009`, `GOLD-047`). Counting all three gives 71 of 96, which is 0.74 and still under the threshold. The rest are real omissions, such as two of three taint effects in `GOLD-149`.

## What Would Change the Result

None of this was tried. The test split has now been read, so a change motivated by this analysis needs a new test split to be judged fairly. The committed baseline only serves as a regression gate.

1. Ask the vector store for more neighbours than needed and keep the best five, or use an exact search. This addresses the 5 questions where the search dropped the gold chunk.
2. Change the chunking. Chunks of 1,000 characters split lists and tables, and 8 questions had the right document without the fact.
3. Add a reranker or a stronger embedding model for the 6 questions with no gold chunk.

## Limits

- One model, one machine, one corpus. With 96 answerable questions, one question moves a metric by about 0.01.
- Key facts are regular expressions. They can reject a correct answer that uses other words, so key-fact correctness is a lower bound.
- The three passes share the seed and run at temperature 0. They measure whether the pipeline repeats itself, and it did. They do not measure sampling variance.
- Retrieval depends on the state of the vector index. After a restart of the stack, the same query returned different chunks for about 10 of the 96 questions ([FINDING-006](FINDINGS.md)). A rerun can therefore move Hit@5 and the metrics after it by a few questions, which is close to the regression tolerance of 0.03.
- Hit@5 was measured with the same approximate search, taking the first five distinct documents of a k=20 query. With the wide query it is 93 of 96.
- Citation validity is limited as described above.

## How to Reproduce

On the homelab host, with the stack up and the corpus ingested (see the README):

```bash
# Test split, three passes, compared with the committed baseline
uv run python -m evals.run --split test --baseline evals/baseline.json

# Retrieval check of the committed run, read from the committed files (no stack needed)
uv run python -m scripts.retrieval_check --answers evals/baseline_answers.jsonl --out evals/retrieval_check.json
```
