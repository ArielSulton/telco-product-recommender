"""
Generate synthetic transactions and events for the Kaggle-based telco dataset.

The generated data is not purely random. It follows the recommendation label
assigned to each user so the application can retain purchase history and
interaction flows that feel realistic enough for development and testing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from random import Random
from typing import Dict, List

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
FEATURES_DIR = ROOT_DIR / "data" / "features"
OUTPUT_TRANSACTIONS = FEATURES_DIR / "telco_synthetic_transactions.csv"
OUTPUT_EVENTS = FEATURES_DIR / "telco_synthetic_events.csv"
INPUT_FILE = FEATURES_DIR / "telco_training_dataset_with_targets.csv"


# RNG dibuat tetap agar data sintetis bisa direproduksi dengan hasil yang konsisten.
RNG = Random(42)
BASE_DATE = datetime(2026, 5, 1, 9, 0, 0)


# Pemetaan ini menjelaskan produk kandidat untuk tiap label rekomendasi.
PRODUCT_CATALOG: Dict[str, List[Dict[str, object]]] = {
    "Paket Pemula": [
        {
            "product_id": "IDN001",
            "product_name": "Paket Awal Hemat 2GB",
            "product_family": "data",
            "price": 15000,
        },
        {
            "product_id": "IDN002",
            "product_name": "Paket Awal Sosmed 4GB",
            "product_family": "data",
            "price": 25000,
        },
        {
            "product_id": "IDN003",
            "product_name": "Paket Awal Kombo 5GB",
            "product_family": "combo",
            "price": 35000,
        },
    ],
    "Paket Kuota Besar": [
        {
            "product_id": "IDN004",
            "product_name": "Paket Kuota Besar 25GB",
            "product_family": "data",
            "price": 75000,
        },
        {
            "product_id": "IDN005",
            "product_name": "Paket Kuota Besar 50GB",
            "product_family": "data",
            "price": 115000,
        },
        {
            "product_id": "IDN006",
            "product_name": "Paket Kuota Besar 100GB",
            "product_family": "data",
            "price": 165000,
        },
    ],
    "Paket Telepon": [
        {
            "product_id": "IDN007",
            "product_name": "Paket Telepon Hemat 300 Menit",
            "product_family": "voice",
            "price": 20000,
        },
        {
            "product_id": "IDN008",
            "product_name": "Paket Telepon Bebas 750 Menit",
            "product_family": "voice",
            "price": 40000,
        },
        {
            "product_id": "IDN009",
            "product_name": "Paket Telepon Maksimal 1000 Menit",
            "product_family": "voice",
            "price": 60000,
        },
    ],
    "Paket Keluarga/Kombo": [
        {
            "product_id": "IDN010",
            "product_name": "Paket Keluarga Kombo 20GB",
            "product_family": "combo",
            "price": 85000,
        },
        {
            "product_id": "IDN011",
            "product_name": "Paket Keluarga Berbagi 40GB",
            "product_family": "combo",
            "price": 135000,
        },
        {
            "product_id": "IDN012",
            "product_name": "Paket Keluarga Maksimal 75GB",
            "product_family": "combo",
            "price": 195000,
        },
    ],
    "Paket Retensi": [
        {
            "product_id": "IDN013",
            "product_name": "Paket Setia Hemat 8GB",
            "product_family": "combo",
            "price": 30000,
        },
        {
            "product_id": "IDN014",
            "product_name": "Paket Setia Kombo 15GB",
            "product_family": "combo",
            "price": 50000,
        },
        {
            "product_id": "IDN015",
            "product_name": "Paket Kembali Aktif 25GB",
            "product_family": "combo",
            "price": 65000,
        },
    ],
    "Paket Data Premium": [
        {
            "product_id": "IDN016",
            "product_name": "Paket Premium Streaming 50GB",
            "product_family": "data",
            "price": 135000,
        },
        {
            "product_id": "IDN017",
            "product_name": "Paket Premium Tanpa Batas",
            "product_family": "data",
            "price": 185000,
        },
        {
            "product_id": "IDN018",
            "product_name": "Paket Premium Jelajah 75GB",
            "product_family": "data",
            "price": 210000,
        },
    ],
}


# Pola event tiap kelas dibuat berbeda agar perilaku sintetis terasa lebih masuk akal.
EVENT_PLAN = {
    "Paket Pemula": {"view": (6, 10), "click": (2, 4), "checkout": (1, 2), "purchase": (1, 1)},
    "Paket Kuota Besar": {"view": (10, 18), "click": (4, 7), "checkout": (1, 3), "purchase": (1, 2)},
    "Paket Telepon": {"view": (5, 9), "click": (2, 4), "checkout": (1, 2), "purchase": (1, 1)},
    "Paket Keluarga/Kombo": {"view": (8, 14), "click": (3, 6), "checkout": (1, 3), "purchase": (1, 2)},
    "Paket Retensi": {"view": (9, 15), "click": (3, 6), "checkout": (1, 3), "purchase": (0, 1)},
    "Paket Data Premium": {"view": (12, 20), "click": (5, 8), "checkout": (2, 4), "purchase": (1, 2)},
}


def load_training_dataset() -> pd.DataFrame:
    """Memuat dataset utama yang sudah memiliki target rekomendasi."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Dataset target belum ada. Jalankan build target dulu: {INPUT_FILE}"
        )
    return pd.read_csv(INPUT_FILE)


def sample_count(min_max: tuple[int, int]) -> int:
    """Mengambil jumlah event dalam rentang yang sudah didefinisikan."""
    return RNG.randint(min_max[0], min_max[1])


def choose_product(label: str, purchase: bool = False) -> Dict[str, object]:
    """Memilih produk kandidat untuk event biasa atau event pembelian."""
    candidates = PRODUCT_CATALOG[label]
    if purchase and len(candidates) > 1:
        weights = [0.55, 0.30, 0.15][:len(candidates)]
        return RNG.choices(candidates, weights=weights, k=1)[0]
    return RNG.choice(candidates)


def create_transactions_and_events(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Membuat data transaksi dan event sintetis untuk setiap customer."""
    transactions = []
    events = []

    for idx, row in df.iterrows():
        # Tiap customer mengikuti pola event berdasarkan label rekomendasinya.
        customer_id = row["customer_id"]
        label = row["target_rekomendasi"]
        plan = EVENT_PLAN[label]
        user_base_date = BASE_DATE - timedelta(days=RNG.randint(1, 180))

        views = sample_count(plan["view"])
        clicks = sample_count(plan["click"])
        checkouts = sample_count(plan["checkout"])
        purchases = sample_count(plan["purchase"])

        session_counter = 1

        # Event view, click, dan checkout dibuat lebih dulu sebagai jejak interaksi.
        for event_type, total in [
            ("view", views),
            ("click", clicks),
            ("checkout", checkouts),
        ]:
            for i in range(total):
                product = choose_product(label, purchase=False)
                event_time = user_base_date + timedelta(
                    days=RNG.randint(0, 150),
                    minutes=(idx + i + session_counter) * 7,
                )
                events.append(
                    {
                        "customer_id": customer_id,
                        "product_id": product["product_id"],
                        "product_name": product["product_name"],
                        "product_family": product["product_family"],
                        "event_type": event_type,
                        "timestamp": event_time.isoformat(),
                        "session_id": f"{customer_id}-session-{session_counter}",
                        "metadata": (
                            f"label={label};monthly_spend={row['monthly_spend']};"
                            f"churn_score={row['churn_score']}"
                        ),
                    }
                )
                session_counter += 1

        # Event purchase sekaligus menghasilkan data transaksi completed.
        for i in range(purchases):
            product = choose_product(label, purchase=True)
            purchase_time = user_base_date + timedelta(
                days=RNG.randint(0, 150),
                minutes=(idx + i + session_counter) * 11,
            )
            purchase_id = f"{customer_id}-purchase-{i + 1}"

            events.append(
                {
                    "customer_id": customer_id,
                    "product_id": product["product_id"],
                    "product_name": product["product_name"],
                    "product_family": product["product_family"],
                    "event_type": "purchase",
                    "timestamp": purchase_time.isoformat(),
                    "session_id": f"{customer_id}-session-{session_counter}",
                    "metadata": (
                        f"label={label};payment_method={row['payment_method']};"
                        f"tenure_months={row['tenure_months']}"
                    ),
                }
            )

            transactions.append(
                {
                    "transaction_id": purchase_id,
                    "customer_id": customer_id,
                    "product_id": product["product_id"],
                    "product_name": product["product_name"],
                    "product_family": product["product_family"],
                    "price": product["price"],
                    "payment_method": row["payment_method"],
                    "status": "completed",
                    "purchase_date": purchase_time.isoformat(),
                    "target_rekomendasi": label,
                }
            )
            session_counter += 1

    # Hasil akhir diubah menjadi DataFrame agar mudah disimpan dan digabung.
    transaction_df = pd.DataFrame(transactions)
    events_df = pd.DataFrame(events)

    return transaction_df, events_df


def main() -> None:
    # Alur utama: load dataset target, buat data sintetis, lalu simpan ke CSV.
    training_df = load_training_dataset()
    transactions_df, events_df = create_transactions_and_events(training_df)

    transactions_df.to_csv(OUTPUT_TRANSACTIONS, index=False)
    events_df.to_csv(OUTPUT_EVENTS, index=False)

    print("Data dummy/sintetis berhasil dibuat.")
    print(f"- Transactions: {OUTPUT_TRANSACTIONS}")
    print(f"- Events: {OUTPUT_EVENTS}")
    print(f"- Total transactions: {len(transactions_df)}")
    print(f"- Total events: {len(events_df)}")


if __name__ == "__main__":
    main()
