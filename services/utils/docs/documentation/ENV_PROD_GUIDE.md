# 🔐 Production Environment Configuration Guide

## ✅ File Created: `.env.prod`

Production environment file sudah dibuat dengan secure defaults. **WAJIB update sebelum deploy!**

---

## 🚨 CRITICAL - Update Sebelum Deploy

### 1. Domain Configuration

**Update 3 domain ini dengan domain kamu yang sebenarnya:**

```bash
# Di .env.prod, ganti:
FRONTEND_DOMAIN=telco-recommender.yourdomain.com
BACKEND_DOMAIN=api.telco-recommender.yourdomain.com
MONITORING_DOMAIN=monitor.telco-recommender.yourdomain.com

# Contoh jika domain kamu: telcorec.com
FRONTEND_DOMAIN=telcorec.com
BACKEND_DOMAIN=api.telcorec.com
MONITORING_DOMAIN=monitor.telcorec.com
```

### 2. CORS Origins

**Update dengan domain kamu:**

```bash
ALLOWED_ORIGINS=https://telcorec.com,https://api.telcorec.com
```

### 3. SSL Email

**Update dengan email kamu untuk Let's Encrypt:**

```bash
TRAEFIK_ACME_EMAIL=your-email@gmail.com
```

### 4. Airflow Email

```bash
AIRFLOW_ADMIN_EMAIL=your-email@gmail.com
```

### 5. Frontend API URL

**Update dengan backend domain kamu:**

```bash
VITE_API_URL=https://api.telcorec.com
```

---

## 🔑 Security Keys (OPSIONAL - Sudah Generate)

File `.env.prod` sudah termasuk secure random values untuk:

✅ `DATABASE_PASSWORD` - Strong password
✅ `REDIS_PASSWORD` - Strong password
✅ `SECRET_KEY` - 64-char hex
✅ `AIRFLOW_FERNET_KEY` - Base64 fernet key
✅ `AIRFLOW_SECRET_KEY` - 64-char hex
✅ `GRAFANA_SECRET_KEY` - 64-char hex
✅ `GRAFANA_ADMIN_PASSWORD` - Strong password
✅ `AIRFLOW_ADMIN_PASSWORD` - Strong password

**Kalau mau generate ulang (opsional):**

```bash
# SECRET_KEY & JWT_SECRET_KEY
openssl rand -hex 32

# AIRFLOW_FERNET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Password (16 chars random)
openssl rand -base64 12
```

---

## 📋 Pre-Deployment Checklist

```bash
# 1. Copy .env.prod ke VPS
scp .env.prod user@your-vps-ip:/var/www/telco-recommender/.env

# 2. Atau paste langsung di Dokploy Environment Variables UI
# (Recommended - lebih aman)
```

### Dokploy Environment Variables Setup

**Option 1: Upload .env.prod di Dokploy UI**
1. Login ke Dokploy: `http://your-vps-ip:3000`
2. Create Project → "telco-recommender"
3. Settings → Environment Variables
4. Upload `.env.prod` atau paste isinya

**Option 2: Manual paste di VPS**
```bash
# SSH ke VPS
ssh user@your-vps-ip

# Create project directory
mkdir -p /var/www/telco-recommender
cd /var/www/telco-recommender

# Clone repository atau upload files
git clone https://github.com/yourusername/telco-recommender.git .

# Copy .env.prod dari local ke .env
# (upload via SCP atau paste manual)
nano .env
# Paste isi .env.prod
```

---

## 🌐 DNS Configuration

**Sebelum deploy, setup DNS records:**

```
Type: A Record
Name: @
Value: your-vps-ip
TTL: 3600

Type: A Record
Name: api
Value: your-vps-ip
TTL: 3600

Type: A Record
Name: monitor
Value: your-vps-ip
TTL: 3600
```

**Verify DNS propagation:**
```bash
nslookup telcorec.com
nslookup api.telcorec.com
nslookup monitor.telcorec.com
```

---

## 🚀 Deploy ke Dokploy

**Setelah update .env.prod:**

1. **Upload project ke Git** (optional tapi recommended):
   ```bash
   git add .
   git commit -m "Production ready"
   git push origin main
   ```

2. **Di Dokploy Dashboard:**
   - New Project → Type: "Compose"
   - Repository: Your Git repo
   - Compose file: `compose.prod.yaml`
   - Environment: Upload `.env.prod`
   - Click "Deploy"

3. **Wait 10-15 minutes** untuk:
   - Docker images build
   - Services start
   - SSL certificates generate (Let's Encrypt)
   - Health checks pass

4. **Verify deployment:**
   ```bash
   # Check services
   curl https://api.telcorec.com/health
   curl https://telcorec.com

   # Check Grafana
   open https://monitor.telcorec.com
   # Login: admin / GrafanaProd2024!Monitor#7d6c5b4a
   ```

---

## 🔒 Security Notes

**IMPORTANT:**

❌ **JANGAN commit `.env.prod` ke Git!**
✅ Simpan di password manager atau secure vault
✅ Backup di tempat aman (encrypted)
✅ Share hanya via secure channel (bukan email!)

**File sudah di .gitignore:**
```bash
# Check
cat .gitignore | grep .env
# Should show: .env, .env.prod, .env.local
```

---

## 📊 Default Admin Credentials

**Grafana:**
- URL: `https://monitor.telcorec.com`
- User: `admin`
- Pass: `GrafanaProd2024!Monitor#7d6c5b4a`

**Airflow:**
- URL: SSH tunnel atau internal only
- User: `admin`
- Pass: `AirflowProd2024!Admin#6c5b4a3f`

**PostgreSQL:**
- Host: `postgres` (internal only)
- User: `postgres`
- Pass: `TelcoProd2024!SecureDB#9f8e7d6c5b4a`

**Redis:**
- Host: `redis` (internal only)
- Pass: `RedisProd2024!Cache#8e7d6c5b4a3f`

⚠️ **Change passwords setelah first login!**

---

## 📝 Quick Reference

**Production URLs (setelah deploy):**
```
Frontend:  https://telcorec.com
API Docs:  https://api.telcorec.com/docs
Grafana:   https://monitor.telcorec.com
```

**Services yang running:**
1. PostgreSQL (database)
2. Redis (cache)
3. Data Simulator (ingestion)
4. Backend (FastAPI)
5. Frontend (React)
6. MLflow (experiment tracking)
7. Prometheus (metrics)
8. Grafana (dashboards)
9. Airflow Init (setup)
10. Airflow Webserver (UI)
11. Airflow Scheduler (orchestration)

---

**Status:** ✅ Production configuration ready!
**Next Step:** Update domains → Deploy to Dokploy → Verify endpoints
