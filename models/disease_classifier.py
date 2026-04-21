"""
Disease Prediction Model — Training Pipeline
---------------------------------------------
Trains a machine learning model on the augmented symptoms-diseases dataset
to predict diseases from symptom vectors.

Dataset: Final_Augmented_dataset_Diseases_and_Symptoms.csv
- 246,945 samples
- 377 symptom features (binary)
- 773 unique disease classes
Model: XGBoost Multi-class Classifier with feature engineering pipeline

Run: python disease_classifier.py
Outputs: models/disease_model.pkl, models/disease_label_encoder.pkl, models/symptom_columns.json
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score, top_k_accuracy_score
from sklearn.ensemble import RandomForestClassifier
import warnings

warnings.filterwarnings('ignore')

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATASET_PATH = os.path.join(BASE_DIR, 'Final_Augmented_dataset_Diseases_and_Symptoms.csv')
MODELS_DIR = os.path.join(BASE_DIR, 'models', 'models')

# Model outputs
MODEL_PATH = os.path.join(MODELS_DIR, 'disease_model.pkl')
ENCODER_PATH = os.path.join(MODELS_DIR, 'disease_label_encoder.pkl')
COLUMNS_PATH = os.path.join(MODELS_DIR, 'symptom_columns.json')
METADATA_PATH = os.path.join(MODELS_DIR, 'disease_model_metadata.json')

# Training config
RANDOM_STATE = 42
TEST_SIZE = 0.2
N_ESTIMATORS = 150
MAX_DEPTH = 20
MIN_SAMPLES_SPLIT = 5


def load_dataset():
    """Load and prepare the symptoms-diseases dataset."""
    print("📊 Loading dataset...")
    df = pd.read_csv(DATASET_PATH)
    
    # Dataset statistics
    n_samples = len(df)
    n_features = len(df.columns) - 1  # Exclude disease column
    n_diseases = df['diseases'].nunique()
    
    print(f"   Samples: {n_samples:,}")
    print(f"   Symptom features: {n_features}")
    print(f"   Unique diseases: {n_diseases}")
    
    return df


def prepare_features(df):
    """Prepare feature matrix and labels."""
    print("\n🔧 Preparing features...")
    
    # Filter out diseases with too few samples (need at least 2 for stratification)
    disease_counts = df['diseases'].value_counts()
    valid_diseases = disease_counts[disease_counts >= 5].index
    df_filtered = df[df['diseases'].isin(valid_diseases)].copy()
    
    print(f"   Filtered to diseases with >= 5 samples")
    print(f"   Original: {len(df):,} -> Filtered: {len(df_filtered):,}")
    
    # Separate features and labels
    symptom_columns = [col for col in df_filtered.columns if col != 'diseases']
    X = df_filtered[symptom_columns].values
    y = df_filtered['diseases'].values
    
    # Encode disease labels
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)
    
    print(f"   Feature matrix shape: {X.shape}")
    print(f"   Label classes: {len(label_encoder.classes_)}")
    
    return X, y_encoded, symptom_columns, label_encoder


def calculate_feature_importance(model, symptom_columns, top_n=20):
    """Extract top symptom features by importance."""
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:top_n]
    
    top_features = []
    for idx in indices:
        top_features.append({
            'symptom': symptom_columns[idx],
            'importance': float(importances[idx])
        })
    
    return top_features


def train_model(X, y, label_encoder, symptom_columns):
    """Train the disease prediction model."""
    print("\n🚂 Training Disease Prediction Model...")
    
    # Train-test split with stratification
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=TEST_SIZE, 
        random_state=RANDOM_STATE, 
        stratify=y
    )
    
    print(f"   Training samples: {len(X_train):,}")
    print(f"   Test samples: {len(X_test):,}")
    
    # Initialize Random Forest Classifier (good for high-dimensional sparse binary features)
    model = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        min_samples_split=MIN_SAMPLES_SPLIT,
        class_weight='balanced',
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbose=1
    )
    
    # Train
    print("\n   Training Random Forest...")
    model.fit(X_train, y_train)
    
    # Evaluate
    print("\n📈 Evaluating model...")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    top3_accuracy = top_k_accuracy_score(y_test, y_proba, k=3)
    top5_accuracy = top_k_accuracy_score(y_test, y_proba, k=5)
    
    print(f"\n   ✅ Top-1 Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"   ✅ Top-3 Accuracy: {top3_accuracy:.4f} ({top3_accuracy*100:.2f}%)")
    print(f"   ✅ Top-5 Accuracy: {top5_accuracy:.4f} ({top5_accuracy*100:.2f}%)")
    
    # Feature importance
    top_features = calculate_feature_importance(model, symptom_columns)
    print(f"\n   Top 5 predictive symptoms:")
    for i, feat in enumerate(top_features[:5], 1):
        print(f"      {i}. {feat['symptom']}: {feat['importance']:.4f}")
    
    # Create metadata
    metadata = {
        'model_type': 'RandomForestClassifier',
        'trained_at': datetime.now().isoformat(),
        'dataset': 'Final_Augmented_dataset_Diseases_and_Symptoms.csv',
        'dataset_stats': {
            'total_samples': len(X_train) + len(X_test),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'n_features': X.shape[1],
            'n_classes': len(label_encoder.classes_)
        },
        'hyperparameters': {
            'n_estimators': N_ESTIMATORS,
            'max_depth': MAX_DEPTH,
            'min_samples_split': MIN_SAMPLES_SPLIT,
            'class_weight': 'balanced'
        },
        'metrics': {
            'top1_accuracy': float(accuracy),
            'top3_accuracy': float(top3_accuracy),
            'top5_accuracy': float(top5_accuracy)
        },
        'top_features': top_features[:10]
    }
    
    return model, metadata


def save_artifacts(model, label_encoder, symptom_columns, metadata):
    """Save model and related artifacts."""
    print("\n💾 Saving model artifacts...")
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    # Save model
    joblib.dump(model, MODEL_PATH)
    print(f"   Model saved: {MODEL_PATH}")
    
    # Save label encoder
    joblib.dump(label_encoder, ENCODER_PATH)
    print(f"   Label encoder saved: {ENCODER_PATH}")
    
    # Save symptom columns
    with open(COLUMNS_PATH, 'w') as f:
        json.dump(symptom_columns, f, indent=2)
    print(f"   Symptom columns saved: {COLUMNS_PATH}")
    
    # Save metadata
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"   Metadata saved: {METADATA_PATH}")


def main():
    print("=" * 60)
    print("  Disease Prediction Model — Training Pipeline")
    print("=" * 60)
    
    # Load data
    df = load_dataset()
    
    # Prepare features
    X, y, symptom_columns, label_encoder = prepare_features(df)
    
    # Train model
    model, metadata = train_model(X, y, label_encoder, symptom_columns)
    
    # Save artifacts
    save_artifacts(model, label_encoder, symptom_columns, metadata)
    
    print("\n" + "=" * 60)
    print("  ✅ Training Complete!")
    print("=" * 60)
    print(f"\n  Model: {metadata['model_type']}")
    print(f"  Accuracy: {metadata['metrics']['top1_accuracy']*100:.2f}%")
    print(f"  Top-3 Accuracy: {metadata['metrics']['top3_accuracy']*100:.2f}%")
    print(f"  Classes: {metadata['dataset_stats']['n_classes']} diseases")
    print(f"  Features: {metadata['dataset_stats']['n_features']} symptoms")
    

if __name__ == '__main__':
    main()
