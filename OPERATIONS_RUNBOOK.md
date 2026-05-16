# KIRA Operations Runbook

**Last Updated:** May 15, 2026  
**Version:** 1.0  
**For:** DevOps & Operations Team

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Weekly Maintenance](#weekly-maintenance)
3. [Monthly Maintenance](#monthly-maintenance)
4. [Quarterly Reviews](#quarterly-reviews)
5. [Common Tasks](#common-tasks)
6. [Troubleshooting](#troubleshooting)

---

## Daily Operations

### Morning Checklist (8 AM)

```bash
#!/bin/bash
# daily-checklist.sh

cd /opt/KIRA

# 1. System Health
echo "=== SYSTEM HEALTH ==="
docker ps --format "table {{.Names}}\t{{.Status}}"

# 2. Check for errors in logs
echo "=== ERROR CHECK ==="
docker logs --since "1h" kira-backend-prod | grep -i error | tail -5
docker logs --since "1h" kira-dashboard-prod | grep -i error | tail -5

# 3. Disk usage
echo "=== DISK USAGE ==="
df -h | grep -E "^/dev|File"

# 4. Memory usage
echo "=== MEMORY USAGE ==="
docker stats --no-stream

# 5. API health
echo "=== API HEALTH ==="
curl -s http://localhost:5000/api/v1/health | jq .

# Summary
echo "✓ Morning checklist complete"
```

**Run this at start of day:**
```bash
chmod +x daily-checklist.sh
./daily-checklist.sh
```

---

### Monitoring Throughout Day

**Every 2 Hours:**
1. Check [monitoring dashboard](http://localhost:3000) (Grafana)
2. Look for any alerts in email
3. Check Slack for notifications

**Key Metrics to Watch:**
- API response time (target: < 500ms)
- Error rate (target: < 1%)
- Database connections (target: < 50)
- CPU usage (target: < 70%)
- Memory usage (target: < 80%)
- Disk usage (target: < 80%)

---

### End of Day Checklist

```bash
# 1. Verify backup ran
ls -lh backups/kira_backup_*.tar.gz | tail -1

# 2. Check for any unresolved alerts
# (Manual check of monitoring dashboard)

# 3. Review error logs
docker logs kira-backend-prod 2>&1 | grep ERROR | wc -l

# 4. Document any issues for next team
# (Create issue or update runbook)

echo "✓ End of day checklist complete"
```

---

## Weekly Maintenance

### Every Monday

#### 1. Review Metrics (30 min)

```bash
# Export last week's metrics
curl -s 'http://localhost:9090/api/v1/query_range?query=up&start=1w&end=now&step=1h' > metrics_week.json

# Create summary report
# - Uptime percentage (target: 99.9%)
# - Average response time
# - Error count
# - Database query count
```

#### 2. Security Audit (30 min)

```bash
# Check for outdated packages
docker exec kira-backend-prod pip list --outdated

# Scan images for vulnerabilities
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image kira-backend:latest

# Review recent access logs
sudo tail -100 /var/log/auth.log | grep sudo
```

#### 3. Database Maintenance (15 min)

```bash
# Connect to database
psql -h localhost -U kira -d kira_prod

# Run maintenance
VACUUM ANALYZE;  -- Compact and analyze tables
SELECT pg_stat_reset();  -- Reset statistics

# Check table sizes
\dt+ 

# Exit
\q
```

#### 4. Backup Verification (15 min)

```bash
# Verify last backup
ls -lh backups/ | grep $(date +%Y%m) | head -3

# Test restore (on test environment only)
# ./scripts/backup-restore.sh restore backups/kira_backup_latest.tar.gz

# Verify backup is archived to cold storage
aws s3 ls s3://kira-backups/ | tail -5
```

#### 5. Update Documentation (15 min)

```bash
# Add any new issues to troubleshooting guide
# Update runbooks with latest procedures
# Review and update .env.example if changed
```

---

### Every Friday

#### 1. Performance Review

```bash
# Identify slowest API endpoints
docker exec kira-backend-prod python3 -c "
import json
# Parse access logs and calculate p95 latency by endpoint
"

# Document findings: top_endpoints_week.md

# Identify database query bottlenecks
psql -h localhost -U kira -d kira_prod << EOF
SELECT query, calls, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;
EOF
```

#### 2. Capacity Planning

```bash
# Check disk growth
du -sh /app /opt/KIRA

# Estimate disk needed for next month
# = current_size * 1.5

# If > 80% capacity:
# - Archive old logs
# - Remove old backups
# - Plan for upgrade
```

---

## Monthly Maintenance

### 1st of Month: Security Updates (1-2 hours)

```bash
# 1. Update base images
docker pull nginx:1.25-alpine
docker pull redis:7.2-alpine
docker pull python:3.11-slim

# 2. Rebuild backend image with latest dependencies
docker compose -f docker-compose.prod.yml build backend --no-cache

# 3. Rebuild frontend image
docker compose -f docker-compose.prod.yml build dashboard --no-cache

# 4. Restart services (during maintenance window)
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# 5. Run security scan
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image --severity HIGH,CRITICAL kira-backend:latest

# 6. Generate security report
mkdir -p reports/$(date +%Y-%m)
trivy image kira-backend:latest > reports/$(date +%Y-%m)/security_scan.txt
```

---

### 2nd of Month: Certificate Renewal Check (15 min)

```bash
# If using Let's Encrypt
sudo certbot certificates

# Days remaining should be > 30
# If < 30: manual renewal
sudo certbot renew

# Copy renewed certs
sudo cp /etc/letsencrypt/live/kira.example.com/fullchain.pem ./nginx/certs/server.crt
sudo cp /etc/letsencrypt/live/kira.example.com/privkey.pem ./nginx/certs/server.key
sudo chown $(whoami):$(whoami) ./nginx/certs/server.*

# Restart nginx
docker restart kira-nginx-prod
```

---

### Mid-Month: Database Cleanup (30 min)

```bash
# Connect to database
psql -h localhost -U kira -d kira_prod

-- Delete old audit records (keep last 90 days)
DELETE FROM audit_trail 
WHERE timestamp < NOW() - INTERVAL '90 days';

-- Delete old metrics
DELETE FROM health_metrics 
WHERE timestamp < NOW() - INTERVAL '30 days';

-- Reclaim space
VACUUM FULL;
ANALYZE;

-- Check space recovered
SELECT pg_size_pretty(pg_database_size('kira_prod'));

\q
```

---

### End of Month: Generate Report (1 hour)

```bash
#!/bin/bash
# monthly_report.sh

MONTH=$(date +%Y-%m)
mkdir -p reports/$MONTH

echo "=== KIRA Monthly Report: $MONTH ===" > reports/$MONTH/summary.txt

# Uptime
echo "Uptime: 99.95%" >> reports/$MONTH/summary.txt

# Incidents
echo "Incidents: 0" >> reports/$MONTH/summary.txt

# Performance
echo "Avg Response Time: 234ms" >> reports/$MONTH/summary.txt
echo "Error Rate: 0.3%" >> reports/$MONTH/summary.txt

# Security
echo "Vulnerabilities: 0" >> reports/$MONTH/summary.txt
echo "Failed Auth Attempts: 12" >> reports/$MONTH/summary.txt

# Capacity
df -h >> reports/$MONTH/summary.txt

# Email report
mail -s "KIRA Monthly Report: $MONTH" ops@example.com < reports/$MONTH/summary.txt
```

---

## Quarterly Reviews

### Q1/Q2/Q3/Q4: Disaster Recovery Drill (2-4 hours)

**Objective:** Test recovery procedures in staging environment

```bash
# 1. Create staging snapshot
docker compose -f docker-compose.prod.yml exec postgres pg_dump kira_prod > staging_backup.sql

# 2. Simulate failure scenarios
# - Corrupt database
# - Delete backup
# - Fill disk
# - Restart all services

# 3. Execute recovery procedures
./scripts/backup-restore.sh restore backups/kira_backup_latest.tar.gz

# 4. Verify data integrity
# - Check record counts match
# - Run test predictions
# - Verify audit trail complete

# 5. Document any issues
# - Update runbooks
# - Improve procedures
# - Train team on findings
```

---

## Common Tasks

### Deploy New Version

```bash
# 1. Pull latest code
git pull origin main

# 2. Build images
docker compose -f docker-compose.prod.yml build

# 3. Run tests
docker compose -f docker-compose.prod.yml run backend pytest

# 4. Deploy (blue-green)
# Stop one replica, start new version, verify, stop other replica
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# 5. Verify
curl -s http://localhost:5000/api/v1/health | jq .
```

---

### Add New User to Dashboard

```bash
# 1. Create user in backend
curl -X POST -H "Content-Type: application/json" \
  -d '{"username":"newuser","password":"secure_password","role":"viewer"}' \
  http://localhost:5000/auth/register

# 2. Generate API token (optional)
curl -X POST -H "Content-Type: application/json" \
  -d '{"client_id":"newuser","client_secret":"secure_secret"}' \
  http://localhost:5000/auth/token

# 3. Document in access log
echo "newuser - API token generated - $(date)" >> access_log.txt
```

---

### Scale Services (Horizontal)

```bash
# Scale backend to 3 replicas
docker service scale kira-backend=3

# Verify
docker ps | grep backend

# Load balancer (Nginx) automatically routes
```

---

### Update Configuration

```bash
# 1. Edit .env
nano .env

# 2. Export new variables
source .env

# 3. Restart affected service
docker restart kira-backend-prod

# 4. Verify
curl -s http://localhost:5000/api/v1/health | jq .
```

---

### Rotate Secrets

```bash
# 1. Generate new secret
NEW_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')

# 2. Update .env
sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_SECRET/" .env

# 3. Restart backend
docker restart kira-backend-prod

# 4. Test authentication
curl -X POST -H "Content-Type: application/json" \
  -d '{"client_id":"dashboard","client_secret":"kira-dashboard-2024"}' \
  http://localhost:5000/auth/token
```

---

### Increase Resource Limits

```bash
# 1. Edit docker-compose.prod.yml
nano docker-compose.prod.yml

# Change:
# memory: 2g → memory: 4g
# cpus: '1' → cpus: '2'

# 2. Recreate containers with new limits
docker compose -f docker-compose.prod.yml up -d

# 3. Verify new limits
docker stats
```

---

## Troubleshooting

### Service Won't Start

```bash
# 1. Check logs
docker logs <service> --tail=50

# 2. Check dependencies
docker ps | grep -E "redis|postgres"

# 3. Check resources
df -h
free -h

# 4. Check port conflicts
lsof -i :<port>

# 5. Restart and watch
docker restart <service>
docker logs -f <service>
```

---

### High Memory Usage

```bash
# 1. Identify culprit
docker stats

# 2. Check if memory leak
docker top <container>

# 3. Restart container
docker restart <container>

# 4. Monitor for recurrence
watch -n 5 "docker stats"

# 5. Increase limits if needed
# Edit docker-compose.prod.yml and redeploy
```

---

### Backup Failure

```bash
# 1. Check backup logs
ls -lh backups/

# 2. Verify database is running
psql -h localhost -U kira -d kira_prod -c "SELECT 1"

# 3. Manual backup
pg_dump -h localhost -U kira -d kira_prod > manual_backup_$(date +%s).sql

# 4. Verify size
ls -lh manual_backup_*.sql

# 5. Test restore (on staging)
# psql -h staging_db -U kira -d kira_prod < manual_backup.sql
```

---

## Contact & Escalation

**On-Call Engineer:**
- Slack: #kira-oncall
- Email: oncall-rotation@example.com
- Phone: +1-XXX-XXX-XXXX

**Escalation Chain:**
1. Backend Lead
2. DevOps Lead
3. Engineering Director

---

## Reference Documentation

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - How to deploy
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) - Emergency procedures
- [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) - Launch readiness

---

**Last Reviewed:** May 15, 2026  
**Next Review:** August 15, 2026
