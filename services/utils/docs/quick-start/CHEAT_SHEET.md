# Cheat Sheet - Quick Commands

## 🔧 Development

### Start/Stop
```bash
# Start all
docker compose -f compose.dev.yaml up -d

# Stop all
docker compose down

# Restart service
docker compose restart backend
```

### Access
- Frontend: http://localhost:5173
- Backend: http://localhost:8000/api/v1/docs
- MLflow: http://localhost:5000
- Airflow: http://localhost:8080 (admin/admin)
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

### Debug
```bash
# Logs
docker compose logs -f backend
docker compose logs -f postgres

# Check status
docker compose ps

# Exec into container
docker compose exec backend bash
```

---

## 🚀 Production

### Deploy
```bash
# Start
docker compose -f compose.prod.yaml up -d

# Update
git pull
docker compose -f compose.prod.yaml build
docker compose -f compose.prod.yaml up -d

# Rollback
git checkout <version>
docker compose -f compose.prod.yaml up -d
```

### Monitor
```bash
# Health
curl https://api.yourdomain.com/health

# Logs
docker compose -f compose.prod.yaml logs -f

# Stats
docker stats
```

### Backup
```bash
# DB backup
docker compose exec postgres pg_dump -U postgres telco_recommender > backup.sql

# Restore
cat backup.sql | docker compose exec -T postgres psql -U postgres telco_recommender
```

---

## 🧪 Testing

```bash
# Unit tests
python tests/test_sprint1.py
python tests/test_sprint2.py
python tests/test_sprint3.py

# E2E test
python scripts/test_e2e_production.py

# Security audit
python scripts/security_audit.py --target http://localhost:8000
```

---

## 🔑 Generate Secrets

```bash
# Random key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Fernet key (Airflow)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 🆘 Emergency

```bash
# Full reset
docker compose down -v
docker compose -f compose.dev.yaml up -d

# Fix database
docker compose restart postgres
docker compose exec postgres psql -U postgres

# Clear cache
docker compose exec redis redis-cli FLUSHALL
```
