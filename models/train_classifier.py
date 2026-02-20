"""
XGBoost Triage Classifier — Training Script
--------------------------------------------
Generates a synthetic dataset and trains XGBoost for 3-class triage:
  0 = HomeCare | 1 = Urgent | 2 = Emergency

Run: python train_classifier.py
Outputs: models/triage_xgb.pkl, models/feature_columns.json
"""

import os, sys, json, joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import xgboost as xgb

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

FEATURE_COLUMNS = [
    "age", "severity_score", "duration_hours", "symptom_count", "red_flag_count",
    "has_fever", "has_chest_pain", "has_shortness_of_breath", "has_head_symptoms",
    "has_gi_symptoms", "bayesian_urgency_score", "comorbidity_count",
]

LABELS = ["HomeCare", "Urgent", "Emergency"]
np.random.seed(42)
N = 5000


def generate_dataset(n: int) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        # Random base features
        age = np.random.randint(1, 90)
        severity = np.random.uniform(1, 10)
        duration = np.random.exponential(48)
        symptom_count = np.random.randint(1, 6)
        red_flag_count = np.random.choice([0, 0, 0, 1, 2], p=[0.6, 0.15, 0.1, 0.1, 0.05])
        has_cp = np.random.choice([0, 1], p=[0.85, 0.15])
        has_sob = np.random.choice([0, 1], p=[0.80, 0.20])
        has_fever = np.random.choice([0, 1], p=[0.70, 0.30])
        has_head = np.random.choice([0, 1], p=[0.75, 0.25])
        has_gi = np.random.choice([0, 1], p=[0.75, 0.25])
        comorbidities = np.random.randint(0, 5)
        bayesian = np.random.choice([0, 1, 2], p=[0.55, 0.30, 0.15])

        # Label logic
        score = (
            severity * 0.25 +
            red_flag_count * 2.5 +
            has_cp * 2.0 +
            has_sob * 1.2 +
            bayesian * 1.0 +
            symptom_count * 0.3 +
            comorbidities * 0.4 +
            (1.2 if age > 65 else 0) +
            (0.8 if age < 5 else 0)
        )

        noise = np.random.normal(0, 0.8)
        score += noise

        if score >= 8.0:
            label = 2  # Emergency
        elif score >= 4.5:
            label = 1  # Urgent
        else:
            label = 0  # HomeCare

        rows.append([
            age, severity, min(duration, 720), symptom_count, red_flag_count,
            has_fever, has_cp, has_sob, has_head, has_gi, bayesian, comorbidities, label
        ])

    cols = FEATURE_COLUMNS + ["label"]
    return pd.DataFrame(rows, columns=cols)


def train():
    print("📊 Generating synthetic dataset...")
    df = generate_dataset(N)
    print(f"  Distribution: {df['label'].value_counts().to_dict()}")

    X = df[FEATURE_COLUMNS]
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    # Class weights to emphasize Emergency recall
    scale_pos = {0: 1.0, 1: 1.5, 2: 3.0}
    sample_weights = y_train.map(scale_pos).values

    print("🚂 Training XGBoost...")
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, sample_weight=sample_weights,
              eval_set=[(X_test, y_test)], verbose=50)

    # Evaluation
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    print("\n📈 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=LABELS))

    print("📊 Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    try:
        auc = roc_auc_score(y_test, y_proba, multi_class="ovr", average="macro")
        print(f"🎯 ROC-AUC (macro): {auc:.4f}")
    except Exception as e:
        print(f"AUC calc skipped: {e}")

    # Emergency-specific metrics
    em_true = (y_test == 2).astype(int)
    em_pred = (y_pred == 2).astype(int)
    tp = ((em_true == 1) & (em_pred == 1)).sum()
    fn = ((em_true == 1) & (em_pred == 0)).sum()
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
    print(f"🚨 Emergency Sensitivity (Recall): {sensitivity:.4f}")

    # Save
    os.makedirs("models", exist_ok=True)
    joblib.dump(model, "models/triage_xgb.pkl")
    with open("models/feature_columns.json", "w") as f:
        json.dump(FEATURE_COLUMNS, f)

    print("\n✅ Model saved to models/triage_xgb.pkl")
    print("✅ Feature columns saved to models/feature_columns.json")


if __name__ == "__main__":
    train()
