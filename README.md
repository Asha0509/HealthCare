# 🏥 HealthAI - AI-Powered Healthcare Triage System

> **⚠️ Medical Disclaimer**: This is a demo/educational project and is NOT a substitute for professional medical advice. In an emergency, call **112** immediately.

An AI-powered healthcare triage system that uses Google's Gemini API for intelligent symptom analysis. Describe your symptoms in natural language; the system extracts symptoms, asks smart follow-up questions, and provides an **Emergency / Urgent / Home Care** triage recommendation with explanations and nearby hospital suggestions.

---

## 📊 Dataset & ML Model

### Medical Symptoms-Diseases Dataset
This project includes a comprehensive medical dataset for disease prediction:

| Metric | Value |
|---|---|
| **Total Samples** | 246,945 |
| **Symptom Features** | 377 |
| **Disease Classes** | 721 |
| **Dataset File** | `Final_Augmented_dataset_Diseases_and_Symptoms.csv` |

### Trained ML Model
A Random Forest classifier trained on the dataset:

| Metric | Value |
|---|---|
| **Model Type** | Random Forest Classifier |
| **Training Samples** | 197,458 |
| **Test Samples** | 49,365 |
| **Top-1 Accuracy** | 68.71% |
| **Top-3 Accuracy** | 79.01% |
| **Top-5 Accuracy** | 82.67% |

**Top Predictive Symptoms:**
1. Cough (2.1%)
2. Shortness of breath (1.9%)
3. Sharp abdominal pain (1.5%)
4. Emotional symptoms (1.5%)
5. Depressive/psychotic symptoms (1.4%)

### Training the Model

```bash
cd Health
python models/disease_classifier.py
```

**Output files** (saved to `models/models/`):
- `disease_model.pkl` - Trained Random Forest model
- `disease_label_encoder.pkl` - Label encoder for diseases
- `symptom_columns.json` - Feature column names
- `disease_model_metadata.json` - Training metadata & metrics

---

## 🧠 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite |
| Backend | FastAPI, Pydantic, Uvicorn |
| AI/NLP | Google Gemini 2.0 Flash API |
| ML Model | Random Forest (scikit-learn) |
| Database | SQLite (aiosqlite) |
| Sessions | In-memory storage |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Google Gemini API Key (get one at https://aistudio.google.com/apikey)

### 1. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv ../.venv
..\.venv\Scripts\Activate.ps1  # Windows
# source ../.venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Create .env file with your Gemini API key
echo "GEMINI_API_KEY=your_api_key_here" > .env

# Start the server
python main.py
# API runs at http://localhost:8000
```

### 2. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# UI runs at http://localhost:5173
```

---

## 📁 Project Structure

```
Health/
├── Final_Augmented_dataset_Diseases_and_Symptoms.csv  # Medical dataset (246K samples)
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── .env                       # GEMINI_API_KEY goes here
│   ├── api/
│   │   ├── triage.py              # Core triage pipeline
│   │   └── hospitals.py           # Hospital recommendations
│   ├── services/
│   │   ├── nlp_engine.py          # Gemini-based symptom extraction
│   │   ├── safety_guardrails.py   # Crisis detection
│   │   ├── adaptive_engine.py     # Smart follow-up questions
│   │   ├── risk_classifier.py     # Gemini-based triage classification
│   │   └── patient_context.py     # Session management
│   ├── core/                      # Config, logging
│   ├── db/                        # SQLite database
│   └── schemas/                   # Pydantic models
├── frontend/
│   └── src/
│       ├── pages/                 # Triage, Result, Landing
│       ├── components/            # Navbar
│       └── api/                   # API client
├── data/
│   └── symptom_disease_graph.json # Knowledge graph
└── models/
    ├── train_classifier.py        # XGBoost triage classifier training
    ├── disease_classifier.py      # Disease prediction model training
    └── models/
        ├── disease_model.pkl              # Trained Random Forest model
        ├── disease_label_encoder.pkl      # Disease label encoder
        ├── symptom_columns.json           # 377 symptom feature names
        ├── disease_model_metadata.json    # Training metrics & config
        ├── triage_xgb.pkl                 # XGBoost triage model
        └── feature_columns.json           # Triage feature columns
```

---

## 🔑 Key Features

### Gemini-Powered Intelligence
- **Symptom Extraction**: Gemini analyzes natural language to identify symptoms
- **Smart Triage**: AI evaluates symptoms, duration, severity, age, and gender
- **Adaptive Questions**: Filters out redundant questions based on user input
- **Location-Aware Hospitals**: Suggests real hospitals based on user location

### Safety Features
- **Crisis Detection**: Identifies mental health emergencies with helpline info
- **Medical Disclaimers**: Clear warnings that this is not medical advice

### User Experience
- Demographics collected upfront (age, gender)
- Chat-based symptom input
- Voice input support
- Progress tracking
- Confidence scores and explanations

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/triage/start` | POST | Begin triage session |
| `/api/triage/answer` | POST | Submit follow-up answer |
| `/api/triage/result/{id}` | GET | Get completed result |
| `/api/hospitals/nearby` | GET | Hospital recommendations |
| `/health` | GET | Health check |
| `/api/docs` | GET | Swagger UI |

---

## 🔧 Configuration

Create `backend/.env` with:

```env
GEMINI_API_KEY=your_gemini_api_key
```

---

## 📝 License

This project is for educational/demo purposes only.
