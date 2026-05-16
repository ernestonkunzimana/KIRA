# KIRA Production Deployment Guide

**Date:** May 15, 2026  
**Version:** 1.0  
**Status:** Production Ready

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Environment Setup](#environment-setup)
3. [Database Setup](#database-setup)
4. [TLS/HTTPS Configuration](#tlshttps-configuration)
5. [Docker Deployment](#docker-deployment)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Monitoring & Logging Setup](#monitoring--logging-setup)
8. [Scaling & Auto-Recovery](#scaling--auto-recovery)

---

## Pre-Deployment Checklist

### Infrastructure Requirements
- [ ] Linux server (Ubuntu 20.04 LTS or later)
- [ ] Docker 24+ and Docker Compose v2
- [ ] PostgreSQL 13+ (local or cloud-hosted)
- [ ] Redis 7.2+ (can be containerized)
- [ ] Domain name (for TLS certificates)
- [ ] DNS records updated to point to server IP
- [ ] Firewall rules allow 80, 443, 5000, 8501 (internally)
- [ ] Disk space: minimum 20GB free
- [ ] RAM: minimum 4GB
- [ ] CPU: minimum 2 cores

### Security Requirements
- [ ] Generate `.env` file with strong secrets
- [ ] TLS certificates obtained (Let's Encrypt or commercial CA)
- [ ] Secrets Manager configured (AWS Secrets Manager, HashiCorp Vault, etc.)
- [ ] VPN/firewall restrictions configured
- [ ] SSH keys configured for deployment automation
- [ ] Audit logging enabled

### Code & Configuration
- [ ] Git repository cloned to production server
- [ ] All required environment variables documented
- [ ] Docker images built and tested locally
- [ ] Backup strategy defined
- [ ] Monitoring endpoints configured
- [ ] SSL/TLS certificates staged

---

## Environment Setup

### 1. Clone Repository

```bash
cd /opt  # or your preferred location
git clone https://github.com/your-org/KIRA.git
cd KIRA
```

### 2. Create `.env` File

```bash
cp .env.example .env
# Edit .env with your production values
nano .env
```

**Critical variables to set:**
```bash
SECRET_KEY="<generate-with-: python -c 'import secrets; print(secrets.token_urlsafe(32))'>
JWT_SECRET_KEY="<generate-with-: python -c 'import secrets; print(secrets.token_urlsafe(32))'>
DATABASE_URL="postgresql://kira:password@postgres.example.com:5432/kira_prod"
ALLOWED_ORIGINS="https://kira.example.com,https://www.kira.example.com"
```

### 3. Verify Environment

```bash
source .env
echo "Database: $DATABASE_URL"
echo "API Port: $API_PORT"
echo "Flask Env: $FLASK_ENV"
```

---

## Database Setup

### Option A: PostgreSQL on the Same Server

```bash
# Install PostgreSQL
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Run setup script
sudo chmod +x scripts/setup-postgres.sh
./scripts/setup-postgres.sh
```

### Option B: Cloud-Hosted Database (AWS RDS)

```bash
# Test connection
psql -h kira-prod.xxxxxx.rds.amazonaws.com -p 5432 -U kira -d kira_prod

# Run migrations
./scripts/setup-postgres.sh
```

### Verify Database

```bash
psql -h localhost -U kira -d kira_prod -c "SELECT count(*) FROM audit_trail;"
```

---

## TLS/HTTPS Configuration

### Option A: Self-Signed Certificates (Development Only)

```bash
sudo chmod +x scripts/generate-certs.sh
./scripts/generate-certs.sh
# Generates: nginx/certs/server.crt and server.key
```

### Option B: Let's Encrypt (Production Recommended)

```bash
# Install certbot
sudo apt-get install -y certbot certbot-nginx

# Generate certificate
sudo certbot certonly --standalone -d kira.example.com -d www.kira.example.com

# Copy to nginx directory
sudo cp /etc/letsencrypt/live/kira.example.com/fullchain.pem ./nginx/certs/server.crt
sudo cp /etc/letsencrypt/live/kira.example.com/privkey.pem ./nginx/certs/server.key
sudo chown $USER:$USER ./nginx/certs/server.*

# Set up renewal
sudo systemctl enable certbot.timer
```

### Update Nginx Config

```bash
# Edit nginx/prod.conf and ensure:
nano nginx/prod.conf
```

Key settings:
```nginx
server_name kira.example.com www.kira.example.com;
ssl_certificate /etc/nginx/certs/server.crt;
ssl_certificate_key /etc/nginx/certs/server.key;
```

---

## Docker Deployment

### 1. Run Smoke Tests

```bash
sudo chmod +x scripts/smoke-tests.sh
./scripts/smoke-tests.sh
```

Expected output:
```
✓ Docker is running
✓ Image found: kira-backend
✓ Image found: kira-dashboard
✓ Redis responded to PING
✓ Backend container started
✓ Backend health endpoint responded
✓ Frontend container started
✓ Frontend is responding to HTTP requests
✓ All smoke tests passed!
```

### 2. Build Production Images

```bash
# Build locally (or use pre-built images from registry)
docker compose -f docker-compose.prod.yml build

# Or pull from registry
docker login docker.io
docker pull your-registry/kira-backend:latest
docker pull your-registry/kira-dashboard:latest
```

### 3. Start Services

```bash
# Start in background
docker compose -f docker-compose.prod.yml up -d

# Watch logs
docker compose -f docker-compose.prod.yml logs -f

# Wait for services to be healthy (30-60 seconds)
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### 4. Verify Services are Running

```bash
# Check container status
docker ps | grep kira

# Expected output:
# kira-redis-prod     Running
# kira-backend-prod   Running (healthy)
# kira-dashboard-prod Running (healthy)
# kira-nginx-prod     Running
```

---

## Post-Deployment Verification

### 1. Health Check Endpoints

```bash
# API Health
curl -s http://localhost/api/v1/health | jq '.'

# Expected response:
# {
#   "status": "ok",
#   "redis": "ok",
#   "database": "ok",
#   "models": "degraded_fallback"
# }

# Frontend Health
curl -s http://localhost/ | head -20
```

### 2. Test Authentication

```bash
TOKEN=$(curl -sS -X POST -H "Content-Type: application/json" \
  -d '{"client_id":"dashboard","client_secret":"kira-dashboard-2024"}' \
  http://localhost/auth/token | jq -r .access_token)

echo "Token obtained: $TOKEN"
```

### 3. Test Predictions

```bash
curl -sS -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"tower_id":"Test-Tower","district":"Gasabo","sensor_data":{"CPU_Usage (%)":50}}' \
  http://localhost/api/v1/predict/iot | jq '.'
```

### 4. Check Container Logs

```bash
# Backend logs
docker compose -f docker-compose.prod.yml logs backend

# Frontend logs
docker compose -f docker-compose.prod.yml logs dashboard

# Nginx logs
docker compose -f docker-compose.prod.yml logs nginx

# Look for errors or warnings
```

---

## Monitoring & Logging Setup

### 1. Configure Log Aggregation

**Option A: ELK Stack (Local)**

```bash
# Add to docker-compose.prod.yml
# (See elasticsearch, logstash, kibana services)

# Access Kibana
open http://localhost:5601
```

**Option B: Cloud Logging (AWS CloudWatch)**

```bash
# Install CloudWatch agent
sudo wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb

# Configure
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard

# Start agent
sudo systemctl start amazon-cloudwatch-agent
```

### 2. Set Up Alerts

```bash
# Monitor CPU usage
# Monitor memory usage
# Monitor disk usage
# Monitor API error rates
# Monitor database connections
```

### 3. Create Dashboard

```bash
# Grafana / CloudWatch / Datadog
# Track: uptime, response time, error rate, active users
```

---

## Scaling & Auto-Recovery

### 1. Horizontal Scaling

```bash
# Update docker-compose to scale backend service
docker compose -f docker-compose.prod.yml up -d --scale backend=3

# Load balancer (Nginx) routes to backend instances
```

### 2. Auto-Restart Policy

Already configured in docker-compose.prod.yml:
```yaml
restart: unless-stopped
```

### 3. Regular Backups

```bash
# Create daily backup
sudo chmod +x scripts/backup-restore.sh
sudo ./scripts/backup-restore.sh

# Schedule with cron
(crontab -l 2>/dev/null; echo "0 2 * * * cd /opt/KIRA && ./scripts/backup-restore.sh") | crontab -
```

### 4. Disaster Recovery Drill

```bash
# Simulate failure
docker stop kira-backend-prod

# Verify auto-recovery
sleep 5
docker ps | grep kira-backend

# Should automatically restart within seconds
```

---

## Troubleshooting

**Services not starting:**
```bash
docker compose -f docker-compose.prod.yml logs --tail=50
# Look for resource limits, port conflicts, missing volumes
```

**Database connection refused:**
```bash
# Verify DATABASE_URL
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

**TLS certificate errors:**
```bash
# Verify cert exists
ls -la nginx/certs/server.*

# Check cert validity
openssl x509 -in nginx/certs/server.crt -text -noout
```

**High disk usage:**
```bash
docker system prune -a
docker volume prune
```

---

## Maintenance

### Weekly
- [ ] Check disk usage: `df -h`
- [ ] Review logs for errors: `docker logs`
- [ ] Test backup/restore: `./scripts/backup-restore.sh restore`

### Monthly
- [ ] Security updates: `docker pull` latest images
- [ ] Database maintenance: `VACUUM` and `ANALYZE`
- [ ] Certificate renewal check (if using Let's Encrypt)

### Quarterly
- [ ] Disaster recovery drill
- [ ] Performance review (query optimization)
- [ ] Security audit (dependency updates)

---

## Success Criteria

✅ All containers running and healthy  
✅ Health endpoints responding  
✅ API authentication working  
✅ Predictions executing  
✅ Database connected  
✅ Redis cache functional  
✅ Nginx reverse proxy routing correctly  
✅ TLS/HTTPS working  
✅ Logs aggregated and accessible  
✅ Monitoring dashboards displaying metrics  
✅ Backups being created daily  

---

**Support:** For issues, check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md).
