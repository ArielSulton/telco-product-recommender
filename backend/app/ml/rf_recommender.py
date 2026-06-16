"""
Layanan Rekomendasi Random Forest (v2.0)

Implementasi produksi model Random Forest untuk sistem rekomendasi
paket telekomunikasi berdasarkan perilaku pelanggan.

Menggantikan pipeline hybrid lama (K-Means + LightFM + XGBoost).

Performa Model:
- Accuracy       : 86,8%
- Top-3 Accuracy : 99,57%
- Waktu inferensi: <50ms (dengan cache Redis)
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.models.database import Product
from app.ml.rf_model import RFRecommender  # Diimpor agar unpickling model lama tetap berjalan

logger = logging.getLogger(__name__)


# Pemetaan label rekomendasi dari model ke kandidat produk di katalog.
# Setiap label memiliki daftar product_id prioritas dan family produk sebagai fallback.
RECOMMENDATION_CANDIDATES = {
    "Paket Pemula": {"product_ids": ["IDN001", "IDN002", "IDN003"], "families": ["data", "combo"], "categories": ["starter"], "tags": ["starter", "trial", "budget"]},
    "Paket Kuota Besar": {"product_ids": ["IDN004", "IDN005", "IDN006"], "families": ["data"], "categories": ["data"], "tags": ["data", "quota", "heavy-usage"]},
    "Paket Telepon": {"product_ids": ["IDN007", "IDN008", "IDN009"], "families": ["voice"], "categories": ["voice"], "tags": ["voice", "call"]},
    "Paket Keluarga/Kombo": {"product_ids": ["IDN010", "IDN011", "IDN012"], "families": ["combo"], "categories": ["combo"], "tags": ["family", "combo", "shared"]},
    "Paket Retensi": {"product_ids": ["IDN013", "IDN014", "IDN015"], "families": ["combo", "data"], "categories": ["retention"], "tags": ["retention", "loyalty", "promo"]},
    "Paket Data Premium": {"product_ids": ["IDN016", "IDN017", "IDN018"], "families": ["data"], "categories": ["premium"], "tags": ["premium", "unlimited", "streaming"]},
    "Data Booster": {"product_ids": ["IDN004", "IDN005", "IDN006"], "families": ["data"], "categories": ["data"], "tags": ["quota", "data"]},
    "Streaming Partner Pack": {"product_ids": ["IDN016", "IDN017"], "families": ["data"], "categories": ["premium"], "tags": ["streaming", "video"]},
    "General Offer": {"product_ids": ["IDN003", "IDN010"], "families": ["combo", "data"], "categories": ["starter", "combo"], "tags": ["value", "combo"]},
    "Voice Bundle": {"product_ids": ["IDN007", "IDN008", "IDN009"], "families": ["voice"], "categories": ["voice"], "tags": ["voice", "call"]},
    "Family Plan Offer": {"product_ids": ["IDN010", "IDN011", "IDN012"], "families": ["combo"], "categories": ["combo"], "tags": ["family", "combo"]},
    "Device Upgrade Offer": {"product_ids": ["IDN016", "IDN017"], "families": ["data"], "categories": ["premium"], "tags": ["premium", "device"]},
    "Retention Offer": {"product_ids": ["IDN013", "IDN014", "IDN015"], "families": ["combo", "data"], "categories": ["retention"], "tags": ["retention", "loyalty"]},
    "Roaming Pass": {"product_ids": ["IDN018", "IDN017"], "families": ["data"], "categories": ["premium"], "tags": ["roaming", "travel"]},
    "Top-up Promo": {"product_ids": ["IDN001", "IDN002"], "families": ["data"], "categories": ["starter"], "tags": ["starter", "promo"]},
    "Starter Pack": {"product_ids": ["IDN001", "IDN002", "IDN003"], "families": ["data"], "categories": ["starter"], "tags": ["starter", "trial"]},
}

PRIMARY_CATEGORY_LABELS = {
    "starter": "Paket Pemula",
    "data": "Paket Kuota Besar",
    "voice": "Paket Telepon",
    "combo": "Paket Keluarga/Kombo",
    "retention": "Paket Retensi",
    "premium": "Paket Data Premium",
}


class RFRecommenderService:
    """
    Layanan rekomendasi berbasis algoritma Random Forest.

    Fitur utama:
    - Rekomendasi berbasis fitur perilaku pelanggan (content-based)
    - Prediksi Top-K label rekomendasi dengan skor confidence
    - Feature engineering dilakukan ulang saat inferensi
    - Waktu inferensi cepat (<50ms)
    - Tidak ada masalah cold start karena berbasis fitur, bukan riwayat interaksi
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Inisialisasi layanan rekomendasi Random Forest.

        Args:
            model_path: Path ke file kaggle_rf_recommender.pkl.
                        Jika None, menggunakan path default relatif terhadap WORKDIR container.
        """
        if model_path is None:
            model_path = (
                Path(__file__).resolve().parents[2]
                / "ml"
                / "models"
                / "kaggle_rf"
                / "kaggle_rf_recommender.pkl"
            )
        else:
            model_path = Path(model_path)

        self.model_path = model_path
        self.model = None
        self.metadata = None
        self.runtime_mode = "legacy_rf_wrapper"
        self._load_model()

    def _load_model(self):
        """Memuat model Random Forest dari file .pkl ke memori."""
        try:
            logger.info(f"Memuat model Random Forest dari: {self.model_path}")
            self.model = joblib.load(self.model_path)

            # Muat metadata model (accuracy, versi, jumlah fitur, dll)
            metadata_path = self.model_path.parent / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    self.metadata = json.load(f)

            # Deteksi format artifact: bundle dict Kaggle RF atau wrapper lama
            if isinstance(self.model, dict) and {"model", "feature_columns", "target_encoder", "label_encoders"}.issubset(self.model.keys()):
                self.runtime_mode = "kaggle_rf_bundle"
            else:
                self.runtime_mode = "legacy_rf_wrapper"

            logger.info(f"Model Random Forest berhasil dimuat dengan mode={self.runtime_mode}")

        except FileNotFoundError:
            logger.error(f"File model tidak ditemukan di: {self.model_path}")
            logger.error("Jalankan ml/notebook/kaggle_rf_retraining.ipynb terlebih dahulu untuk menghasilkan artifact model.")
            raise
        except Exception as e:
            logger.error(f"Gagal memuat model: {e}")
            raise

    async def get_recommendations(
        self,
        user_id: int,
        user_features: Dict[str, Any],
        db: AsyncSession,
        k: int = 5,
        min_confidence: float = 0.05,
        include_explanations: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Menghasilkan rekomendasi paket telekomunikasi yang dipersonalisasi untuk satu pengguna.

        Args:
            user_id          : ID pengguna
            user_features    : Dict fitur pengguna yang diambil dari database
            db               : Sesi database async untuk pencarian produk
            k                : Jumlah rekomendasi yang dikembalikan
            min_confidence   : Threshold minimum skor confidence prediksi
            include_explanations: Apakah menyertakan penjelasan berbasis feature importance

        Returns:
            List dict rekomendasi dengan detail produk lengkap:
                - product_id      : ID produk
                - product_name    : Nama produk
                - price           : Harga produk
                - quota_data_mb   : Kuota data (MB)
                - validity_days   : Masa berlaku (hari)
                - confidence      : Skor confidence prediksi (0-1)
                - rank            : Peringkat rekomendasi (1 sampai k)
                - explanation     : Penjelasan feature importance (jika diaktifkan)
        """
        start_time = datetime.now()

        try:
            # Validasi ketersediaan fitur wajib sebelum inferensi
            required_features = [
                'plan_type', 'device_brand', 'avg_data_usage_gb',
                'pct_video_usage', 'avg_call_duration', 'sms_freq',
                'monthly_spend', 'topup_freq', 'travel_score', 'complaint_count'
            ]

            missing = [f for f in required_features if f not in user_features]
            if missing:
                raise ValueError(f"Fitur wajib tidak tersedia: {missing}")

            # Beri ruang untuk contextual re-ranking bila pengguna baru membeli paket.
            has_recent_purchase = bool(user_features.get("latest_recommendation_category"))
            has_retention_risk = (
                float(user_features.get("churn_score", 0) or 0) >= 0.75
                or float(user_features.get("complaint_count", 0) or 0) >= 2
            )
            expand_candidates = has_recent_purchase or not has_retention_risk
            prediction_limit = max(k, len(PRIMARY_CATEGORY_LABELS)) if expand_candidates else k
            prediction_threshold = 0.0 if expand_candidates else min_confidence

            # Jalankan prediksi Top-K menggunakan model Random Forest
            recommendations = self._predict_topk(
                user_features=user_features,
                k=prediction_limit,
                min_confidence=prediction_threshold
            )
            recommendations = self._prioritize_latest_purchase_category(
                recommendations=recommendations,
                user_features=user_features,
                k=k,
            )

            # Perkaya hasil prediksi dengan detail produk dari database
            enriched_recommendations = await self._enrich_with_products(
                db, recommendations, user_features
            )

            # Tambahkan penjelasan berbasis feature importance jika diminta
            if include_explanations:
                enriched_recommendations = self._add_explanations(
                    enriched_recommendations, user_features
                )

            # Hitung waktu inferensi
            inference_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                f"Berhasil menghasilkan {len(enriched_recommendations)} rekomendasi "
                f"untuk user {user_id} dalam {inference_time:.1f}ms"
            )

            # Tambahkan metadata ke setiap item rekomendasi
            for rec in enriched_recommendations:
                rec['user_id'] = user_id
                rec['model_version'] = self.metadata.get('version', '2.0.0')
                rec['inference_time_ms'] = inference_time
                rec['created_at'] = datetime.now().isoformat()

            return enriched_recommendations

        except Exception as e:
            logger.error(f"Rekomendasi gagal untuk user {user_id}: {e}")
            raise

    def _prioritize_latest_purchase_category(
        self,
        recommendations: List[Dict[str, Any]],
        user_features: Dict[str, Any],
        k: int,
    ) -> List[Dict[str, Any]]:
        """Keep a recent purchase category visible unless retention risk takes precedence."""
        latest_category = str(user_features.get("latest_recommendation_category") or "").lower()
        churn_score = float(user_features.get("churn_score", 0) or 0)
        complaint_count = float(user_features.get("complaint_count", 0) or 0)
        has_retention_risk = churn_score >= 0.75 or complaint_count >= 2
        if latest_category != "retention" and not has_retention_risk:
            recommendations = [
                recommendation
                for recommendation in recommendations
                if recommendation.get("product") not in {"Paket Retensi", "Retention Offer"}
            ]

        if has_retention_risk:
            retention_labels = {"Paket Retensi", "Retention Offer"}
            retention_recommendation = None
            remaining = []

            for recommendation in recommendations:
                if recommendation.get("product") in retention_labels and retention_recommendation is None:
                    retention_recommendation = recommendation
                else:
                    remaining.append(recommendation)

            if retention_recommendation is None:
                fallback_confidence = max(
                    [float(recommendation.get("confidence", 0) or 0) for recommendation in recommendations] or [0.5]
                )
                retention_recommendation = {
                    "product": "Paket Retensi",
                    "confidence": max(0.5, fallback_confidence * 0.95),
                    "context_source": "complaint_retention_signal",
                }
            else:
                retention_recommendation["context_source"] = "complaint_retention_signal"

            prioritized = [retention_recommendation, *remaining][:k]
            for index, recommendation in enumerate(prioritized, start=1):
                recommendation["rank"] = index
            return prioritized

        if latest_category not in PRIMARY_CATEGORY_LABELS:
            return recommendations[:k]

        if latest_category != "retention" and has_retention_risk:
            return recommendations[:k]

        contextual_label = PRIMARY_CATEGORY_LABELS[latest_category]
        contextual = None
        remaining = []
        for recommendation in recommendations:
            if recommendation.get("product") == contextual_label and contextual is None:
                contextual = recommendation
            else:
                remaining.append(recommendation)

        if contextual is None:
            return recommendations[:k]

        prioritized = [contextual, *remaining][:k]
        for index, recommendation in enumerate(prioritized, start=1):
            recommendation["rank"] = index
            if recommendation is contextual:
                recommendation["context_source"] = "latest_purchase_category"

        return prioritized

    def _predict_topk(
        self,
        user_features: Dict[str, Any],
        k: int,
        min_confidence: float,
    ) -> List[Dict[str, Any]]:
        """Mengarahkan prediksi ke metode yang sesuai berdasarkan format artifact model."""
        if self.runtime_mode == "kaggle_rf_bundle":
            return self._predict_topk_kaggle_bundle(user_features, k, min_confidence)

        # Fallback ke wrapper model lama
        return self.model.predict_topk(
            user_features=user_features,
            k=k,
            min_confidence=min_confidence,
        )

    def _predict_topk_kaggle_bundle(
        self,
        user_features: Dict[str, Any],
        k: int,
        min_confidence: float,
    ) -> List[Dict[str, Any]]:
        """
        Menjalankan inferensi menggunakan artifact Random Forest format bundle dict Kaggle.

        Artifact berisi: model RF, feature_columns, label_encoders, dan target_encoder
        yang semuanya disimpan dalam satu file .pkl.
        """
        bundle_model = self.model["model"]
        feature_columns = self.model["feature_columns"]
        label_encoders = self.model["label_encoders"]
        target_encoder = self.model["target_encoder"]

        # Bentuk DataFrame dari fitur pengguna lalu jalankan feature engineering
        df = pd.DataFrame([user_features]).copy()
        df = self._engineer_features_kaggle(df)

        # Encode kolom kategorikal menggunakan LabelEncoder yang sudah dilatih
        for col, encoder in label_encoders.items():
            value = str(df.at[0, col]) if col in df.columns else str(encoder.classes_[0])
            if value not in encoder.classes_:
                value = str(encoder.classes_[0])
            df[f"{col}_encoded"] = encoder.transform([value])[0]

        # Jalankan prediksi probabilitas per kelas menggunakan Random Forest
        X = df[feature_columns]
        proba = bundle_model.predict_proba(X)[0]
        sorted_indices = np.argsort(proba)[::-1]

        # Ambil Top-K label dengan confidence di atas threshold minimum
        recommendations = []
        for idx in sorted_indices:
            confidence = float(proba[idx])
            if confidence >= min_confidence:
                recommendations.append(
                    {
                        "product": target_encoder.inverse_transform([idx])[0],
                        "confidence": confidence,
                        "rank": len(recommendations) + 1,
                    }
                )
            if len(recommendations) == k:
                break

        return recommendations

    def _engineer_features_kaggle(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Mereplikasi feature engineering yang dilakukan saat training agar input model konsisten.

        Fitur yang dibentuk meliputi:
        - RFM features: recency, frequency, monetary
        - Interaction features: freq_x_monetary, arpu_per_data, data_intensity
        - Composite score: loyalty_score
        """
        engineered = df.copy()

        # Isi nilai default untuk fitur yang mungkin tidak tersedia
        defaults = {
            "monthly_spend": 0.0,
            "avg_data_usage_gb": 0.0,
            "avg_call_duration": 0.0,
            "sms_freq": 0.0,
            "topup_freq": 0.0,
            "complaint_count": 0.0,
            "travel_score": 0.0,
            "churn_score": 0.0,
            "tenure_months": 12.0,
            "cltv": 0.0,
        }
        for col, default in defaults.items():
            if col not in engineered.columns:
                engineered[col] = default

        # RFM features — mengukur recency, frequency, dan monetary pelanggan
        engineered["recency"] = 1 / (engineered["complaint_count"] + 1)
        engineered["frequency"] = engineered["topup_freq"]
        engineered["monetary"] = engineered["monthly_spend"]
        engineered["arpu"] = engineered["monthly_spend"]

        # Interaction features — menangkap hubungan antar fitur
        engineered["avg_spend_per_topup"] = engineered["monthly_spend"] / (engineered["topup_freq"] + 1)
        engineered["data_intensity"] = engineered["avg_data_usage_gb"] / (engineered["monthly_spend"] + 1)
        engineered["communication_intensity"] = engineered["avg_call_duration"] + engineered["sms_freq"]
        engineered["freq_x_monetary"] = engineered["frequency"] * engineered["monetary"]
        engineered["arpu_per_data"] = engineered["arpu"] / (engineered["avg_data_usage_gb"] + 1)

        # Estimasi CLTV jika belum tersedia
        if float(engineered["cltv"].max()) <= 0:
            engineered["cltv"] = engineered["monthly_spend"] * 12

        # Loyalty score — composite dari tenure, CLTV, dan churn score
        tenure_max = max(float(engineered["tenure_months"].max()), 1.0)
        cltv_max = max(float(engineered["cltv"].max()), 1.0)
        engineered["loyalty_score"] = (
            (engineered["tenure_months"] / (tenure_max + 1)) * 0.4
            + (engineered["cltv"] / (cltv_max + 1)) * 0.4
            + ((100 - engineered["churn_score"]) / 100) * 0.2
        )

        return engineered

    async def _enrich_with_products(
        self,
        db: AsyncSession,
        recommendations: List[Dict],
        user_features: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """
        Memperkaya hasil prediksi label dengan detail produk dari database.

        Setiap label rekomendasi dari model (misal 'Paket Kuota Besar') dipetakan
        ke produk aktif yang paling sesuai di katalog menggunakan scoring function.

        Args:
            db              : Sesi database async
            recommendations : List hasil prediksi model berisi label dan confidence
            user_features   : Fitur pengguna untuk scoring produk kandidat

        Returns:
            List rekomendasi yang sudah dilengkapi detail produk
        """
        enriched = []
        used_product_ids = set()

        for rec in recommendations:
            model_output_name = rec.get('product')

            if not model_output_name:
                logger.warning(f"Label rekomendasi kosong pada item: {rec}")
                continue

            product = await self._select_best_product(
                db=db,
                recommendation_label=model_output_name,
                user_features=user_features or {},
                used_product_ids=used_product_ids,
            )

            if not product:
                logger.warning(
                    f"Label '{model_output_name}' tidak menemukan kandidat produk aktif di katalog."
                )
                continue

            used_product_ids.add(product.product_id)

            enriched_rec = {
                'product_id': product.product_id,
                'product_name': product.product_name,
                'price': float(product.price),
                'quota_data_mb': product.quota_data_mb,
                'validity_days': product.validity_days,
                'family': product.product_family,
                'kategori_rekomendasi': product.kategori_rekomendasi,
                'tags': product.tags or [],
                'ikut_rekomendasi': product.ikut_rekomendasi,
                'description': None,
                'confidence': rec.get('confidence'),
                'rank': rec.get('rank'),
                'predicted_label': model_output_name,
                'context_source': rec.get('context_source'),
            }

            if 'explanation' in rec:
                enriched_rec['explanation'] = rec['explanation']

            enriched.append(enriched_rec)

        return enriched

    async def _select_best_product(
        self,
        db: AsyncSession,
        recommendation_label: str,
        user_features: Dict[str, Any],
        used_product_ids: set[str],
    ) -> Optional[Product]:
        """
        Memilih produk aktif terbaik dari katalog untuk label rekomendasi tertentu.

        Pencarian dilakukan dalam urutan prioritas:
        1. Produk berdasarkan product_id yang sudah dipetakan di RECOMMENDATION_CANDIDATES
        2. Produk berdasarkan family (data, voice, combo)
        3. Produk berdasarkan tag yang cocok dengan label
        4. Produk dengan nama persis sama dengan label
        """
        mapping = RECOMMENDATION_CANDIDATES.get(
            recommendation_label,
            {"product_ids": [], "families": ["data"], "categories": ["data"], "tags": []},
        )
        normalized_label = recommendation_label.lower()
        recommended_categories = [cat.lower() for cat in mapping.get("categories", [])]
        recommended_tags = [tag.lower() for tag in mapping.get("tags", [])]

        # Cari produk berdasarkan product_id prioritas
        products_by_id: List[Product] = []
        if mapping["product_ids"]:
            result = await db.execute(
                select(Product)
                .where(Product.product_id.in_(mapping["product_ids"]))
                .where(Product.is_active == True)
                .where(Product.ikut_rekomendasi == True)
            )
            products_by_id = list(result.scalars().all())

        # Cari produk berdasarkan kategori rekomendasi eksplisit dari admin
        category_products: List[Product] = []
        if recommended_categories:
            result = await db.execute(
                select(Product)
                .where(func.lower(Product.kategori_rekomendasi).in_(recommended_categories))
                .where(Product.is_active == True)
                .where(Product.ikut_rekomendasi == True)
            )
            category_products = list(result.scalars().all())

        # Cari produk berdasarkan family sebagai fallback
        family_products: List[Product] = []
        if mapping["families"]:
            result = await db.execute(
                select(Product)
                .where(Product.product_family.in_(mapping["families"]))
                .where(Product.is_active == True)
                .where(Product.ikut_rekomendasi == True)
            )
            family_products = list(result.scalars().all())

        # Cari produk berdasarkan tag yang cocok dengan label
        tagged_products: List[Product] = []
        try:
            result = await db.execute(
                select(Product)
                .where(Product.is_active == True)
                .where(Product.ikut_rekomendasi == True)
                .where(Product.tags.isnot(None))
            )
            tag_pool = list(result.scalars().all())
            tagged_products = [
                product
                for product in tag_pool
                if self._tags_match_label(product.tags or [], normalized_label, recommended_tags)
            ]
        except Exception:
            tagged_products = []

        # Cari produk dengan nama persis sama dengan label
        result = await db.execute(
            select(Product)
            .where(Product.product_name == recommendation_label)
            .where(Product.is_active == True)
            .where(Product.ikut_rekomendasi == True)
        )
        exact_name_products = list(result.scalars().all())

        # Gabungkan semua kandidat, hindari duplikasi dan produk yang sudah dipakai
        candidate_map: Dict[str, Product] = {}
        latest_product_id = user_features.get("latest_product_id")
        for product in [*products_by_id, *category_products, *family_products, *tagged_products, *exact_name_products]:
            if product.product_id not in used_product_ids and product.product_id != latest_product_id:
                candidate_map[product.product_id] = product

        candidates = list(candidate_map.values())
        if not candidates:
            return None

        # Pilih produk dengan skor tertinggi berdasarkan relevansi label dan fitur pengguna
        return sorted(
            candidates,
            key=lambda product: self._score_product_candidate(
                product=product,
                recommendation_label=recommendation_label,
                user_features=user_features,
                preferred_ids=mapping["product_ids"],
                preferred_categories=recommended_categories,
                preferred_tags=recommended_tags,
            ),
            reverse=True,
        )[0]

    def _tags_match_label(
        self,
        product_tags: List[str],
        normalized_label: str,
        preferred_tags: List[str],
    ) -> bool:
        """Check if product tags match model label or mapped recommendation tags."""
        normalized_tags = [(tag or "").lower() for tag in product_tags]
        return any(
            normalized_label in tag
            or tag in normalized_label
            or tag in preferred_tags
            for tag in normalized_tags
        )

    def _score_product_candidate(
        self,
        product: Product,
        recommendation_label: str,
        user_features: Dict[str, Any],
        preferred_ids: List[str],
        preferred_categories: Optional[List[str]] = None,
        preferred_tags: Optional[List[str]] = None,
    ) -> float:
        """
        Menghitung skor relevansi produk kandidat terhadap label dan profil pengguna.

        Scoring mempertimbangkan:
        - Apakah produk ada di daftar prioritas label
        - Kedekatan harga dengan pengeluaran bulanan pengguna
        - Kuota data/voice sesuai kebutuhan label
        - Family produk yang sesuai dengan kategori label
        """
        score = 0.0

        # Produk prioritas mendapat bobot lebih tinggi
        if product.product_id in preferred_ids:
            score += 4.0

        category = (product.kategori_rekomendasi or "").lower()
        if preferred_categories and category in preferred_categories:
            score += 3.0

        product_tags = [(tag or "").lower() for tag in (product.tags or [])]
        if preferred_tags:
            tag_matches = len(set(product_tags) & set(preferred_tags))
            score += min(tag_matches, 3) * 1.0

        monthly_spend = float(
            user_features.get("monthly_budget_idr", user_features.get("monthly_spend", 0)) or 0
        )
        avg_data_usage_gb = float(user_features.get("avg_data_usage_gb", 0) or 0)
        pct_video_usage = float(user_features.get("pct_video_usage", 0) or 0)
        topup_freq = float(user_features.get("topup_freq", 0) or 0)
        travel_score = float(user_features.get("travel_score", 0) or 0)
        complaint_count = float(user_features.get("complaint_count", 0) or 0)
        price = float(product.price or 0)
        quota_data_mb = int(product.quota_data_mb or 0)
        quota_voice_min = int(product.quota_voice_min or 0)
        validity_days = int(product.validity_days or 0)
        family = (product.product_family or "").lower()

        # Skor kedekatan harga dengan pengeluaran bulanan pengguna
        if monthly_spend > 0:
            budget_gap = abs(price - monthly_spend)
            score += max(0.0, 2.0 - (budget_gap / max(monthly_spend, 1)))
            # Cegah paket sangat mahal mendominasi hanya karena memiliki kuota terbesar.
            budget_overrun = max(0.0, price - (monthly_spend * 1.5))
            score -= (budget_overrun / max(monthly_spend, 10000.0)) * 1.5

        # Profil penggunaan data tinggi cenderung membutuhkan kuota besar.
        if avg_data_usage_gb > 0:
            expected_quota_mb = avg_data_usage_gb * 1024
            if quota_data_mb >= expected_quota_mb:
                score += min(quota_data_mb / max(expected_quota_mb, 1), 3.0) * 0.4

        # Video/streaming usage menaikkan produk bertag streaming/video/data.
        if pct_video_usage >= 0.5 and set(product_tags) & {"streaming", "video", "data", "unlimited"}:
            score += 1.0

        # Travel score membantu produk roaming/travel.
        if travel_score >= 0.6 and set(product_tags) & {"roaming", "travel"}:
            score += 1.2

        # Banyak komplain mendorong retention/loyalty offer.
        if complaint_count >= 2 and (
            category == "retention" or set(product_tags) & {"retention", "loyalty", "promo"}
        ):
            score += 1.1

        # Frekuensi top-up tinggi cocok dengan promo/top-up/value.
        if topup_freq >= 5 and set(product_tags) & {"topup", "promo", "value", "budget"}:
            score += 0.8

        # Skor khusus untuk label berbasis telepon/voice
        if recommendation_label in {"Paket Telepon", "Voice Bundle"}:
            score += min(quota_voice_min / 100.0, 5.0)
            if family == "voice":
                score += 2.0

        # Skor khusus untuk label berbasis data besar
        if recommendation_label in {"Paket Kuota Besar", "Paket Data Premium", "Data Booster", "Streaming Partner Pack"}:
            score += min(quota_data_mb / 20000.0, 3.0)
            if family == "data":
                score += 1.5

        # Skor khusus untuk label berbasis keluarga/kombo/retensi
        if recommendation_label in {"Paket Keluarga/Kombo", "Paket Retensi", "General Offer", "Family Plan Offer", "Retention Offer"}:
            if family == "combo":
                score += 2.0
            score += validity_days / 30.0
            score += quota_data_mb / 30000.0

        # Skor khusus untuk label paket pemula/entry-level
        if recommendation_label in {"Paket Pemula", "Starter Pack", "Top-up Promo"}:
            score += max(0.0, 2.0 - (price / 50000.0))
            if validity_days <= 30:
                score += 1.0

        # Skor tambahan untuk paket data premium (harga dan kuota tinggi)
        if recommendation_label == "Paket Data Premium":
            if price >= 100000:
                score += 1.5
            if quota_data_mb >= 25000:
                score += 1.5

        return score

    def _add_explanations(
        self,
        recommendations: List[Dict],
        user_features: Dict[str, Any]
    ) -> List[Dict]:
        """
        Menambahkan penjelasan berbasis feature importance Random Forest ke setiap rekomendasi.

        Mengambil 3 fitur dengan kontribusi tertinggi dari model dan menghasilkan
        teks penjelasan yang mudah dipahami pengguna.
        """
        try:
            # Ambil nilai feature importance dari model Random Forest
            if self.runtime_mode == "kaggle_rf_bundle":
                feature_importance = self.model["model"].feature_importances_
                feature_names = self.model["feature_columns"]
            else:
                feature_importance = self.model.model.feature_importances_
                feature_names = self.model.feature_cols

            # Ambil 3 fitur dengan importance tertinggi
            top_k_features = 3
            top_indices = np.argsort(feature_importance)[-top_k_features:][::-1]
            top_features = [
                {
                    'feature': feature_names[idx],
                    'importance': float(feature_importance[idx]),
                    'value': user_features.get(feature_names[idx], 'N/A')
                }
                for idx in top_indices
            ]

            # Tambahkan penjelasan ke setiap item rekomendasi
            for rec in recommendations:
                rec['explanation'] = {
                    'top_features': top_features,
                    'explanation_text': self._generate_explanation_text(
                        rec.get('predicted_label') or rec.get('product_name', 'paket yang direkomendasikan'),
                        top_features
                    )
                }

            return recommendations

        except Exception as e:
            logger.warning(f"Gagal menghasilkan penjelasan rekomendasi: {e}")
            # Kembalikan rekomendasi tanpa penjelasan jika terjadi error
            return recommendations

    def _generate_explanation_text(
        self,
        product: str,
        top_features: List[Dict]
    ) -> str:
        """Menghasilkan teks penjelasan rekomendasi yang mudah dibaca pengguna."""
        feature_texts = []

        for feat in top_features:
            name = feat['feature']
            value = feat['value']

            # Pemetaan nama fitur teknis ke teks yang mudah dipahami
            feature_map = {
                'monthly_spend': f"pengeluaran bulanan Anda sebesar Rp {value:,.0f}",
                'avg_data_usage_gb': f"penggunaan data Anda sebesar {value:.1f} GB",
                'plan_type': f"jenis paket Anda saat ini ({value})",
                'device_brand': f"perangkat {value} yang Anda gunakan",
                'topup_freq': f"frekuensi top-up Anda sebanyak {value} kali/bulan",
                'arpu': f"pola pengeluaran rata-rata Anda",
                'churn_score': "pola penggunaan layanan Anda",
                'loyalty_score': "loyalitas Anda sebagai pelanggan",
                'data_intensity': "intensitas penggunaan data Anda",
                'communication_intensity': "intensitas komunikasi Anda",
            }

            text = feature_map.get(name, f"profil {name} Anda")
            feature_texts.append(text)

        if len(feature_texts) >= 2:
            explanation = (
                f"Kami merekomendasikan {product} berdasarkan "
                f"{feature_texts[0]} dan {feature_texts[1]}"
            )
        elif len(feature_texts) == 1:
            explanation = f"Kami merekomendasikan {product} berdasarkan {feature_texts[0]}"
        else:
            explanation = f"Kami merekomendasikan {product} berdasarkan profil penggunaan Anda"

        return explanation

    async def bulk_recommend(
        self,
        users: List[Dict[str, Any]],
        db: AsyncSession,
        k: int = 5,
        min_confidence: float = 0.05
    ) -> Dict[int, List[Dict]]:
        """
        Menghasilkan rekomendasi untuk banyak pengguna sekaligus (batch inference).

        Args:
            users           : List dict berisi user_id dan fitur masing-masing pengguna
            db              : Sesi database async untuk pencarian produk
            k               : Jumlah rekomendasi per pengguna
            min_confidence  : Threshold minimum skor confidence

        Returns:
            Dict dengan user_id sebagai key dan list rekomendasi sebagai value
        """
        results = {}

        for user in users:
            user_id = user['user_id']
            try:
                recommendations = await self.get_recommendations(
                    user_id=user_id,
                    user_features=user,
                    db=db,
                    k=k,
                    min_confidence=min_confidence,
                    include_explanations=False  # Penjelasan dinonaktifkan untuk efisiensi batch
                )
                results[user_id] = recommendations
            except Exception as e:
                logger.error(f"Rekomendasi batch gagal untuk user {user_id}: {e}")
                results[user_id] = []

        return results

    def get_model_info(self) -> Dict[str, Any]:
        """Mengembalikan metadata dan informasi performa model Random Forest yang aktif."""
        performance = {
            'accuracy': self.metadata.get('accuracy') if self.metadata else None,
            'top3_accuracy': self.metadata.get('top3_accuracy') if self.metadata else None,
            'inference_time_ms': '<50ms (dengan cache)'
        }
        return {
            'model_type': 'RandomForestRecommender',
            'version': self.metadata.get('version', 'kaggle_rf') if self.metadata else 'kaggle_rf',
            'created_at': self.metadata.get('created_at') if self.metadata else None,
            'n_features': self.metadata.get('n_features') if self.metadata else None,
            'n_classes': self.metadata.get('n_classes') if self.metadata else None,
            'temperature': self.metadata.get('temperature') if self.metadata else None,
            'model_path': str(self.model_path),
            'runtime_mode': self.runtime_mode,
            'performance': performance
        }


# Instance singleton — model hanya dimuat sekali saat aplikasi pertama kali dijalankan
_rf_recommender: Optional[RFRecommenderService] = None


def get_rf_recommender() -> RFRecommenderService:
    """Mengembalikan instance singleton RFRecommenderService."""
    global _rf_recommender
    if _rf_recommender is None:
        _rf_recommender = RFRecommenderService()
    return _rf_recommender


async def generate_rf_recommendations(
    user_id: int,
    user_features: Dict[str, Any],
    db: AsyncSession,
    k: int = 5,
    min_confidence: float = 0.05,
    include_explanations: bool = True
) -> List[Dict[str, Any]]:
    """
    Fungsi utama untuk menghasilkan rekomendasi paket telekomunikasi menggunakan Random Forest.

    Ini adalah entry point yang dipanggil oleh endpoint /api/v1/recommend/v2.

    Args:
        user_id              : ID pengguna
        user_features        : Dict fitur pengguna dari database
        db                   : Sesi database async untuk pencarian produk
        k                    : Jumlah rekomendasi yang dikembalikan
        min_confidence       : Threshold minimum skor confidence
        include_explanations : Apakah menyertakan penjelasan feature importance

    Returns:
        List rekomendasi produk telekomunikasi yang sudah diperkaya dengan detail produk
    """
    recommender = get_rf_recommender()
    return await recommender.get_recommendations(
        user_id=user_id,
        user_features=user_features,
        db=db,
        k=k,
        min_confidence=min_confidence,
        include_explanations=include_explanations
    )
