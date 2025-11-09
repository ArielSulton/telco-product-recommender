# 🚀 Dokploy Deployment Guide

## ✅ Status: READY FOR DOKPLOY!

Sistem ini **SUDAH SIAP** untuk di-deploy ke Dokploy di VPS. Semua konfigurasi sudah lengkap.

---

## 📋 Pre-Deployment Checklist

### ✅ Yang Sudah Ada:
- [x] `compose.prod.yaml` - Production Docker Compose
- [x] Dockerfiles untuk semua services (4 files)
- [x] Traefik labels (backend, frontend, grafana)
- [x] Environment variables template (`.env.example`)
- [x] Health checks untuk semua services
- [x] Resource limits (CPU & Memory)
- [x] Logging configuration
- [x] Persistent volumes
- [x] Network configuration
- [x] Security headers & authentication
- [x] Monitoring stack (Prometheus + Grafana)

### ✅ Dockerfiles Available:
```
✅ backend/Dockerfile         (FastAPI - multi-stage)
✅ frontend/Dockerfile        (React - multi-stage)
✅ services/data-simulator/Dockerfile
✅ ml/Dockerfile              (ML training)
```

### ✅ Traefik Integration:
```yaml
Backend:   https://api.yourdomain.com
Frontend:  https://yourdomain.com
Grafana:   https://monitor.yourdomain.com
```

---

## 🎯 Dokploy Deployment Steps

### **1. Prerequisites**

**VPS Requirements:**
- Ubuntu 20.04+ atau Debian 11+
- 4GB RAM minimum (8GB recommended)
- 50GB disk space
- Docker & Docker Compose installed
- Dokploy installed

**Install Dokploy (if not installed):**
```bash
curl -sSL https://dokploy.com/install.sh | sh
```

---

### **2. Setup Git Repository**

**Option A: GitHub/GitLab (Recommended)**
```bash
# Push project to Git
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/telco-recommender.git
git push -u origin main
```

**Option B: Direct Upload to VPS**
```bash
# From local machine
scp -r . user@your-vps-ip:/var/www/telco-recommender

# On VPS
cd /var/www/telco-recommender
```

---

### **3. Dokploy Dashboard Setup**

**A. Access Dokploy:**
```
http://your-vps-ip:3000
```

**B. Create New Project:**
1. Click "New Project"
2. Name: `telco-recommender`
3. Type: "Compose"
4. Repository: Select your Git repo (or local path)

**C. Configure Compose:**
1. Compose File: `compose.prod.yaml`
2. Build Context: `/`
3. Environment: Production

---

### **4. Environment Variables (Dokploy UI)**

**CRITICAL - Set These in Dokploy:**

```bash
# Environment
ENVIRONMENT=production
NODE_ENV=production

# Database
DATABASE_USER=postgres
DATABASE_PASSWORD=<GENERATE_STRONG_PASSWORD>
DATABASE_NAME=telco_recommender

# Redis
REDIS_PASSWORD=<GENERATE_STRONG_PASSWORD>

# Security
SECRET_KEY=<GENERATE_SECRET_KEY>
JWT_SECRET_KEY=<GENERATE_JWT_SECRET>

# Airflow
AIRFLOW_FERNET_KEY=<GENERATE_FERNET_KEY>
AIRFLOW_SECRET_KEY=<GENERATE_SECRET>
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=<STRONG_PASSWORD>
AIRFLOW_ADMIN_EMAIL=admin@yourdomain.com

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<STRONG_PASSWORD>
GRAFANA_SECRET_KEY=<GENERATE_SECRET>

# Domains (Important!)
BACKEND_DOMAIN=api.yourdomain.com
FRONTEND_DOMAIN=yourdomain.com
MONITORING_DOMAIN=monitor.yourdomain.com
ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com

# Data Simulator
BATCH_SIZE=1000
INGESTION_INTERVAL_HOURS=4
START_IMMEDIATELY=true
REPLAY_MODE=false
```

**Generate Secrets:**
```bash
# SECRET_KEY & JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# FERNET_KEY (Airflow)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

### **5. DNS Configuration**

**Point your domains to VPS IP:**

```
A Record:
yourdomain.com          → your-vps-ip
api.yourdomain.com      → your-vps-ip
monitor.yourdomain.com  → your-vps-ip
```

**Wait for DNS propagation** (5-30 minutes):
```bash
nslookup yourdomain.com
```

---

### **6. Deploy via Dokploy**

**In Dokploy Dashboard:**

1. **Review Configuration**
   - Check environment variables
   - Verify domains
   - Confirm compose file

2. **Click "Deploy"**
   - Dokploy will:
     - Pull Git repo (or use local files)
     - Build Docker images
     - Start all services
     - Configure Traefik
     - Generate SSL certificates (Let's Encrypt)

3. **Monitor Deployment**
   - Watch logs in Dokploy UI
   - Check service status
   - Verify health checks

**Expected Deploy Time:** 10-15 minutes (first time)

---

### **7. Verify Deployment**

**Check Services Status:**
```bash
# SSH to VPS
ssh user@your-vps-ip

# Check running containers
docker ps

# Check logs
docker logs telco-backend-prod
docker logs telco-frontend-prod
docker logs telco-data-simulator-prod
```

**Test Endpoints:**
```bash
# Health checks
curl https://api.yourdomain.com/health
curl https://yourdomain.com

# API docs
curl https://api.yourdomain.com/docs
```

**Access Dashboards:**
```
Frontend:  https://yourdomain.com
API Docs:  https://api.yourdomain.com/docs
Grafana:   https://monitor.yourdomain.com (admin/yourpassword)
```

---

### **8. Post-Deployment Tasks**

**A. Verify Data Simulator:**
```bash
docker logs telco-data-simulator-prod -f

# Check database
docker exec telco-postgres-prod psql -U postgres telco_recommender \
  -c "SELECT COUNT(*) FROM ingestion_batches;"
```

**B. Trigger Airflow DAGs:**
```bash
# Access Airflow (internal only - port forward if needed)
ssh -L 8080:localhost:8080 user@your-vps-ip

# Then open: http://localhost:8080
# Enable DAGs and trigger manually
```

**C. Configure Grafana:**
```bash
# Access: https://monitor.yourdomain.com
# Login: admin / yourpassword
# Import dashboards from infrastructure/monitoring/grafana/dashboards/
```

**D. Run Security Audit:**
```bash
python scripts/security_audit.py --target https://api.yourdomain.com
```

---

## 🔒 Security Checklist

### **Immediate Actions:**
- [ ] Change all default passwords
- [ ] Generate unique secret keys
- [ ] Enable firewall (UFW)
- [ ] Setup fail2ban
- [ ] Configure backup schedule
- [ ] Review SSL certificate

### **Firewall Rules (UFW):**
```bash
# SSH
sudo ufw allow 22/tcp

# HTTP & HTTPS (Traefik)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Dokploy UI
sudo ufw allow 3000/tcp

# Enable firewall
sudo ufw enable
```

---

## 📊 Monitoring After Deployment

### **Grafana Dashboards:**
```
URL: https://monitor.yourdomain.com

Dashboards:
1. API Performance (request rate, latency, errors)
2. ML Models (NDCG, inference time, drift)
3. Recommender System (CTR, conversion, cache)
```

### **Application Logs:**
```bash
# Backend logs
docker logs -f telco-backend-prod

# Data simulator
docker logs -f telco-data-simulator-prod

# Airflow scheduler
docker logs -f telco-airflow-scheduler-prod
```

### **Resource Monitoring:**
```bash
# Container stats
docker stats

# Disk usage
df -h

# Memory usage
free -h
```

---

## 🔄 Update & Rollback

### **Update Application:**
```bash
# In Dokploy UI:
1. Go to Project → telco-recommender
2. Click "Redeploy"
3. Dokploy will:
   - Pull latest code
   - Rebuild images
   - Rolling update (zero downtime)
```

### **Rollback:**
```bash
# In Dokploy UI:
1. Go to Deployments
2. Select previous successful deployment
3. Click "Rollback"
```

### **Manual Update (SSH):**
```bash
cd /var/www/telco-recommender
git pull
docker compose -f compose.prod.yaml build
docker compose -f compose.prod.yaml up -d
```

---

## 🆘 Troubleshooting

### **Services Not Starting:**
```bash
# Check logs
docker logs <container-name>

# Check resources
docker stats

# Restart specific service
docker compose -f compose.prod.yaml restart <service>
```

### **SSL Certificate Issues:**
```bash
# Check Traefik logs
docker logs traefik

# Force renewal
dokploy ssl renew
```

### **Database Connection Failed:**
```bash
# Check PostgreSQL
docker exec telco-postgres-prod pg_isready

# Check environment variables
docker exec telco-backend-prod env | grep DATABASE
```

### **Out of Memory:**
```bash
# Check memory
free -h

# Reduce resource limits in compose.prod.yaml
# Or upgrade VPS plan
```

---

## 💾 Backup Strategy

### **Database Backup (Automated):**
```bash
# Create backup script
cat > /root/backup-db.sh << 'BACKUP'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker exec telco-postgres-prod pg_dump -U postgres telco_recommender > /backup/db_$DATE.sql
# Keep only last 7 days
find /backup -name "db_*.sql" -mtime +7 -delete
BACKUP

chmod +x /root/backup-db.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /root/backup-db.sh
```

### **Volume Backup:**
```bash
# Backup all volumes
docker run --rm -v telco-recommender_postgres_data:/data \
  -v /backup:/backup alpine \
  tar czf /backup/volumes_$(date +%Y%m%d).tar.gz -C /data .
```

---

## 🎓 Production Best Practices

### **Implemented:**
✅ Multi-stage Docker builds (smaller images)
✅ Resource limits (prevent runaway processes)
✅ Health checks (automatic restart on failure)
✅ Log rotation (prevent disk full)
✅ SSL/TLS encryption (Let's Encrypt)
✅ Security headers (OWASP compliance)
✅ Monitoring & alerting (Prometheus/Grafana)
✅ Automated backups (recommended above)

### **Recommended:**
- [ ] Setup monitoring alerts (email/Slack)
- [ ] Configure log aggregation (ELK/Loki)
- [ ] Implement rate limiting (already configured)
- [ ] Setup CDN for frontend (Cloudflare)
- [ ] Database read replicas (if needed)
- [ ] Redis Sentinel (high availability)

---

## 📚 Additional Resources

### **Documentation:**
- Dokploy Docs: https://docs.dokploy.com
- Traefik Docs: https://doc.traefik.io/traefik/
- Docker Compose: https://docs.docker.com/compose/

### **Project Docs:**
- `QUICK_START.md` - Local development
- `docs/DEPLOYMENT_GUIDE.md` - Detailed deployment guide
- `docs/MONITORING_RUNBOOK.md` - Monitoring procedures
- `docs/TROUBLESHOOTING_GUIDE.md` - Common issues

---

## ✅ Deployment Summary

**Status:** ✅ **READY FOR DOKPLOY**

**Requirements Met:**
- ✅ Docker Compose configured
- ✅ Dockerfiles present (4 services)
- ✅ Traefik labels configured
- ✅ Environment variables documented
- ✅ Health checks implemented
- ✅ Resource limits defined
- ✅ SSL/TLS ready
- ✅ Monitoring configured
- ✅ Production hardening complete

**Estimated Deploy Time:** 10-15 minutes
**Zero Downtime Updates:** ✅ Supported
**Auto SSL:** ✅ Let's Encrypt via Traefik
**Monitoring:** ✅ Grafana dashboards ready

---

**Last Updated:** November 8, 2024
**Status:** Production Ready
**Tested:** Docker Compose v2.x, Dokploy v0.x
