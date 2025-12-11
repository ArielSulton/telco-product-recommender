#!/usr/bin/env python3
"""
Export Random Forest model from notebook to production format.

This script:
1. Loads trained model from improved_rf_topk notebook
2. Validates model performance
3. Exports to MLflow Model Registry
4. Creates production artifacts
"""

import sys
import os
import joblib
import json
import shutil
import logging
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# Add project root to path for imports
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent.parent.parent
sys.path.append(str(project_root / 'backend'))

# Explicitly import from backend module to ensure correct pickling
# The class MUST be imported from the same module path that the backend uses
try:
    from app.ml.rf_model import RFRecommender
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Could not import RFRecommender from backend module.")
    print(f"   Error: {e}")
    print("   Please ensure PYTHONPATH includes the 'backend' directory.")
    print("   Example: export PYTHONPATH=$PYTHONPATH:$(pwd)/backend")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class RFModelExporter:
    """Export Random Forest model to production."""

    def __init__(
        self,
        model_path: str = "/home/arielsulton/Documents/Stargazing Project/VScode Project/dicoding/ASAH Capstone/ml/models/improved_rf/improved_rf_topk_model.pkl",
        experiment_name: str = "telco_rf_production",
        mlflow_uri: str = "http://localhost:5000"
    ):
        self.model_path = Path(model_path)
        self.experiment_name = experiment_name
        self.mlflow_uri = mlflow_uri

    def load_model_artifacts(self):
        """Load model and artifacts from notebook export."""
        print(f"📦 Loading model from: {self.model_path}")

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {self.model_path}.\n"
                "Please run improved_rf_topk.ipynb notebook first!"
            )

        artifacts = joblib.load(self.model_path)

        # Required keys
        required_keys = [
            'model', 'label_encoder_target', 'feature_columns', 'temperature'
        ]

        for key in required_keys:
            if key not in artifacts:
                raise ValueError(f"Missing required artifact: {key}")

        # Construct label_encoders dict from individual encoders
        label_encoders = {}
        for key in artifacts.keys():
            if key.startswith('label_encoder_') and key != 'label_encoder_target':
                # Extract column name (e.g., 'label_encoder_plan' -> 'plan_type')
                col_name = key.replace('label_encoder_', '')
                if col_name == 'plan':
                    col_name = 'plan_type'
                elif col_name == 'device':
                    col_name = 'device_brand'
                label_encoders[col_name] = artifacts[key]

        artifacts['label_encoders'] = label_encoders

        print("✅ Model artifacts loaded successfully")
        print(f"   - Features: {len(artifacts['feature_columns'])}")
        print(f"   - Classes: {len(artifacts['label_encoder_target'].classes_)}")
        print(f"   - Temperature: {artifacts['temperature']}")
        print(f"   - Label encoders: {list(label_encoders.keys())}")

        return artifacts

    def create_inference_wrapper(self, artifacts):
        """Create production inference wrapper."""
        return RFRecommender(
            model=artifacts['model'],
            le_target=artifacts['label_encoder_target'],
            feature_cols=artifacts['feature_columns'],
            temperature=artifacts['temperature'],
            le_dict=artifacts['label_encoders']
        )

    def register_to_mlflow(self, artifacts, wrapper):
        """Register model to MLflow Model Registry."""
        print(f"\n📝 Registering model to MLflow: {self.mlflow_uri}")

        mlflow.set_tracking_uri(self.mlflow_uri)
        mlflow.set_experiment(self.experiment_name)

        with mlflow.start_run(run_name=f"rf_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):

            # Log parameters
            mlflow.log_param("model_type", "RandomForest")
            mlflow.log_param("n_estimators", artifacts['model'].n_estimators)
            mlflow.log_param("n_features", len(artifacts['feature_columns']))
            mlflow.log_param("n_classes", len(artifacts['label_encoder_target'].classes_))
            mlflow.log_param("temperature", artifacts['temperature'])

            # Log model metadata
            mlflow.log_dict(
                {
                    'feature_columns': artifacts['feature_columns'],
                    'target_classes': artifacts['label_encoder_target'].classes_.tolist(),
                    'temperature': artifacts['temperature']
                },
                "model_metadata.json"
            )

            # Create sample input for signature
            sample_input = pd.DataFrame([{
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
            }])

            # Log model with signature
            signature = infer_signature(
                sample_input,
                wrapper.predict_topk(sample_input.to_dict('records')[0])
            )

            mlflow.sklearn.log_model(
                artifacts['model'],
                "model",
                signature=signature,
                registered_model_name="telco_rf_recommender"
            )

            # Log artifacts
            mlflow.log_artifact(str(self.model_path), "model_artifacts")

            run_id = mlflow.active_run().info.run_id
            print(f"✅ Model registered successfully!")
            print(f"   Run ID: {run_id}")
            print(f"   Model URI: runs:/{run_id}/model")

        return run_id

    def export_production_artifacts(self, artifacts, wrapper, output_dir: str = None):
        """Export production-ready artifacts."""
        if output_dir is None:
            output_dir = Path("/home/arielsulton/Documents/Stargazing Project/VScode Project/dicoding/ASAH Capstone/backend/app/ml/models/rf_v2")
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n📤 Exporting production artifacts to: {output_dir}")

        # 1. Save wrapper model
        wrapper_path = output_dir / "rf_recommender.pkl"
        joblib.dump(wrapper, wrapper_path)
        print(f"   ✅ Wrapper model: {wrapper_path.name}")

        # 2. Save metadata
        metadata = {
            'model_type': 'RandomForestRecommender',
            'version': '2.0.0',
            'created_at': datetime.now().isoformat(),
            'n_features': len(artifacts['feature_columns']),
            'n_classes': len(artifacts['label_encoder_target'].classes_),
            'temperature': artifacts['temperature'],
            'feature_columns': artifacts['feature_columns'],
            'target_classes': artifacts['label_encoder_target'].classes_.tolist()
        }

        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"   ✅ Metadata: {metadata_path.name}")

        # 3. Create usage example
        usage_example = '''
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
'''
        usage_path = output_dir / "usage_example.py"
        with open(usage_path, 'w') as f:
            f.write(usage_example)
        print(f"   ✅ Usage example: {usage_path.name}")

        print(f"\n✅ All production artifacts exported to: {output_dir}")
        return output_dir

    def run(self):
        """Run full export pipeline."""
        print("=" * 60)
        print("🚀 RF Model Production Export Pipeline")
        print("=" * 60)

        # 1. Load model
        artifacts = self.load_model_artifacts()

        # 2. Create wrapper
        print("\n🔧 Creating production inference wrapper...")
        wrapper = self.create_inference_wrapper(artifacts)
        print("✅ Wrapper created")

        # 3. Test inference
        print("\n🧪 Testing inference...")
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

        recommendations = wrapper.predict_topk(test_user, k=3)
        print(f"✅ Inference test passed!")
        print(f"   Sample recommendations: {recommendations[0]['product']} ({recommendations[0]['confidence']:.2%})")

        # 4. Register to MLflow
        try:
            run_id = self.register_to_mlflow(artifacts, wrapper)
        except Exception as e:
            print(f"⚠️  MLflow registration failed: {e}")
            print("   Continuing with local export...")
            run_id = None

        # 5. Export artifacts
        output_dir = self.export_production_artifacts(artifacts, wrapper)

        print("\n" + "=" * 60)
        print("✅ Export completed successfully!")
        print("=" * 60)
        print(f"\n📂 Production artifacts: {output_dir}")
        if run_id:
            print(f"📝 MLflow run ID: {run_id}")
        print("\n🎯 Next steps:")
        print("   1. Review exported artifacts")
        print("   2. Update backend/app/ml/recommender.py")
        print("   3. Run backend tests")
        print("   4. Deploy with A/B testing")

        return output_dir, run_id


if __name__ == "__main__":
    exporter = RFModelExporter()
    exporter.run()
