# Pre-Registered Evaluation Protocol — Internal Knowledge Assistant (Kubernetes Concepts)

*** PRE-REGISTRATION NOTICE: THIS PROTOCOL WAS FROZEN PRIOR TO RUNNING EVALUATIONS ON THE TEST SET. THIS DOCUMENT DEFINES METHODOLOGY, DATASET PARTITIONS, METRIC FORMULAS, AND QUALITY GATES. IT CONTAINS NO EMPIRICAL RESULTS. ***

---

## 1. Corpus Specification & Pinned Source

The retrieval knowledge base is sourced from the official Kubernetes documentation repository:
- **Repository:** `kubernetes/website` (`https://github.com/kubernetes/website`)
- **Pinned Git Commit:** `7fde177e22dc98390a6d55d215dd0301b5f6d0bb`
- **Subdirectory Scope:** `content/en/docs/concepts` (architectural and operational concepts of Kubernetes)
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Ingestion Pre-processing:** Converted to Markdown documents, cataloged with relative path identifiers, and indexed into Open WebUI knowledge collection `k8s-concepts`.

---

## 2. Golden Question Dataset Partitioning

The evaluation dataset comprises exactly **150 questions** formatted as JSON Lines (`evals/golden.jsonl`):

```text
Total Questions: 150
├── Dev Split: 30 questions (allowed exclusively for prompt tuning, chunk size calibration, or system prompt refinement)
└── Test Split: 120 questions (strictly frozen; never inspected or tuned against)
    ├── Answerable: 96 questions (ground truth document path and 1–3 required key fact regexes provided)
    └── Unanswerable: 24 questions (out-of-scope or unanswerable queries requiring explicit assistant refusal)
```

### Item Schema
Each item in `evals/golden.jsonl` adheres to the following JSON structure:
- `id`: Unique string identifier (e.g. `"GOLD-001"`)
- `split`: `"dev"` or `"test"`
- `question`: Natural language inquiry about Kubernetes concepts
- `answerable`: Boolean (`true` for questions answerable from corpus, `false` otherwise)
- `gold_doc_paths`: List of relative document paths containing the definitive ground truth
- `key_fact_regexes`: List of 1–3 compiled regular expressions validating necessary semantic components in the answer

---

## 3. Evaluation Metrics and Mathematical Formulas

Let $Q_{\text{ans}}$ denote the set of answerable test questions ($|Q_{\text{ans}}| = 96$), $Q_{\text{unans}}$ denote the set of unanswerable test questions ($|Q_{\text{unans}}| = 24$), and $Q = Q_{\text{ans}} \cup Q_{\text{unans}}$ ($|Q| = 120$).

### 3.1 Retrieval Hit@5
Measures whether at least one ground-truth gold document appears in the top 5 documents returned by the retriever:

$$\text{Hit@5} = \frac{1}{|Q_{\text{ans}}|} \sum_{q \in Q_{\text{ans}}} \mathbb{I}\Big(\exists d \in \text{gold\_doc\_paths}(q) : d \in \text{top\_5\_sources}(q)\Big)$$

- **Pre-registered Threshold:** $\ge 0.85$

### 3.2 Key-Fact Correctness (KFC)
Measures the proportion of answerable questions whose generated response satisfies all pre-registered key fact regexes:

$$\text{KFC} = \frac{1}{|Q_{\text{ans}}|} \sum_{q \in Q_{\text{ans}}} \prod_{r \in \text{regexes}(q)} \mathbb{I}\Big(r \text{ matches } \text{answer}(q)\Big)$$

- **Pre-registered Threshold:** $\ge 0.75$

### 3.3 Refusal Rate (RR) on Unanswerable Queries
Measures the assistant's ability to decline answering questions outside the scope of the knowledge corpus:

$$\text{RR} = \frac{1}{|Q_{\text{unans}}|} \sum_{q \in Q_{\text{unans}}} \mathbb{I}\Big(\text{is\_refusal}(\text{answer}(q))\Big)$$

- **Pre-registered Threshold:** $\ge 0.90$

### 3.4 False Refusal Rate (FRR) on Answerable Queries
Measures the proportion of legitimate, answerable queries erroneously declined by the assistant:

$$\text{FRR} = \frac{1}{|Q_{\text{ans}}|} \sum_{q \in Q_{\text{ans}}} \mathbb{I}\Big(\text{is\_refusal}(\text{answer}(q))\Big)$$

- **Pre-registered Threshold:** $\le 0.10$

### 3.5 Citation Validity (CV)
Measures the accuracy and hallucination-free nature of all cited sources in the generated answer:

$$\text{CV} = \frac{1}{|Q|} \sum_{q \in Q} \mathbb{I}\Big(\forall c \in \text{citations}(q) : c \in \text{top\_sources}(q) \wedge c \in \text{CorpusPaths}\Big)$$

- **Pre-registered Threshold:** $= 1.00$ (100% of generated citations must correspond to valid corpus files)

---

## 4. Execution Protocol & Stability Standards

1. **Deterministic Hyperparameters:**
   - Inference Temperature: $T = 0.0$
   - Random Seed: $\text{Seed} = 42$
   - Context Window: 4096 tokens
2. **Repetition and Variance:**
   - Every evaluation run consists of **3 full passes** over the 120-item test split.
   - For every metric $M$, the evaluation report records the mean $\bar{M}$, minimum $M_{\min}$, and maximum $M_{\max}$.
3. **CI Regression Gate:**
   - The continuous integration gate automatically fails if any metric mean in the test split falls more than **0.03** below the committed baseline:
     $$\Delta M = M_{\text{baseline}} - \bar{M}_{\text{current}} > 0.03 \implies \text{FAIL}$$

---

## 5. LLM Judge Calibration Rule (Faithfulness)

An automated LLM judge may be used to assess answer faithfulness (whether every factual claim is strictly supported by the retrieved context) **only if** calibrated against human annotations:
- **Calibration Set:** 40 randomly sampled answer-context pairs labeled manually by human reviewer.
- **Agreement Metric:** Cohen's kappa coefficient ($\kappa$):
  $$\kappa = \frac{p_o - p_e}{1 - p_e}$$
  where $p_o$ is observed relative agreement and $p_e$ is the hypothetical probability of chance agreement.
- **Acceptance Gate:**
  - If $\kappa \ge 0.60$: The judge is accepted for automated evaluation, and its cost must remain $\le \$0.50$ USD per run.
  - If $\kappa < 0.60$: The judge is rejected and excluded from automated scoring, and the evaluation relies solely on deterministic ground truth regexes and retrieval metrics.
