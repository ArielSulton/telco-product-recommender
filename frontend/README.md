# Frontend - Paketify Web App

Frontend ini adalah aplikasi React + Vite untuk pengguna dan admin Paketify.

## Stack

- React 18
- Vite
- Tailwind CSS
- React Router
- Axios
- Context API
- Lucide React icons

## Fitur Pengguna

- Register dan login.
- Onboarding preferensi rekomendasi.
- Dashboard pengguna.
- Kartu profil rekomendasi Random Forest v2.
- Rekomendasi paket personal.
- Daftar paket aktif.
- Riwayat transaksi.
- Pembelian paket.
- Form keluhan pengguna.

## Fitur Admin

- Dashboard admin.
- Melihat ringkasan produk dan rekomendasi pengguna.
- Menambah, mengedit, dan menghapus produk.
- Mengelola metadata produk:
  - kategori rekomendasi
  - tags
  - ikut rekomendasi
- Melihat keluhan pengguna.
- Mengubah status keluhan menjadi `reviewed` atau `resolved`.
- Melihat informasi model Random Forest v2.

## Menjalankan Frontend

Dari root project dengan Docker:

```bash
docker compose -f compose.dev.yaml up -d frontend
```

Atau lokal:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Buka:

```text
http://localhost:5173
```

## Build

```bash
cd frontend
npm run build
```

## Environment

Frontend development memakai:

```text
VITE_API_URL=http://localhost:8000/api/v1
```

## File Penting

```text
src/pages/DashboardPage.jsx
src/pages/AdminDashboardPage.jsx
src/pages/ProductsPage.jsx
src/pages/AboutPage.jsx
src/components/RecommendationWidget.jsx
src/components/ProductCard.jsx
src/context/RecommendationContext.jsx
src/services/api.js
src/services/recommendationService.js
```

## Catatan

Tampilan dashboard saat ini sudah disesuaikan dengan model Random Forest v2. Istilah lama seperti K-Means segmentation, LightFM, dan XGBoost tidak dipakai sebagai informasi model utama di UI aktif.
