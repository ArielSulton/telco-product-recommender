# %%
import joblib
import pandas as pd

# Load file pkl kamu
artifacts = joblib.load("ml/models/kaggle_rf/kaggle_rf_recommender.pkl")

# Ambil informasi model atau list fiturnya
model = artifacts["model"]
fitur = artifacts["feature_columns"]

print(f"Jumlah pohon keputusan: {model.n_estimators}")

# Mengubah daftar fitur menjadi DataFrame agar bisa diintip seperti Excel
df_fitur = pd.DataFrame(fitur, columns=["Nama Fitur"])

df_fitur.to_csv("daftar_fitur.csv", index=False)
# %%
importance = pd.DataFrame({
    "Feature": fitur,
    "Importance": model.feature_importances_
})

importance = importance.sort_values(
    by="Importance",
    ascending=False
)

print(importance.head(20))

importance.to_csv(
    "feature_importance.csv",
    index=False
)