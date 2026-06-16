from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
FEATURES_DIR = ROOT_DIR / "data" / "features"
INPUT_FILE = FEATURES_DIR / "telco_user_profile_features.csv"
OUTPUT_FILE = FEATURES_DIR / "telco_training_dataset_with_targets.csv"


def load_feature_table() -> pd.DataFrame:
    """Memuat feature table hasil preprocessing yang akan diberi label target."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Feature table belum ada. Jalankan preprocess dulu: {INPUT_FILE}"
        )

    return pd.read_csv(INPUT_FILE)


def assign_target_label(row: pd.Series) -> str:
    """Menentukan label rekomendasi berdasarkan rule bisnis sederhana."""
    monthly_spend = float(row["monthly_spend"])
    churn_score = float(row["churn_score"])
    cltv = float(row["cltv"])
    tenure = float(row["tenure_months"])
    phone_service = row["phone_service"]
    multiple_lines = row["multiple_lines"]
    internet_service = row["internet_service"]
    streaming_tv = row["streaming_tv"]
    streaming_movies = row["streaming_movies"]
    partner = row["partner"]
    dependents = row["dependents"]

    # Variabel bantu ini dipakai agar rule lebih mudah dibaca dan diubah.
    streaming_active = streaming_tv == "Yes" or streaming_movies == "Yes"
    premium_streaming = streaming_tv == "Yes" and streaming_movies == "Yes"
    internet_active = internet_service in {"Fiber optic", "DSL"}
    family_ready = (
        partner == "Yes"
        and dependents == "Yes"
        and phone_service == "Yes"
        and multiple_lines == "Yes"
        and internet_active
        and monthly_spend >= 70
    )

    # Prioritas pertama adalah retensi, karena user berisiko churn harus
    # diarahkan dulu ke paket yang bertujuan menjaga pelanggan tetap aktif.
    if churn_score >= 75 or row["churn_label"] == "Yes":
        return "Paket Retensi"

    # User dengan spend dan CLTV tinggi diarahkan ke paket data premium.
    if (
        monthly_spend >= 95
        and cltv >= 4000
        and internet_active
        and premium_streaming
    ):
        return "Paket Data Premium"

    # User dengan profil keluarga dibuat lebih spesifik agar tidak bercampur
    # terlalu banyak dengan kelas kuota besar.
    if family_ready:
        return "Paket Keluarga/Kombo"

    # User voice-only diarahkan ke paket telepon agar berbeda dari kelas data.
    if (
        phone_service == "Yes"
        and internet_service == "No"
        and multiple_lines != "Yes"
        and monthly_spend <= 55
    ):
        return "Paket Telepon"

    # User internet aktif dengan kebutuhan streaming masuk ke kelas kuota besar.
    if (
        internet_active
        and streaming_active
        and monthly_spend >= 60
    ):
        return "Paket Kuota Besar"

    # User baru dengan spend rendah diberi label paket pemula.
    if tenure <= 6 and monthly_spend < 60:
        return "Paket Pemula"

    # Fallback untuk user internet aktif tanpa sinyal premium yang kuat.
    if internet_active and monthly_spend >= 45:
        return "Paket Kuota Besar"

    # Fallback terakhir dipilih ke paket pemula agar semua baris punya label.
    return "Paket Pemula"


def build_training_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Menyalin feature table lalu menambahkan kolom target rekomendasi."""
    training_df = df.copy()
    training_df["target_rekomendasi"] = training_df.apply(assign_target_label, axis=1)
    return training_df


def main() -> None:
    # Alur utama: load fitur, bentuk target, simpan hasil, lalu tampilkan distribusi.
    feature_df = load_feature_table()
    training_df = build_training_dataset(feature_df)
    training_df.to_csv(OUTPUT_FILE, index=False)

    print("Target rekomendasi berhasil dibuat.")
    print(f"- Output: {OUTPUT_FILE}")
    print("- Distribusi target:")
    print(training_df["target_rekomendasi"].value_counts().to_string())


if __name__ == "__main__":
    main()
