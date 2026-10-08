# HealthAI Project: Executive Summary, User Flow, and Architecture

---

## 1. Project Overview
HealthAI is an AI-powered clinical triage system. It guides users through symptom assessment, asks adaptive follow-up questions, and classifies risk (HomeCare/Urgent/Emergency) with explanations and recommendations. The system combines a FastAPI backend, React frontend, ML models (XGBoost, Random Forest), and the Gemini API for advanced reasoning.

---

## 2. User Flow (Step-by-Step)

1. **User visits the triage page** and enters their chief complaint (e.g., "I have a fever and cough").
2. **Frontend sends** this input to `/api/triage/start`.
3. **Backend extracts symptoms** using NLP (Gemini API or fallback logic).
   - **Fallback logic:** If Gemini API is unavailable, the backend uses a rule-based keyword matching approach. It loads a pre-built knowledge graph (from the dataset and clinical expertise) containing canonical symptom keys and their synonyms. The user's input is scanned for any of these phrases, mapping matches to canonical symptoms. This ensures robust extraction even without advanced NLP.
   - **Knowledge graph:** This is a static resource, not built on-the-fly. It is constructed from the dataset (Final_Augmented_dataset_Diseases_and_Symptoms.csv) and domain knowledge, mapping all possible ways a user might describe a symptom to a standard key. User input is chunked and matched against this graph for synonym-aware extraction.
4. **Backend selects the most relevant follow-up question** using adaptive logic and knowledge graph.
5. **Frontend displays the question**; user answers.
6. **Frontend sends answer** to `/api/triage/answer`.
7. **Backend records answer, updates context, and checks for crisis/guardrails** (e.g., red-flag symptoms).
8. **If more info is needed, backend selects next question**; loop continues (steps 5–8) until enough data is gathered or a crisis is detected.
9. **When complete, backend classifies risk** (using Gemini API, XGBoost, or heuristics) and generates a confidence score and explanation.
10. **Frontend displays the result** (risk label, confidence, explanation, recommended action).

---

## 3. Application Architecture

### High-Level Diagram (Text)

```
[User]
  |
  v
[React Frontend]
  |
  v
[API Client (axios)]
  |
  v
[FastAPI Backend]
  |      |         |         |         |
  |   [NLP]   [Adaptive] [Risk]   [Guardrails]
  |   Engine   Engine    Classifier  Module
  |      |         |         |         |
  |   [Gemini API] [Knowledge Graph] [ML Models]
  |
[Database (SQLite/Postgres)]
```

### Component Roles
- **Frontend:** UI, collects user input, displays questions/results, manages session state.
- **API Client:** Handles HTTP requests to backend endpoints.
- **Backend:**
  - **NLP Engine:** Extracts symptoms from free text (Gemini API or fallback).
  - **Adaptive Engine:** Selects next question based on symptoms, answers, and knowledge graph.
  - **Risk Classifier:** Classifies risk using Gemini API, XGBoost, or heuristics; computes confidence.
  - **Guardrails:** Detects crisis/red-flag situations and interrupts flow if needed.
  - **Database:** Stores sessions, answers, results, and logs.
- **ML Models:**
  - **XGBoost:** Triage risk classification (tabular, class-weighted for emergencies).
  - **Random Forest:** Disease prediction (high-dimensional, interpretable).
  - **Gemini API:** Advanced NLP and reasoning.

---

## 4. Concepts & Technologies Used
- **Adaptive Questioning:** Bayesian/context-aware selection, no repeats, only relevant questions.
- **NLP:** Symptom extraction from user text (Gemini API, fallback rules).
- **ML Models:** XGBoost (triage), Random Forest (disease), class weighting for rare/critical classes.
- **Confidence Scoring:** Based on AI/heuristics, higher when data is clear, lower if ambiguous.
- **Guardrails:** Crisis detection (e.g., red-flag symptoms, immediate escalation).
- **Async/Scalable Backend:** FastAPI, async DB, efficient for concurrent users.
- **Automated Testing:** End-to-end and unit tests for extraction, flow, efficiency, and correctness.
---
## 5. Verification & Efficiency
- **Automated tests** for symptom extraction, question flow, crisis detection, classification, and speed.
- **Model metrics:**
  - Triage (XGBoost): ~0.95 ROC-AUC, ~0.90–0.95 Emergency recall, ~0.85–0.90 accuracy.
  - Disease (Random Forest): ~0.82 Top-1, ~0.92 Top-3, ~0.96 Top-5 accuracy.
- **Efficiency:**
  - <2s per triage session in tests.
  - No repeated/irrelevant questions.
  - High recall for emergencies.

---
## 6. Flaws & Improvements
- **Flaws:**
  - Relies on quality of symptom extraction and knowledge graph.
  - May miss rare/ambiguous cases.
  - UI is minimal.
- **Improvements:**
  - Expand clinical guardrails and explanations.
  - Add more real-world data and user feedback.
  - Enhance UI/UX for accessibility.
  - Update to latest FastAPI/Pydantic.
  - Integrate more advanced LLMs for reasoning.

---

*This file provides a concise but detailed summary of HealthAI’s modules, workflow, architecture, concepts, verification, and future directions.*
