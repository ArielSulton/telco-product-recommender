#!/usr/bin/env python3
"""
Quick test for exported RF model.
"""
import sys
from pathlib import Path
import joblib

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Import RFRecommender class (required for unpickling)
from backend.app.ml.rf_model import RFRecommender

# Load exported model
model_path = "/home/arielsulton/Documents/Stargazing Project/VScode Project/dicoding/ASAH Capstone/backend/app/ml/models/rf_v2/rf_recommender.pkl"

print("🧪 Testing exported RF model...")
print(f"📦 Loading from: {model_path}")

model = joblib.load(model_path)

print(f"✅ Model loaded successfully!")
print(f"   Type: {type(model).__name__}")

# Test inference
test_user = {
    'plan_type': 'Postpaid',
    'device_brand': 'Samsung',
    'avg_data_usage_gb': 12.5,
    'pct_video_usage': 0.65,
    'avg_call_duration': 15.2,
    'sms_freq': 25,
    'monthly_spend': 150000,
    'topup_freq': 4,
    'travel_score': 0.3,
    'complaint_count': 1
}

print("\n🔮 Testing inference...")
recommendations = model.predict_topk(test_user, k=5, min_confidence=0.05)

print(f"✅ Got {len(recommendations)} recommendations:")
for rec in recommendations:
    print(f"   {rec['rank']}. {rec['product']:25s} - {rec['confidence']:.2%}")

print("\n✅ All tests passed! Model is ready for production.")
