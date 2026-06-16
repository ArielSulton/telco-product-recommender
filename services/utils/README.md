# Services Utils

Folder ini berisi dokumentasi lama, test utility, script pendukung, dan catatan implementasi project.

## Status

Sebagian isi folder ini berasal dari fase sprint awal dan masih menyebut arsitektur lama seperti K-Means, LightFM, dan XGBoost. Untuk kondisi aplikasi aktif saat ini, rujukan utama adalah:

- `README.md`
- `backend/README.md`
- `frontend/README.md`
- `ml/README.md`
- `infrastructure/README.md`

## Isi Folder

```text
services/utils/
|-- docs/                  Dokumentasi pendukung dan arsip sprint
`-- tests/                 Script test integration, frontend, security, dan e2e
```

## Test Utility

Beberapa test di folder ini masih berguna untuk validasi umum, tetapi belum semuanya disesuaikan dengan RF v2.

Contoh yang masih relevan:

```bash
python services/utils/tests/e2e/test_e2e_production.py --base-url http://localhost:8000
python services/utils/tests/security/security_audit.py --target http://localhost:8000
bash services/utils/tests/frontend/verify_frontend.sh
```

## Catatan

Jika ada perbedaan antara dokumentasi di `services/utils/docs/` dan README utama, ikuti README utama karena sudah disesuaikan dengan implementasi terbaru.
