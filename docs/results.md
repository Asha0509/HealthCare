# Results

What the 60-case evaluation measured, how the safety-rules baseline performs, and what has not been measured. Every figure below comes from `evals/results/rules.json` (the only results file in the repository), from the test suite, or from git history.

> **Not a medical device.** The expected levels were written by the project author from public triage guidance. They are **not clinically validated**. Sixty cases are enough to catch regressions and compare designs, not to claim clinical accuracy.

Related: [architecture.md](architecture.md), [HLD.md](HLD.md), [LLD.md](LLD.md), [errorlog.md](errorlog.md).

## 1. Setup (read this before the numbers)

| Item | Value |
|---|---|
| Cases | 60 in `evals/cases.jsonl`: 20 HomeCare, 20 Urgent, 20 Emergency |
| Case tags | 37 `judgement` (worded without textbook keywords), 14 `red_flag_text`, 7 `red_flag_answer`, 2 `red_flag_age` (23 red-flag cases in all) |
| Labels | Written by the author with a one-line rationale per case; not reviewed by a clinician |
| Pipeline measured | **Rules only**: `python evals/run_eval.py --pipeline rules`. The request goes through the real `POST /api/triage/assess` route in process with `use_llm=false`. Symptom extraction and assessment use the keyword fallback and the red-flag rules; no model is called (`avg_llm_calls` is 0.0, `providers` is empty) |
| Recorded in file | `run_at` 2026-10-07T09:55:56+00:00, target `in-process`, 60 cases, 0 errored |
| Reproduced | The run was repeated for this write-up on 2026-10-08, writing to a scratch path outside the repository. Accuracy, macro-F1, emergency recall, under- and over-triage, critical misses and the full confusion matrix were identical |
| Tests | 135 passed (`cd backend && python -m pytest`) |

**Metric definitions** (from `evals/run_eval.py`):

- **Critical miss** (a "missed emergency"): an Emergency case answered HomeCare. This is the headline safety metric.
- **Emergency recall**: share of Emergency cases answered Emergency. A case answered Urgent counts against recall but is not a critical miss.
- **Under-triage rate**: share of all cases given a level lower than expected. **Over-triage rate**: higher than expected.
- **Gates** (CI fails if violated): rules pipeline, over the `red_flag_*` cases only, zero critical misses and emergency recall 1.0; agent pipeline, over all cases, zero critical misses and emergency recall at least 0.9.

## 2. What the baseline is

The comparison point is the **rules-only pipeline**: the deterministic red-flag rules and the rule-based assessment from the symptom graph, with no language model. It is the system's own fallback path, so the numbers also describe what a person gets when no AI provider is reachable.

The project has no earlier measured baseline. The first version of the app displayed a made-up confidence percentage and was never evaluated; the Random Forest and XGBoost experiments under `models/` solve different problems (see section 7) and are not baselines for triage levels.

## 3. Rules-only results

| Metric | Value |
|---|---|
| Cases / errors | 60 / 0 |
| Accuracy (exact level) | 73.3% (0.733) |
| Macro-F1 | 0.723 |
| **Emergency recall, all 20 Emergency cases** | **85% (17 of 20)** |
| **Emergency recall, red-flag cases only** | **100% (17 of 17), 0 misses** |
| **Critical misses (Emergency told HomeCare)** | **2** (`e18`, `e20`, both `judgement`) |
| Under-triage rate | 25% (15 of 60) |
| Over-triage rate | 1.7% (1 of 60) |
| Cases raised by a safety rule | 19 |
| Fallback rate | 98.3% (59 of 60; the exception is the self-harm case, which takes the safety-rule path by design) |
| Per-case latency p50 / p95 | 1 ms / 1 ms (no network) |

Per class:

| Expected level | Precision | Recall | F1 | Cases |
|---|---|---|---|---|
| HomeCare | 0.576 | 0.95 | 0.717 | 20 |
| Urgent | 0.800 | 0.40 | 0.533 | 20 |
| Emergency | 1.000 | 0.85 | 0.919 | 20 |

Confusion matrix (rows are expected, columns are given):

| | HomeCare | Urgent | Emergency |
|---|---|---|---|
| **HomeCare** | 19 | 1 | 0 |
| **Urgent** | 12 | 8 | 0 |
| **Emergency** | 2 | 1 | 17 |

By tag:

| Tag | Cases | Accuracy |
|---|---|---|
| `red_flag_text` | 14 | 100% |
| `red_flag_answer` | 7 | 100% |
| `red_flag_age` | 2 | 100% |
| `judgement` | 37 | 56.8% |

## 4. How to read it

- **The safety rules do their job on textbook wording.** All 23 red-flag cases are classified correctly and none of the 17 red-flag emergencies is missed. The gate on this subset is why CI is green.
- **The rules alone are not enough.** Three Emergency cases were not caught, and all three are worded without textbook signs:
  - `e18`: "My father is 70 and suddenly can't lift his right arm and his words are all jumbled" (stroke) was told HomeCare.
  - `e20`: "My throat feels like it is closing up after a bee sting and my voice is hoarse" (anaphylaxis) was told HomeCare.
  - `e19`: "Severe tearing pain in my chest that goes through to my back" (possible aortic dissection) was told Urgent, not Emergency.
  - The first two are the 2 critical misses. `e19` lowers recall to 85% but is not a critical miss.
- **Urgent is the weak class.** 12 of 20 Urgent cases (for example a four-day fever of 39 C, burning urination with fever and back pain, a four-week cough with weight loss) were told HomeCare. These cases have no emergency flag and the symptom-graph fallback defaults them to home care. This accounts for 12 of the 15 under-triaged cases and is the largest quality gap in the baseline.
- **Over-triage is small**: one HomeCare case (`h18`, mild palpitations after coffee) was told Urgent.
- **Latency is not informative** for the baseline: it measures regular expressions, not network calls.

## 5. Comparison: rules only versus the agent

| Pipeline | Cases | Accuracy | Emergency recall | Critical misses | Under-triage | Status |
|---|---|---|---|---|---|---|
| Rules only (no AI) | 60 | 73.3% | 85% | 2 | 25% | Measured, `evals/results/rules.json` |
| AI agent + safety rules | 60 | not measured | not measured | not measured | not measured | No results file exists |
| Optional decision model second opinion | 60 | not measured | not measured | not measured | not measured | No results file exists |

**No agent numbers are claimed.** `evals/run_eval.py --pipeline agent` exists and is gated in CI when a model key secret is configured (zero critical misses and 90% emergency recall over all 60 cases), but this repository holds no agent result, and the README states that the optional decision model has not been evaluated. `evals/decision_eval.py` is written and tested for the conformal maths, but no endpoint was run against the 60 cases, so there is no `evals/results/decision.json`.

What can be said without a measurement is limited to design intent: the agent is the part meant to address the three `judgement` emergencies and the Urgent class; the safety merge guarantees it cannot make any rules-only emergency result lower. Whether it actually improves recall or Urgent accuracy is the open question.

## 6. Changes in the baseline over time

The rules results file has been committed twice. The difference between the two runs is a bug fix, not tuning on the test set:

| Commit | What changed | Accuracy | Emergency recall | Critical misses | Under-triage |
|---|---|---|---|---|---|
| `b99950c` (eval harness added) | First recorded run | 71.7% | 85% | 2 | 25% |
| `f1649cc` (negation in symptom extraction) | `h11` "Acid reflux after a heavy dinner, no chest pain" no longer carries the negated symptom through extraction and goes from Urgent to HomeCare | 73.3% | 85% | 2 | 25% |

Just before the harness was committed, `adfdf6c` fixed two red-flag misses (its message says they were found by the eval) ("thoughts of ending my life" was not treated as a crisis; "no chest pain" after a heavy dinner fired the heart-attack rule). See [errorlog.md](errorlog.md).

## 7. The earlier model experiments (not comparable)

- `models/disease_classifier.py` trained a Random Forest on a public symptom-to-disease dataset. Saved metadata: top-1 0.687, top-3 0.790, top-5 0.827 accuracy over 721 disease classes (49,365 test rows). It predicts **diseases**, not triage levels, so it cannot be compared with the table above, and it is not used by the live app.
- `models/train_classifier.py` trains an XGBoost 3-class triage model on a synthetic dataset generated from random draws. No metrics are stored in the repository.

Neither experiment ran on the 60 cases.

## 8. What did not work

- **Rules alone miss judgement cases.** Three of 20 emergencies are not escalated to Emergency, two of them told to stay home. The rules were never meant to read indirect wording; this is the reason the agent exists and why the agent eval gates on zero missed emergencies.
- **Rules alone under-triage Urgent cases.** Recall 40% on Urgent; 12 of 20 told HomeCare. Nothing in the fallback path knows about a four-day fever or a chronic cough with weight loss.
- **The agent has no measured result.** It has been built, unit-tested against a scripted fake provider (12 agent tests), and put behind a CI gate that only runs with a key. That is not evidence of accuracy.
- **The decision model has no measured result.** The conformal procedure is tested for correctness, but no model endpoint was available to calibrate or evaluate. With 60 calibration cases the quantile would be coarse even if one were.
- **The earlier confidence number.** The first version showed a percentage from `random.uniform(0.79, 0.89)`. It was removed; a probability is shown only when a model supplied it.
- **Earlier work with a small distilled student model** was reported in the README as too weak to use on its own. That work is not in this repository, so it cannot be re-checked here.
- **Free-tier model ids and prompts drifted.** Retired Llama ids stopped serving and the defaults moved to gpt-oss; a prompt example leaked a spurious "fever" symptom; model-written action text once included "911". None of these is covered by an eval case, which is a gap in the eval itself: it does not check the action text or the extracted symptoms. See [errorlog.md](errorlog.md).

## 9. Limitations

- Labels are author-written and unreviewed by a clinician; 60 cases; one author's idea of which wording is "textbook" and which is "judgement".
- The set is balanced 20/20/20, which does not reflect real case mix. Accuracy on a real population would differ.
- The rules baseline was shaped by this same set: the tags `red_flag_*` mark cases written to be catchable by rules, and rules were adjusted after the eval exposed misses (section 6). Treat the 100% on red-flag cases as a regression check, not a generalisation estimate.
- No confidence intervals. With 20 cases per class a single case moves a class metric by 5 percentage points.
- Latency figures are for the rules path only.
- The Evals page and tour describe the expected levels as what "a careful clinician would" choose; the labels in fact come from the author, as stated here and in the README.
- Nothing here measures harm, calibration of any probability, or performance across languages, age groups beyond two age cases, or accents and spellings.
- The decision model and the agent remain unevaluated; do not infer from this document that either improves on the baseline.

## 10. Reproduce

```bash
cd backend
python -m pytest                                   # 135 tests, no network
python ../evals/run_eval.py --pipeline rules --gate --out /tmp/rules.json
# agent pipeline, needs GROQ_API_KEY or NVIDIA_NIM_API_KEY:
python ../evals/run_eval.py --pipeline agent --delay 2 --out /tmp/agent.json
```

Pass `--out` to keep the committed `evals/results/*.json` unchanged while experimenting. The published Evals page reads whatever is in `evals/results/`.
