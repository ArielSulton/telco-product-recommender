"""
Generate evaluation plots for the Kaggle-based Random Forest model.

The output figures are intended for reporting and chapter-4 style model
evaluation, so the script saves ready-to-use PNG files alongside a CSV
summary of the classification report.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, top_k_accuracy_score
from sklearn.model_selection import train_test_split


ROOT_DIR = Path(__file__).resolve().parents[1]
FEATURES_DIR = ROOT_DIR / "data" / "features"
MODEL_DIR = ROOT_DIR / "models" / "kaggle_rf"
PLOTS_DIR = MODEL_DIR / "evaluation_plots"

TRAINING_FILE = FEATURES_DIR / "telco_training_dataset_with_targets.csv"
SYNTHETIC_TX_FILE = FEATURES_DIR / "telco_synthetic_transactions.csv"
SYNTHETIC_EVENTS_FILE = FEATURES_DIR / "telco_synthetic_events.csv"
MODEL_FILE = MODEL_DIR / "kaggle_rf_recommender.pkl"
SUMMARY_FILE = PLOTS_DIR / "evaluation_summary.json"
REPORT_FILE = PLOTS_DIR / "classification_report.csv"
TOP3_MATRIX_FILE = PLOTS_DIR / "top3_hit_matrix.csv"


def ensure_output_dir() -> None:
    """Membuat folder output grafik evaluasi."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Memuat dataset training, data sintetis, dan artifact model."""
    if not TRAINING_FILE.exists():
        raise FileNotFoundError(f"Training dataset tidak ditemukan: {TRAINING_FILE}")
    if not MODEL_FILE.exists():
        raise FileNotFoundError(f"Model artifact tidak ditemukan: {MODEL_FILE}")

    df = pd.read_csv(TRAINING_FILE)
    tx_df = pd.read_csv(SYNTHETIC_TX_FILE) if SYNTHETIC_TX_FILE.exists() else pd.DataFrame()
    events_df = pd.read_csv(SYNTHETIC_EVENTS_FILE) if SYNTHETIC_EVENTS_FILE.exists() else pd.DataFrame()
    artifacts = joblib.load(MODEL_FILE)
    return df, tx_df, events_df, artifacts


def add_behavior_aggregates(df: pd.DataFrame, tx_df: pd.DataFrame, events_df: pd.DataFrame) -> pd.DataFrame:
    """Menambahkan agregasi transaksi dan event ke dataset utama."""
    enriched = df.copy()

    # Total purchase dan total spend dipakai sebagai ringkasan histori transaksi.
    if not tx_df.empty:
        tx_agg = tx_df.groupby("customer_id").agg(
            total_purchases=("transaction_id", "count"),
            total_transaction_spend=("price", "sum"),
        ).reset_index()
        enriched = enriched.merge(tx_agg, on="customer_id", how="left")
    else:
        enriched["total_purchases"] = 0
        enriched["total_transaction_spend"] = 0

    # Event view, click, checkout, dan purchase diubah menjadi hitungan per user.
    if not events_df.empty:
        event_counts = (
            events_df.pivot_table(
                index="customer_id",
                columns="event_type",
                values="product_id",
                aggfunc="count",
                fill_value=0,
            )
            .reset_index()
        )
        event_counts.columns = [
            "customer_id" if col == "customer_id" else f"event_{col}"
            for col in event_counts.columns
        ]
        enriched = enriched.merge(event_counts, on="customer_id", how="left")

    # Nilai kosong diisi nol agar aman dipakai untuk evaluasi ulang model.
    for col in [
        "total_purchases",
        "total_transaction_spend",
        "event_checkout",
        "event_click",
        "event_purchase",
        "event_view",
    ]:
        if col not in enriched.columns:
            enriched[col] = 0
        enriched[col] = enriched[col].fillna(0)

    return enriched


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Membentuk kembali fitur engineered yang sama seperti saat training notebook."""
    engineered = df.copy()
    engineered["recency"] = 1 / (engineered["complaint_count"] + 1)
    engineered["frequency"] = engineered["topup_freq"]
    engineered["monetary"] = engineered["monthly_spend"]
    engineered["arpu"] = engineered["monthly_spend"]
    engineered["avg_spend_per_topup"] = engineered["monthly_spend"] / (engineered["topup_freq"] + 1)
    engineered["data_intensity"] = engineered["avg_data_usage_gb"] / (engineered["monthly_spend"] + 1)
    engineered["communication_intensity"] = engineered["avg_call_duration"] + engineered["sms_freq"]
    engineered["freq_x_monetary"] = engineered["frequency"] * engineered["monetary"]
    engineered["arpu_per_data"] = engineered["arpu"] / (engineered["avg_data_usage_gb"] + 1)
    engineered["loyalty_score"] = (
        (engineered["tenure_months"] / (engineered["tenure_months"].max() + 1)) * 0.4
        + (engineered["cltv"] / (engineered["cltv"].max() + 1)) * 0.4
        + ((100 - engineered["churn_score"]) / 100) * 0.2
    )
    return engineered


def encode_features(df: pd.DataFrame, artifacts: dict) -> tuple[pd.DataFrame, pd.Series, list[str], list[str]]:
    """Mengubah fitur kategorikal ke bentuk numerik memakai encoder model yang sama."""
    encoded = df.copy()
    label_encoders = artifacts["label_encoders"]
    target_encoder = artifacts["target_encoder"]
    feature_columns = artifacts["feature_columns"]
    target_classes = list(artifacts["target_classes"])

    for col, encoder in label_encoders.items():
        encoded[f"{col}_encoded"] = encoder.transform(encoded[col].astype(str))

    encoded["target_encoded"] = target_encoder.transform(encoded["target_rekomendasi"])
    X = encoded[feature_columns]
    y = encoded["target_encoded"]
    return X, y, feature_columns, target_classes


def recreate_test_split(X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Membuat ulang split train-test agar evaluasi konsisten dengan notebook."""
    return train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )


def save_confusion_matrix(cm: pd.DataFrame, labels: list[str]) -> None:
    """Menyimpan heatmap confusion matrix untuk analisis klasifikasi."""
    plt.figure(figsize=(10, 7))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
    )
    plt.title("Confusion Matrix Random Forest")
    plt.xlabel("Prediksi")
    plt.ylabel("Label Aktual")
    plt.xticks(rotation=25, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "confusion_matrix_rf.png", dpi=300, bbox_inches="tight")
    plt.close()


def save_top3_hit_matrix(y_test: pd.Series, y_proba, labels: list[str]) -> pd.DataFrame:
    """Menyimpan matrix hit/miss Top-3 per kelas aktual."""
    top3_indices = y_proba.argsort(axis=1)[:, -3:][:, ::-1]
    y_true = y_test.to_numpy()
    top3_hits = [true_label in predicted_top3 for true_label, predicted_top3 in zip(y_true, top3_indices)]

    matrix_df = pd.DataFrame(
        {
            "Masuk Top-3": 0,
            "Tidak Masuk Top-3": 0,
        },
        index=labels,
    )

    for true_label, is_hit in zip(y_true, top3_hits):
        label_name = labels[int(true_label)]
        column = "Masuk Top-3" if is_hit else "Tidak Masuk Top-3"
        matrix_df.loc[label_name, column] += 1

    matrix_df["Total"] = matrix_df["Masuk Top-3"] + matrix_df["Tidak Masuk Top-3"]
    matrix_df["Top-3 Accuracy"] = matrix_df["Masuk Top-3"] / matrix_df["Total"]
    matrix_df.to_csv(TOP3_MATRIX_FILE, encoding="utf-8-sig")

    plt.figure(figsize=(9, 6))
    sns.heatmap(
        matrix_df[["Masuk Top-3", "Tidak Masuk Top-3"]],
        annot=True,
        fmt="d",
        cmap="Greens",
    )
    plt.title("Top-3 Hit Matrix Random Forest")
    plt.xlabel("Status")
    plt.ylabel("Label Aktual")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "top3_hit_matrix_rf.png", dpi=300, bbox_inches="tight")
    plt.close()

    return matrix_df


def save_feature_importance(model, feature_columns: list[str]) -> None:
    """Menyimpan grafik fitur paling berpengaruh pada model."""
    importance_df = (
        pd.DataFrame(
            {
                "feature": feature_columns,
                "importance": model.feature_importances_,
            }
        )
        .sort_values("importance", ascending=False)
        .head(12)
    )

    plt.figure(figsize=(10, 6))
    sns.barplot(data=importance_df, x="importance", y="feature", palette="viridis")
    plt.title("Top 12 Feature Importance Random Forest")
    plt.xlabel("Importance")
    plt.ylabel("Fitur")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "feature_importance_rf.png", dpi=300, bbox_inches="tight")
    plt.close()


def save_target_distribution(df: pd.DataFrame) -> None:
    """Menyimpan grafik distribusi target rekomendasi."""
    dist_df = (
        df["target_rekomendasi"]
        .value_counts()
        .rename_axis("label")
        .reset_index(name="jumlah")
    )

    plt.figure(figsize=(10, 6))
    sns.barplot(data=dist_df, x="jumlah", y="label", palette="crest")
    plt.title("Distribusi Target Rekomendasi")
    plt.xlabel("Jumlah Data")
    plt.ylabel("Label")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "distribusi_target_rf.png", dpi=300, bbox_inches="tight")
    plt.close()


def save_classification_metrics(report_df: pd.DataFrame) -> None:
    """Menyimpan grafik precision, recall, dan F1-score per kelas."""
    class_metrics = report_df.loc[
        ~report_df.index.isin(["accuracy", "macro avg", "weighted avg"])
    ].reset_index(names="label")
    melted = class_metrics.melt(
        id_vars="label",
        value_vars=["precision", "recall", "f1-score"],
        var_name="metric",
        value_name="score",
    )

    plt.figure(figsize=(12, 6))
    sns.barplot(data=melted, x="label", y="score", hue="metric", palette="Set2")
    plt.title("Perbandingan Precision, Recall, dan F1-Score per Kelas")
    plt.xlabel("Label")
    plt.ylabel("Skor")
    plt.xticks(rotation=20, ha="right")
    plt.ylim(0, 1.05)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "classification_metrics_rf.png", dpi=300, bbox_inches="tight")
    plt.close()


def save_prediction_comparison(y_test_labels: list[str], y_pred_labels: list[str], labels: list[str]) -> None:
    """Menyimpan perbandingan distribusi label aktual dan hasil prediksi."""
    comparison_df = pd.DataFrame(
        {
            "Aktual": pd.Series(y_test_labels).value_counts().reindex(labels, fill_value=0),
            "Prediksi": pd.Series(y_pred_labels).value_counts().reindex(labels, fill_value=0),
        }
    ).reset_index(names="label")
    melted = comparison_df.melt(id_vars="label", var_name="jenis", value_name="jumlah")

    plt.figure(figsize=(11, 6))
    sns.barplot(data=melted, x="label", y="jumlah", hue="jenis", palette="magma")
    plt.title("Perbandingan Distribusi Label Aktual vs Prediksi")
    plt.xlabel("Label")
    plt.ylabel("Jumlah")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "aktual_vs_prediksi_rf.png", dpi=300, bbox_inches="tight")
    plt.close()


def main() -> None:
    # Alur utama: load data dan model, bangun ulang fitur, hitung metrik, lalu simpan plot.
    ensure_output_dir()
    df, tx_df, events_df, artifacts = load_inputs()
    df = add_behavior_aggregates(df, tx_df, events_df)
    df = engineer_features(df)
    X, y, feature_columns, target_classes = encode_features(df, artifacts)
    _, X_test, _, y_test = recreate_test_split(X, y)

    # Prediksi ulang pada test split dipakai untuk menghasilkan grafik evaluasi.
    model = artifacts["model"]
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    top3_accuracy = top_k_accuracy_score(y_test, y_proba, k=3)
    report = classification_report(
        y_test,
        y_pred,
        target_names=target_classes,
        output_dict=True,
        zero_division=0,
    )
    report_df = pd.DataFrame(report).transpose()
    report_df.to_csv(REPORT_FILE, encoding="utf-8-sig")

    cm = confusion_matrix(y_test, y_pred)
    save_confusion_matrix(cm, target_classes)
    top3_matrix_df = save_top3_hit_matrix(y_test, y_proba, target_classes)
    save_feature_importance(model, feature_columns)
    save_target_distribution(df)
    save_classification_metrics(report_df)

    target_encoder = artifacts["target_encoder"]
    y_test_labels = target_encoder.inverse_transform(y_test)
    y_pred_labels = target_encoder.inverse_transform(y_pred)
    save_prediction_comparison(y_test_labels, y_pred_labels, target_classes)

    # Ringkasan evaluasi disimpan agar mudah diambil lagi saat penulisan laporan.
    summary = {
        "accuracy": round(float(accuracy), 4),
        "top3_accuracy": round(float(top3_accuracy), 4),
        "plot_dir": str(PLOTS_DIR),
        "classification_report_csv": str(REPORT_FILE),
        "top3_hit_matrix_csv": str(TOP3_MATRIX_FILE),
        "top3_hit_total": int(top3_matrix_df["Masuk Top-3"].sum()),
        "top3_miss_total": int(top3_matrix_df["Tidak Masuk Top-3"].sum()),
    }
    with open(SUMMARY_FILE, "w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print("Plot evaluasi berhasil dibuat.")
    print(f"- Folder output: {PLOTS_DIR}")
    print(f"- Accuracy: {summary['accuracy']}")
    print(f"- Top-3 Accuracy: {summary['top3_accuracy']}")
    print(f"- Ringkasan metrik: {SUMMARY_FILE}")
    print(f"- Classification report CSV: {REPORT_FILE}")
    print(f"- Top-3 hit matrix CSV: {TOP3_MATRIX_FILE}")


if __name__ == "__main__":
    main()
