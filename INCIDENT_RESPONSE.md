# KIRA Incident Response Procedures

**Last Updated:** May 15, 2026  
**Version:** 1.0  
**Status:** Production Ready

---

## Incident Classification

### Severity Levels

| Level | Impact | Response Time | Examples |
|-------|--------|----------------|----------|
| **P1 - Critical** | Complete system down | Immediate (5 min) | All services down, data loss, security breach |
| **P2 - High** | Partial degradation | 15-30 minutes | API down, frontend not responding, predictions failing |
| **P3 - Medium** | Slow performance | 1-2 hours | High latency, occasional errors, database slow |
| **P4 - Low** | Minor issues | Next business day | UI bug, informational error, cosmetic issue |

---

## Incident Response Workflow

```
Detection
   ↓
Triage & Severity Assignment
   ↓
Alert Notification Team
   ↓
Initial Diagnosis (5-10 min)
   ↓
Implement Mitigation
   ↓
Root Cause Analysis
   ↓
Resolution & Verification
   ↓
Post-Incident Review
   ↓
Documentation
```

---

## P1 - Critical Incidents

### Scenario 1: All Services Down

**Symptoms:**
- API returns 503 Service Unavailable
- Frontend cannot load
- Health checks fail

**Diagnosis (5 min):**
```bash
# Check if any containers are running
docker ps

# Expected: Should see 4 running containers
# If none: All services are down
```

**Immediate Mitigation (5-10 min):**
```bash
# 1. Restart all services
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# 2. Monitor startup
watch -n 2 "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# 3. Verify health
curl -s http://localhost:5000/api/v1/health | jq .

# If still failing, proceed to restoration
```

**Restoration (if restart fails):**
```bash
# 1. Check system resources
df -h        # Disk space
free -h      # Memory
docker stats # Container stats

# 2. Clean up if disk full
docker system prune -a --volumes

# 3. Rebuild images
docker compose -f docker-compose.prod.yml build --no-cache

# 4. Restart
docker compose -f docker-compose.prod.yml up -d
```

**Escalation (if still failing after 15 min):**
- Restore from backup: `./scripts/backup-restore.sh restore <backup-file>`
- Notify team for manual intervention
- Begin war room meeting

---

### Scenario 2: Data Loss / Database Corruption

**Symptoms:**
- Database connection fails
- Audit trail tables missing
- Query returns "relation does not exist"

**Immediate Mitigation (5 min):**
```bash
# 1. STOP writing to database
docker stop kira-backend-prod

# 2. Verify backup availability
ls -lh backups/kira_backup_*.tar.gz | tail -5

# 3. Restore latest backup
./scripts/backup-restore.sh restore backups/kira_backup_latest.tar.gz

# 4. Verify data integrity
psql -h localhost -U kira -d kira_prod -c "SELECT COUNT(*) FROM audit_trail;"

# 5. Restart backend
docker start kira-backend-prod
```

**Prevention for next time:**
- Verify backups run daily: `crontab -l | grep backup`
- Test restore monthly: `./scripts/backup-restore.sh restore <test-backup>`
- Document backup location in wiki

---

### Scenario 3: Security Breach

**Symptoms:**
- Unauthorized API access
- Unexpected data modification
- Suspicious network traffic

**Immediate Containment (5 min):**
```bash
# 1. Isolate affected service
docker network disconnect kira-network kira-backend-prod

# 2. Preserve logs
docker logs kira-backend-prod > /tmp/incident_logs_$(date +%s).txt

# 3. Freeze affected data
psql -h localhost -U kira -d kira_prod << EOF
-- Lock all tables
LOCK TABLE audit_trail IN EXCLUSIVE MODE;
EOF

# 4. Notify security team
# (Manual step - contact security@example.com)

# 5. Change secrets
# Generate new SECRET_KEY and JWT_SECRET_KEY
# Update .env file
# DO NOT restart yet
```

**Investigation:**
```bash
# Check API logs for suspicious requests
grep "UNAUTHORIZED\|403\|401" /app/logs/api.log

# Check database logs
tail -100 /var/log/postgresql/postgresql.log

# Check system logs
journalctl --since "2 hours ago" | grep -E "error|fail|denied"
```

**Recovery:**
```bash
# 1. After investigation and fix
docker restart kira-backend-prod

# 2. Verify logs
docker logs kira-backend-prod | grep -i "error"

# 3. Re-run security scan
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image kira-backend:latest
```

---

## P2 - High Priority Incidents

### Scenario 1: API Down (Backend Service)

**Detection:**
```bash
curl -v http://localhost:5000/api/v1/health
# Response: Connection refused or 503
```

**Diagnosis (10 min):**
```bash
# 1. Check if container is running
docker ps | grep backend
# If not running: container crashed

# 2. Check logs for error
docker logs kira-backend-prod --tail=50
# Look for: ImportError, ValueError, Exception

# 3. Check resource usage
docker stats kira-backend-prod
# If CPU/Memory at limits: resource exhaustion
```

**Mitigation:**
```bash
# Quick restart
docker restart kira-backend-prod

# Wait for startup
sleep 10

# Verify
curl -s http://localhost:5000/api/v1/health | jq .

# If still failing:
# - Check .env variables: echo $SECRET_KEY
# - Check logs again
# - Increase resource limits if needed
```

---

### Scenario 2: Database Connection Fails

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server
```

**Quick Checks:**
```bash
# 1. Is PostgreSQL running?
sudo systemctl status postgresql

# 2. Is port open?
netstat -tuln | grep 5432

# 3. Test connection directly
psql -h localhost -U kira -d kira_prod -c "SELECT 1"

# If failed: restart PostgreSQL
sudo systemctl restart postgresql
```

**If using cloud database (RDS):**
```bash
# 1. Check security group allows port 5432
# 2. Check endpoint is correct
# 3. Verify DB instance is running (AWS console)
# 4. Test connection with updated credentials
```

---

### Scenario 3: Redis Cache Failure

**Symptoms:**
```
RedisConnectionError: Connection refused
```

**Quick Fix:**
```bash
# 1. Check if Redis container is running
docker ps | grep redis

# 2. Restart Redis
docker restart kira-redis-prod

# 3. Verify connectivity
redis-cli ping
# Expected: PONG

# 4. Check logs
docker logs kira-redis-prod
```

**Note:** Backend has fallback for Redis failure (lockout stored in-memory).

---

## P3 - Medium Priority Issues

### High Latency / Slow Responses

**Detection:**
```bash
time curl -s http://localhost:5000/api/v1/health > /dev/null
# If time > 2 seconds: slow response
```

**Diagnosis:**
```bash
# 1. Check resource usage
docker stats

# 2. Check database query logs
sudo tail -50 /var/log/postgresql/postgresql.log

# 3. Check API logs for errors
docker logs kira-backend-prod | grep -i "slow\|timeout"
```

**Mitigation:**
```bash
# 1. Increase resource limits (if near capacity)
# Edit docker-compose.prod.yml:
# memory: 3g (increase from 2g)
# cpus: '2' (increase from 1)

# Restart
docker compose -f docker-compose.prod.yml up -d

# 2. Optimize database queries
# (Contact DBA or run EXPLAIN on slow queries)

# 3. Clear cache if bloated
redis-cli FLUSHDB  # WARNING: Clears all cached data
```

---

### Container Restart Loop

**Symptom:** Container keeps restarting every few seconds

**Fix:**
```bash
# Check logs
docker logs kira-backend-prod

# Common causes:
# - Missing import: pip install missing-package
# - Wrong env var: echo $SECRET_KEY
# - Insufficient resources: increase memory
# - Port conflict: change API_PORT in .env

# After fix:
docker compose -f docker-compose.prod.yml restart backend
```

---

## P4 - Low Priority Issues

### Minor Frontend Bug

**Response:** Log issue, schedule for next sprint

```bash
# Create issue
echo "Bug: Dashboard shows 'undefined' in status indicator" >> /tmp/issues.log

# No immediate action needed
```

---

## Post-Incident Procedures

### Immediate (Within 1 hour)

```bash
# 1. Notify stakeholders
# Email: "INCIDENT RESOLVED: Services restored at 14:32 UTC"

# 2. Collect all logs
mkdir -p /tmp/incident_$(date +%s)
docker logs kira-backend-prod > /tmp/incident_*/backend.log
docker logs kira-dashboard-prod > /tmp/incident_*/frontend.log
docker logs kira-redis-prod > /tmp/incident_*/redis.log

# 3. Create incident ticket
# Jira/GitHub issue with: time, impact, resolution, logs
```

### Within 24 Hours

```bash
# 1. Root Cause Analysis (RCA) meeting
# - What happened?
# - Why did it happen?
# - How do we prevent it?

# 2. Document findings
# Create: RCA_<date>.md

# 3. Implement fixes
# - Code changes
# - Configuration updates
# - Monitoring improvements
```

### Within 1 Week

```bash
# 1. Implement preventive measures
# - Add alerting
# - Improve monitoring
# - Update runbooks

# 2. Training
# - Debrief team
# - Update documentation

# 3. Follow-up verification
# - Confirm fix is working
# - Check metrics are normal
```

---

## Communication Templates

### Incident Alert

```
🚨 INCIDENT: [SERVICE] DOWN
Severity: P[1-4]
Time: [UTC timestamp]
Impact: [Describe what's broken]
Status: INVESTIGATING
```

### Resolution Notification

```
✅ INCIDENT RESOLVED: [SERVICE]
Duration: [X minutes]
Root Cause: [Brief explanation]
Resolution: [What we did]
ETA for full post-mortem: [Date]
```

---

## On-Call Rotation

**Primary On-Call:** Monday-Friday 8 AM - 6 PM  
**Secondary On-Call:** 24/7 backup  

**Escalation:**
- P1: Page primary immediately
- P2: Email primary, page if no response in 15 min
- P3: Slack notification
- P4: No immediate notification needed

---

## Runbooks

Quick reference for common incidents:

```bash
# Service Down
docker compose -f docker-compose.prod.yml restart <service>

# Database Down
sudo systemctl restart postgresql

# Redis Down
docker restart kira-redis-prod

# Disk Full
docker system prune -a

# Memory Leak
docker restart <container>

# High CPU
docker stats  # Identify culprit
# Increase CPU limit if needed
```

---

## Monitoring & Alerts

Set up automated alerts for:

- [ ] CPU > 80%
- [ ] Memory > 90%
- [ ] Disk > 85%
- [ ] Error rate > 5%
- [ ] API latency > 2s
- [ ] Database connections > 80
- [ ] Redis memory > 512MB
- [ ] Service down for > 2 min

---

**Questions?** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or contact the on-call engineer.
