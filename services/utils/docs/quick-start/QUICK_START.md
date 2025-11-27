# Quick Start Guide - Development & Production

Panduan super singkat untuk setup dan run sistem di development dan production.

---

## 🔧 Development Environment

### Prerequisites
```bash
# Yang harus ada:
- Docker Desktop
- 8GB RAM
- 20GB disk space
```

### Setup & Run (5 menit)
```bash
# 1. Masuk ke folder project
cd "/home/arielsulton/Documents/Stargazing Project/VScode Project/dicoding/ASAH Capstone"

# 2. Copy environment file
cp .env.example .env
# (Bisa skip edit, default values sudah OK)

# 3. Start semua services
docker compose -f compose.dev.yaml up -d

# 4. Tunggu 2-3 menit sampai semua ready
docker compose ps

# 5. Done! Akses aplikasik
```

### Access URLs
| Service | URL | Login |
|---------|-----|-------|
| Frontend | http://localhost:5173 | - |
| Backend API | http://localhost:8000/api/v1/docs | - |
| Airflow | http://localhost:8080 | admin/admin |
| MLflow | http://localhost:5000 | - |
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | - |

### Test API
```bash
# Health check
curl http://localhost:8000/health

# Get recommendations
curl -X POST http://localhost:8000/api/v1/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id": "123e4567-e89b-12d3-a456-426614174000", "limit": 5}'
```

### Stop Services
```bash
# Stop (data tetap ada)
docker compose down

# Stop + hapus semua data (fresh start)
docker compose down -v
```

---

## 🚀 Production Environment

### Prerequisites
```bash
# Yang harus ada:
- Server Linux (Ubuntu 20.04+)
- Docker + Docker Compose
- Domain name (optional)
- 16GB RAM (recommended)
- 50GB disk space
```

### Setup & Deploy

#### 1. Preparation
```bash
# Clone/upload project ke server
cd /var/www/telco-recommender

# Copy production env
cp .env.example .env.prod

# Edit dengan production values
nano .env.prod
```

#### 2. Configure .env.prod
```bash
# REQUIRED CHANGES:
ENVIRONMENT=production

# Database
DATABASE_PASSWORD=<strong-password>
DATABASE_HOST=postgres

# Security
SECRET_KEY=<generate-random-key>
JWT_SECRET_KEY=<generate-random-key>

# Redis
REDIS_PASSWORD=<strong-password>

# Airflow
AIRFLOW_FERNET_KEY=<generate-fernet-key>
AIRFLOW_SECRET_KEY=<generate-random-key>

# Domain (if using)
BACKEND_URL=https://api.yourdomain.com
FRONTEND_URL=https://yourdomain.com
```

#### 3. Generate Secrets
```bash
# Generate secret keys
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate Fernet key (for Airflow)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### 4. Deploy
```bash
# Start production services
docker compose -f compose.prod.yaml up -d

# Check all services running
docker compose -f compose.prod.yaml ps

# Check logs
docker compose -f compose.prod.yaml logs -f
```

#### 5. Verify Deployment
```bash
# Run E2E test
python scripts/test_e2e_production.py --base-url http://localhost:8000

# Run security audit
python scripts/security_audit.py --target http://localhost:8000

# Expected: All tests passing
```

### Production URLs
```bash
# Access (ganti dengan domain kamu)
Frontend: https://yourdomain.com
Backend:  https://api.yourdomain.com
Grafana:  https://monitor.yourdomain.com:3000
```

### SSL/HTTPS Setup (Optional)
```bash
# Using nginx + Let's Encrypt
apt install nginx certbot python3-certbot-nginx

# Get SSL certificate
certbot --nginx -d yourdomain.com -d api.yourdomain.com

# Auto-renew
certbot renew --dry-run
```

### Monitoring & Maintenance
```bash
# Check system health
docker compose -f compose.prod.yaml ps
curl https://api.yourdomain.com/health/ready

# View Grafana dashboards
open https://monitor.yourdomain.com:3000

# Check logs
docker compose -f compose.prod.yaml logs backend -f
docker compose -f compose.prod.yaml logs airflow-scheduler -f

# Restart service jika perlu
docker compose -f compose.prod.yaml restart backend
```

### Backup & Restore
```bash
# Backup database
docker compose exec postgres pg_dump -U postgres telco_recommender > backup.sql

# Restore database
cat backup.sql | docker compose exec -T postgres psql -U postgres telco_recommender

# Backup MLflow artifacts
docker compose exec mlflow tar czf /mlflow/backup.tar.gz /mlflow/artifacts
```

### Update/Rollback
```bash
# Update to new version
git pull
docker compose -f compose.prod.yaml build
docker compose -f compose.prod.yaml up -d

# Rollback jika ada masalah
git checkout <previous-version>
docker compose -f compose.prod.yaml up -d
```

### Stop Production
```bash
# Stop services (data tetap ada)
docker compose -f compose.prod.yaml down

# DANGER: Stop + hapus data
docker compose -f compose.prod.yaml down -v
```

---

## 📊 Quick Comparison

| Aspect | Development | Production |
|--------|-------------|------------|
| File | compose.dev.yaml | compose.prod.yaml |
| Environment | .env | .env.prod |
| Replicas | 1 backend | 2 backend |
| Logging | Console | JSON files |
| Security | Relaxed | Strict |
| Monitoring | Basic | Full (Prometheus/Grafana) |
| Database | Default password | Strong password |
| SSL | No | Yes (recommended) |
| Domain | localhost | yourdomain.com |

---

## 🆘 Troubleshooting

### Dev Environment
```bash
# Services tidak start
docker compose down -v
docker compose -f compose.dev.yaml up -d

# Port sudah dipakai
sudo lsof -i :8000  # Cari yang pakai port
docker compose down  # Stop services

# Database error
docker compose logs postgres
docker compose restart postgres
```

### Production Environment
```bash
# Services unhealthy
docker compose -f compose.prod.yaml ps
docker compose -f compose.prod.yaml logs <service-name>

# High memory usage
docker stats
docker compose -f compose.prod.yaml down
# Edit compose.prod.yaml - adjust resource limits

# Security audit fails
python scripts/security_audit.py --target http://localhost:8000
# Check output, fix issues reported
```

---

## 📚 Next Steps

**After Dev Setup:**
1. Test frontend: http://localhost:5173
2. Test API: http://localhost:8000/api/v1/docs
3. Trigger Airflow DAG: http://localhost:8080
4. View Grafana: http://localhost:3000

**After Prod Setup:**
1. Setup domain & SSL
2. Configure firewall
3. Setup backup schedule
4. Configure monitoring alerts
5. Setup log rotation

---

## 💡 Tips

**Development:**
- Gunakan `docker compose logs -f` untuk debug
- Edit code langsung, auto-reload aktif
- Data tetap ada setelah restart (kecuali pakai `-v`)

**Production:**
- Selalu backup sebelum update
- Monitor Grafana untuk performance
- Setup automated backups
- Use strong passwords
- Enable SSL/HTTPS
- Setup firewall rules

---

**Need Help?**
- Dev: Check `docs/TROUBLESHOOTING_GUIDE.md`
- Prod: Check `docs/DEPLOYMENT_GUIDE.md`

---

**Last Updated**: November 8, 2024
