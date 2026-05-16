# KIRA Troubleshooting Guide

**Last Updated:** May 15, 2026

---

## Common Issues & Solutions

### Container Issues

#### Problem: "docker: error response from daemon: driver failed programming external connectivity"

**Cause:** Port is already in use

**Solution:**
```bash
# Find what's using the port
lsof -i :5000  # or :8501, :6379, :80, :443

# Kill the process
kill -9 <PID>

# Or change port in .env
API_PORT=5001
REDIS_PORT=6380

# Restart
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

---

#### Problem: Containers fail with "no space left on device"

**Cause:** Disk is full

**Solution:**
```bash
# Check disk usage
df -h

# Clean Docker
docker system prune -a --volumes
docker builder prune -a

# Delete old images
docker rmi $(docker images -q)

# Check logs directory
du -sh logs/
# Remove old logs if needed
```

---

#### Problem: Container keeps restarting

**Cause:** Application crash or health check failure

**Solution:**
```bash
# Check logs
docker logs kira-backend-prod --tail=50
docker logs kira-dashboard-prod --tail=50

# Look for:
# - Import errors
# - Configuration issues
# - Resource limits exceeded
# - Database connection failures

# Check resource limits
docker stats

# If memory exceeded, increase in docker-compose.prod.yml:
# memory: 2g  # increase from 1.5g
```

---

### Database Issues

#### Problem: "could not connect to server: Connection refused"

**Cause:** PostgreSQL not running or wrong host/port

**Solution:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# If not running, start it
sudo systemctl start postgresql

# Verify connection parameters
echo $DATABASE_URL

# Test connection
psql -h <host> -p <port> -U <user> -d <database>

# If remote connection fails, check firewall
sudo ufw allow 5432
```

---

#### Problem: "FATAL: role 'kira' does not exist"

**Cause:** Database user not created

**Solution:**
```bash
# Connect as postgres superuser
sudo -u postgres psql

# Create user
CREATE USER kira WITH PASSWORD 'your-password';
CREATE DATABASE kira_prod OWNER kira;
GRANT ALL PRIVILEGES ON DATABASE kira_prod TO kira;

# Exit psql
\q

# Re-run setup
./scripts/setup-postgres.sh
```

---

#### Problem: "permission denied for schema public"

**Cause:** Insufficient privileges

**Solution:**
```bash
# Connect as superuser
sudo -u postgres psql -d kira_prod

# Grant privileges
GRANT USAGE ON SCHEMA public TO kira;
GRANT CREATE ON SCHEMA public TO kira;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kira;
```

---

### Redis Issues

#### Problem: "Connection refused" to Redis

**Cause:** Redis container not running or port mismatch

**Solution:**
```bash
# Check if Redis is running
docker ps | grep redis

# If not, check logs
docker logs kira-redis-prod

# Restart Redis
docker restart kira-redis-prod

# Verify connectivity
redis-cli ping

# If "PONG" returned, Redis is working
```

---

#### Problem: "MISCONF Redis is configured to save RDB snapshots"

**Cause:** Persistence enabled but disk full

**Solution:**
```bash
# Connect to Redis
redis-cli

# Disable persistence temporarily
CONFIG SET stop-writes-on-bgsave-error no

# Or check disk
df -h

# Free up space and restart
docker restart kira-redis-prod
```

---

### API Issues

#### Problem: API returns 500 error

**Cause:** Unhandled exception in Flask app

**Solution:**
```bash
# Check backend logs
docker logs kira-backend-prod --tail=100

# Look for:
# - ImportError (missing module)
# - ValueError (configuration issue)
# - Exception (application error)

# Restart backend
docker restart kira-backend-prod

# Check if issue persists
curl -s http://localhost:5000/api/v1/health | jq .
```

---

#### Problem: "No module named 'module_name'"

**Cause:** Package not installed in Docker image

**Solution:**
```bash
# Add to backend/requirements-prod.txt
echo "package-name==1.2.3" >> kigali_watchman/backend/requirements-prod.txt

# Rebuild image
docker compose -f docker-compose.prod.yml build backend

# Restart
docker compose -f docker-compose.prod.yml up -d backend
```

---

#### Problem: Authentication fails ("Invalid token" or "Expired token")

**Cause:** Token secret mismatch or expiration

**Solution:**
```bash
# Verify JWT_SECRET_KEY is set correctly
echo $JWT_SECRET_KEY

# Get new token
curl -X POST -H "Content-Type: application/json" \
  -d '{"client_id":"dashboard","client_secret":"kira-dashboard-2024"}' \
  http://localhost:5000/auth/token

# Use token in request
TOKEN="<token-from-above>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:5000/api/v1/health
```

---

#### Problem: Prediction endpoint returns "Model not found"

**Cause:** ML models not available (using fallback inference)

**Solution:**
```bash
# This is expected behavior - fallback engine is active
# Check health status
curl -s http://localhost:5000/api/v1/health | jq '.models'

# Response: "degraded_fallback" is normal
# Fallback provides basic rule-based predictions

# To use full ML stack:
# - Mount models volume correctly
# - Ensure TensorFlow/XGBoost are installed
# - Check model file permissions
ls -la kigali_watchman/backend/models/
```

---

### Frontend Issues

#### Problem: Streamlit shows "StreamlitAPIException"

**Cause:** Connection to backend API failed

**Solution:**
```bash
# Check KIRA_API_URL
echo $KIRA_API_URL

# Verify backend is running
curl http://backend:5000/api/v1/health

# Restart frontend
docker restart kira-dashboard-prod

# Check logs
docker logs kira-dashboard-prod
```

---

#### Problem: Dashboard loads but no data appears

**Cause:** API communication issue or empty response

**Solution:**
```bash
# Test API directly
TOKEN=$(curl -sS -X POST -H "Content-Type: application/json" \
  -d '{"client_id":"dashboard","client_secret":"kira-dashboard-2024"}' \
  http://localhost:5000/auth/token | jq -r .access_token)

# Try prediction
curl -sS -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"tower_id":"Test","district":"Gasabo","sensor_data":{"CPU_Usage (%)":50}}' \
  http://localhost:5000/api/v1/predict/iot

# If no response, check backend logs
docker logs kira-backend-prod
```

---

### TLS/HTTPS Issues

#### Problem: "SSL certificate problem: self signed certificate"

**Cause:** Using self-signed cert or cert not recognized by client

**Solution:**
```bash
# For development/testing:
curl -k -s https://localhost/api/v1/health  # -k = insecure

# For production:
# - Use valid certificate from Let's Encrypt
# - Update nginx config with correct cert path
# - Verify domain name matches certificate

# Check cert details
openssl x509 -in nginx/certs/server.crt -text -noout | grep -E "Subject:|CN="

# Should show: CN=kira.example.com
```

---

#### Problem: "certbot: error: the specified network socket is already in use"

**Cause:** Port 80 or 443 already in use

**Solution:**
```bash
# Stop nginx temporarily
docker compose -f docker-compose.prod.yml stop nginx

# Generate certificate
certbot certonly --standalone -d kira.example.com

# Restart nginx
docker compose -f docker-compose.prod.yml up -d nginx
```

---

### Nginx Issues

#### Problem: "502 Bad Gateway"

**Cause:** Nginx can't reach backend

**Solution:**
```bash
# Check if backend is running
docker ps | grep backend

# Check backend logs
docker logs kira-backend-prod

# Verify upstream config
grep -A5 "upstream backend" nginx/prod.conf

# Should be: server backend:5000;

# Restart nginx
docker restart kira-nginx-prod
```

---

#### Problem: Nginx gives "404 Not Found"

**Cause:** Route not configured in nginx.conf

**Solution:**
```bash
# Check nginx config
cat nginx/prod.conf

# Verify location blocks
grep -A10 "location /" nginx/prod.conf

# Look for proxy_pass directives
# Should have:
# - / → backend (Flask API)
# - /dashboard → dashboard (Streamlit)

# Reload nginx config
docker exec kira-nginx-prod nginx -s reload
```

---

### Performance Issues

#### Problem: API is slow (>1 second response time)

**Cause:** Database query, model inference, or resource limits

**Solution:**
```bash
# Check resource usage
docker stats

# If CPU/memory near limits, increase in docker-compose.prod.yml:
# memory: 3g
# cpus: '2'

# Check database query logs
# (Enable in PostgreSQL config)

# Profile backend
docker exec kira-backend-prod \
  python -m cProfile -s cumulative kigali_watchman/backend/main.py

# Identify slow functions and optimize
```

---

#### Problem: High memory usage (>80%)

**Cause:** Memory leak or cache bloat

**Solution:**
```bash
# Check which container
docker stats

# Check application logs
docker logs <container> | grep -i memory

# Increase allocation
# In docker-compose.prod.yml, increase memory limit

# Restart container to clear cache
docker restart <container>

# Check for memory leaks (run for 24 hours)
docker stats --no-stream
```

---

## Diagnostic Commands

### Get System Status

```bash
# All containers
docker ps -a

# Container health
docker inspect <container> | grep -A 10 Health

# Network connectivity
docker network inspect kira-network

# Disk usage
df -h

# Memory usage
free -h

# CPU usage
top
```

### Check Application Logs

```bash
# Last 50 lines, following in real-time
docker logs -f --tail=50 <container>

# Search for errors
docker logs <container> | grep ERROR

# Show timestamps
docker logs --timestamps <container>
```

### Database Diagnostics

```bash
# Connection count
psql -h localhost -U kira -d kira_prod -c \
  "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;"

# Slow queries
psql -h localhost -U kira -d kira_prod -c \
  "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Table sizes
psql -h localhost -U kira -d kira_prod -c \
  "SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename)) FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(tablename) DESC;"
```

### Redis Diagnostics

```bash
# Check info
redis-cli info stats

# Current connections
redis-cli client list

# Memory usage
redis-cli info memory

# Keys in database
redis-cli dbsize
```

---

## Escalation Procedures

### Level 1: Restart Service
1. Try restarting the failing container
2. Check logs for obvious errors
3. Verify environment variables

### Level 2: Restart All Services
1. Stop all containers: `docker compose down`
2. Clear cache: `docker system prune`
3. Restart: `docker compose up -d`

### Level 3: Restore from Backup
1. Get latest backup: `ls -lt backups/`
2. Restore: `./scripts/backup-restore.sh restore <backup-file>`
3. Verify data integrity

### Level 4: Incident Report
1. Document error details
2. Collect logs: `docker logs > /tmp/logs.txt`
3. Get system info: `docker stats > /tmp/stats.txt`
4. Report to team with logs attached

---

## Health Checks

Run these regularly:

```bash
#!/bin/bash
# health-check.sh

# API
curl -s http://localhost:5000/api/v1/health | jq .

# Database
psql -h localhost -U kira -d kira_prod -c "SELECT 1"

# Redis
redis-cli ping

# Frontend
curl -s http://localhost:8501 | head -10
```

---

**Still having issues?** See [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) or contact support.
