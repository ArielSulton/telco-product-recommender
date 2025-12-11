#!/usr/bin/env python3
"""
Quick script to inspect model artifacts structure.
"""
import joblib
from pathlib import Path

model_path = "/home/arielsulton/Documents/Stargazing Project/VScode Project/dicoding/ASAH Capstone/ml/models/improved_rf/improved_rf_topk_model.pkl"

print(f"📦 Loading model from: {model_path}")
artifacts = joblib.load(model_path)

print(f"\n🔍 Type: {type(artifacts)}")

if isinstance(artifacts, dict):
    print(f"\n📋 Available keys ({len(artifacts)}):")
    for key in artifacts.keys():
        value = artifacts[key]
        print(f"   - {key}: {type(value).__name__}")

        # Show more details for certain types
        if hasattr(value, 'shape'):
            print(f"     Shape: {value.shape}")
        elif hasattr(value, '__len__') and not isinstance(value, str):
            print(f"     Length: {len(value)}")
        elif isinstance(value, (int, float, str)):
            print(f"     Value: {value}")
else:
    print(f"\n⚠️  Artifacts is not a dict, it's: {type(artifacts)}")
    print(f"Available attributes: {dir(artifacts)}")
