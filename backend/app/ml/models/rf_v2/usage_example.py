
"""
Production usage example for RF Recommender v2.0
"""
import joblib

# Load model
model = joblib.load('rf_recommender.pkl')

# Example user features
user = {
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

# Get recommendations
recommendations = model.predict_topk(user, k=5, min_confidence=0.05)

# Output:
# [
#     {'product': '5G Premium Package', 'confidence': 0.873, 'rank': 1},
#     {'product': 'Unlimited Data Plus', 'confidence': 0.084, 'rank': 2},
#     {'product': 'Business Pro Plan', 'confidence': 0.021, 'rank': 3},
#     ...
# ]
