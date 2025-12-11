
# ============================================================================
# HOW TO LOAD AND USE THE MODEL IN PRODUCTION
# ============================================================================

import joblib
import pandas as pd
import numpy as np

# 1. Load model artifacts
artifacts = joblib.load('../models/improved_rf/improved_rf_topk_model.pkl')

model = artifacts['model']
le_target = artifacts['label_encoder_target']
le_plan = artifacts['label_encoder_plan']
le_device = artifacts['label_encoder_device']
feature_cols = artifacts['feature_columns']
temperature = artifacts['temperature']
min_confidence = artifacts['min_confidence']
k = artifacts['k']

# 2. Prepare new customer data (same features as training)
new_customer = {
    'plan_type': 'Postpaid',
    'device_brand': 'Samsung',
    'avg_data_usage_gb': 12.5,
    'pct_video_usage': 0.65,
    'avg_call_duration': 45.0,
    'sms_freq': 20,
    'monthly_spend': 150000,
    'topup_freq': 3,
    'travel_score': 0.8,
    'complaint_count': 0
}

# 3. Feature engineering (same as training)
new_customer['recency'] = 1 / (new_customer['complaint_count'] + 1)
new_customer['frequency'] = new_customer['topup_freq']
new_customer['monetary'] = new_customer['monthly_spend']
new_customer['arpu'] = new_customer['monthly_spend']
# ... (add all other engineered features)

# 4. Encode categorical features
new_customer['plan_type_encoded'] = le_plan.transform([new_customer['plan_type']])[0]
new_customer['device_brand_encoded'] = le_device.transform([new_customer['device_brand']])[0]

# 5. Create feature vector
X_new = pd.DataFrame([new_customer])[feature_cols]

# 6. Get predictions with calibration
proba_raw = model.predict_proba(X_new)[0]

# Temperature scaling
logits = np.log(np.clip(proba_raw, 1e-9, 1.0))
scaled_logits = logits / temperature
exp_logits = np.exp(scaled_logits)
proba_calibrated = exp_logits / exp_logits.sum()

# 7. Get Top-K recommendations
sorted_indices = np.argsort(proba_calibrated)[::-1]
recommendations = []

for idx in sorted_indices:
    confidence = proba_calibrated[idx]
    if confidence >= min_confidence:
        product = le_target.classes_[idx]
        recommendations.append((product, confidence))
    if len(recommendations) == k:
        break

# 8. Display recommendations
print("Top-3 Product Recommendations:")
for rank, (product, confidence) in enumerate(recommendations, 1):
    print(f"{rank}. {product} (confidence: {confidence:.2%})")

# Output example:
# Top-3 Product Recommendations:
# 1. 5G Premium Package (confidence: 87.32%)
# 2. Unlimited Data Plus (confidence: 8.45%)
# 3. Business Pro Plan (confidence: 2.13%)
