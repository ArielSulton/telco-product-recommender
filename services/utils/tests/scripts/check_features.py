#!/usr/bin/env python3
"""
Check feature columns in model.
"""
import joblib

model_path = "/home/arielsulton/Documents/Stargazing Project/VScode Project/dicoding/ASAH Capstone/ml/models/improved_rf/improved_rf_topk_model.pkl"

artifacts = joblib.load(model_path)

print("📋 Feature columns:")
for i, col in enumerate(artifacts['feature_columns'], 1):
    print(f"   {i:2d}. {col}")
