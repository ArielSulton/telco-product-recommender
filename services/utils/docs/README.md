# Documentation Archive

Folder ini berisi dokumentasi pendukung, arsip sprint, deployment notes, dan catatan teknis dari fase pengembangan project.

## Rujukan Utama Saat Ini

Untuk kondisi project terbaru, gunakan README berikut:

```text
README.md
backend/README.md
frontend/README.md
ml/README.md
infrastructure/README.md
```

## Isi Dokumentasi

```text
services/utils/docs/
|-- deployment/       Catatan deployment dan production readiness
|-- documentation/    Dokumentasi API, monitoring, troubleshooting, dan arsitektur
|-- quick-start/      Panduan quick start lama
`-- sprints/          Catatan implementasi per sprint
```

## Catatan Penting

Beberapa dokumen di folder ini masih menyebut arsitektur lama seperti:

- K-Means segmentation
- LightFM collaborative filtering
- XGBoost ranking
- target performa sprint awal

Arsitektur aktif aplikasi web saat ini menggunakan Random Forest v2 sebagai rekomendasi utama melalui:

```text
POST /api/v1/recommend/v2
```

Dokumen lama tetap disimpan sebagai arsip proses pengembangan.
