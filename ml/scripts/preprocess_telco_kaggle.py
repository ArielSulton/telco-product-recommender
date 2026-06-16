"""
Preprocess Kaggle Telco churn dataset for the recommendation pipeline.

This script keeps the raw Kaggle file untouched and writes cleaned outputs
to dedicated processed/features folders so the legacy dataset and notebooks
remain safe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT_DIR / "data" / "raw" / "Telco_customer_churn.xlsx"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
FEATURES_DIR = ROOT_DIR / "data" / "features"
PROCESSED_FILE = PROCESSED_DIR / "telco_customer_churn_clean.csv"
FEATURES_FILE = FEATURES_DIR / "telco_user_profile_features.csv"


# Bagian ini memetakan nama kolom asli dari Kaggle menjadi nama kolom yang
# lebih konsisten untuk pipeline Python dan backend kita.
COLUMN_RENAME_MAP: Dict[str, str] = {
    "CustomerID": "customer_id",
    "Gender": "gender",
    "Senior Citizen": "senior_citizen",
    "Partner": "partner",
    "Dependents": "dependents",
    "Tenure Months": "tenure_months",
    "Phone Service": "phone_service",
    "Multiple Lines": "multiple_lines",
    "Internet Service": "internet_service",
    "Online Security": "online_security",
    "Online Backup": "online_backup",
    "Device Protection": "device_protection",
    "Tech Support": "tech_support",
    "Streaming TV": "streaming_tv",
    "Streaming Movies": "streaming_movies",
    "Contract": "contract",
    "Paperless Billing": "paperless_billing",
    "Payment Method": "payment_method",
    "Monthly Charges": "monthly_charges",
    "Total Charges": "total_charges",
    "Churn Label": "churn_label",
    "Churn Value": "churn_value",
    "Churn Score": "churn_score",
    "CLTV": "cltv",
}


SELECTED_COLUMNS = list(COLUMN_RENAME_MAP.keys())


def ensure_output_dirs() -> None:
    """Membuat folder output agar proses simpan file tidak gagal."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)


def load_raw_dataset() -> pd.DataFrame:
    """Memuat dataset mentah dari file Excel Kaggle."""
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Raw dataset not found: {RAW_FILE}")

    # openpyxl is required to read .xlsx files with pandas.
    return pd.read_excel(RAW_FILE, sheet_name="Telco_Churn", engine="openpyxl")


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Membersihkan kolom, tipe data, nilai kosong, dan duplikasi."""
    cleaned = df[SELECTED_COLUMNS].copy()
    cleaned = cleaned.rename(columns=COLUMN_RENAME_MAP)

    # Identifier pelanggan dibersihkan lebih dulu karena akan dipakai untuk join.
    cleaned["customer_id"] = cleaned["customer_id"].astype(str).str.strip()

    # Kolom numerik dipaksa ke format angka agar aman untuk rule dan training.
    numeric_columns = [
        "senior_citizen",
        "tenure_months",
        "monthly_charges",
        "total_charges",
        "churn_value",
        "churn_score",
        "cltv",
    ]
    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    # Kolom kategorikal dibersihkan dari null dan spasi agar label tetap konsisten.
    categorical_columns = [
        "gender",
        "partner",
        "dependents",
        "phone_service",
        "multiple_lines",
        "internet_service",
        "online_security",
        "online_backup",
        "device_protection",
        "tech_support",
        "streaming_tv",
        "streaming_movies",
        "contract",
        "paperless_billing",
        "payment_method",
        "churn_label",
    ]
    for column in categorical_columns:
        cleaned[column] = (
            cleaned[column]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
        )

    # Satu customer cukup punya satu baris agar training tidak bias karena duplikasi.
    cleaned = cleaned.drop_duplicates(subset=["customer_id"]).reset_index(drop=True)

    # Nilai kosong diisi dengan pendekatan sederhana agar pipeline tetap stabil.
    cleaned["total_charges"] = cleaned["total_charges"].fillna(cleaned["monthly_charges"])
    cleaned["monthly_charges"] = cleaned["monthly_charges"].fillna(cleaned["monthly_charges"].median())
    cleaned["tenure_months"] = cleaned["tenure_months"].fillna(0)
    cleaned["churn_score"] = cleaned["churn_score"].fillna(cleaned["churn_score"].median())
    cleaned["cltv"] = cleaned["cltv"].fillna(cleaned["cltv"].median())
    cleaned["churn_value"] = cleaned["churn_value"].fillna(0)
    cleaned["senior_citizen"] = cleaned["senior_citizen"].fillna(0).astype(int)

    return cleaned


def build_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    """Membentuk feature table yang mengikuti kebutuhan jalur Random Forest."""
    features = df.copy()

    # Fitur dasar ini dipakai sebagai padanan dari fitur spend pada model lama.
    features["monthly_spend"] = features["monthly_charges"].round(2)
    features["plan_type"] = features["contract"].map(
        {
            "Month-to-month": "Prepaid",
            "One year": "Postpaid",
            "Two year": "Postpaid",
        }
    ).fillna("Prepaid")

    def infer_pct_video_usage(row: pd.Series) -> float:
        """Mengubah status streaming menjadi skor intensitas video."""
        tv = row["streaming_tv"] == "Yes"
        movies = row["streaming_movies"] == "Yes"
        if tv and movies:
            return 0.80
        if tv or movies:
            return 0.55
        return 0.20

    def infer_avg_data_usage(row: pd.Series) -> float:
        """Mengestimasi penggunaan data berdasarkan internet, streaming, dan spend."""
        internet = row["internet_service"]
        monthly_spend = float(row["monthly_charges"])
        video_usage = infer_pct_video_usage(row)

        if internet == "Fiber optic":
            base = 14.0
        elif internet == "DSL":
            base = 7.0
        else:
            base = 2.0

        spend_boost = min(monthly_spend / 40.0, 6.0)
        video_boost = 4.0 if video_usage >= 0.8 else 2.0 if video_usage >= 0.55 else 0.5
        return round(base + spend_boost + video_boost, 2)

    def infer_topup_freq(row: pd.Series) -> int:
        """Mengaproksimasi frekuensi top-up dari spend dan masa berlangganan."""
        monthly_spend = float(row["monthly_charges"])
        tenure = float(row["tenure_months"])
        if monthly_spend >= 120:
            return 4
        if monthly_spend >= 70:
            return 3
        if tenure <= 6:
            return 2
        return 1

    def infer_avg_call_duration(row: pd.Series) -> float:
        """Mengaproksimasi durasi telepon untuk user yang punya phone service."""
        if row["phone_service"] != "Yes":
            return 3.0
        if row["multiple_lines"] == "Yes":
            return 14.0
        return 9.0

    def infer_sms_freq(row: pd.Series) -> int:
        """Mengaproksimasi frekuensi SMS sederhana dari profil user."""
        if row["phone_service"] != "Yes":
            return 5
        if row["senior_citizen"] == 1:
            return 18
        return 12

    def infer_device_brand(row: pd.Series) -> str:
        """Memberi brand device sintetis berdasarkan tingkat spend user."""
        monthly_spend = float(row["monthly_charges"])
        if monthly_spend >= 110:
            return "Apple"
        if monthly_spend >= 75:
            return "Samsung"
        return "Xiaomi"

    def infer_travel_score(row: pd.Series) -> float:
        """Membentuk skor travel sederhana agar fitur legacy tetap tersedia."""
        contract = row["contract"]
        monthly_spend = float(row["monthly_charges"])
        score = 0.2
        if contract == "Month-to-month":
            score += 0.1
        if monthly_spend >= 100:
            score += 0.2
        return round(min(score, 0.8), 2)

    def infer_complaint_count(row: pd.Series) -> int:
        """Membentuk jumlah komplain sintetis dari churn score dan tech support."""
        if row["churn_score"] >= 80:
            return 3
        if row["tech_support"] == "No":
            return 2
        if row["churn_score"] >= 50:
            return 1
        return 0

    # Seluruh fitur turunan dihitung di sini agar file features sudah siap
    # dipakai untuk pembentukan target dan training.
    features["pct_video_usage"] = features.apply(infer_pct_video_usage, axis=1)
    features["avg_data_usage_gb"] = features.apply(infer_avg_data_usage, axis=1)
    features["topup_freq"] = features.apply(infer_topup_freq, axis=1)
    features["avg_call_duration"] = features.apply(infer_avg_call_duration, axis=1)
    features["sms_freq"] = features.apply(infer_sms_freq, axis=1)
    features["device_brand"] = features.apply(infer_device_brand, axis=1)
    features["travel_score"] = features.apply(infer_travel_score, axis=1)
    features["complaint_count"] = features.apply(infer_complaint_count, axis=1)

    # Hanya kolom yang dipakai pipeline yang disimpan ke feature table akhir.
    feature_columns = [
        "customer_id",
        "partner",
        "dependents",
        "phone_service",
        "multiple_lines",
        "plan_type",
        "device_brand",
        "avg_data_usage_gb",
        "pct_video_usage",
        "avg_call_duration",
        "sms_freq",
        "monthly_spend",
        "topup_freq",
        "travel_score",
        "complaint_count",
        "tenure_months",
        "internet_service",
        "streaming_tv",
        "streaming_movies",
        "contract",
        "payment_method",
        "churn_label",
        "churn_value",
        "churn_score",
        "cltv",
    ]

    return features[feature_columns].copy()


def save_outputs(cleaned_df: pd.DataFrame, feature_df: pd.DataFrame) -> None:
    """Menyimpan dataset bersih dan feature table ke folder output."""
    cleaned_df.to_csv(PROCESSED_FILE, index=False)
    feature_df.to_csv(FEATURES_FILE, index=False)


def main() -> None:
    # Alur utama: siapkan folder, baca raw data, bersihkan, bentuk fitur, lalu simpan.
    ensure_output_dirs()
    raw_df = load_raw_dataset()
    cleaned_df = clean_dataset(raw_df)
    feature_df = build_feature_table(cleaned_df)
    save_outputs(cleaned_df, feature_df)

    print("Preprocessing selesai.")
    print(f"- Clean dataset: {PROCESSED_FILE}")
    print(f"- Feature table: {FEATURES_FILE}")
    print(f"- Total rows: {len(feature_df)}")


if __name__ == "__main__":
    main()
