# Security Policy - KIRA Infrastructure Monitoring

**Version:** 1.0.0  
**Date:** 2026-05-11  
**Status:** Enforced

---

## 1. Secret Management

### 1.1 Enforcement Points

| Location | What's Blocked | What's Allowed | Enforcement |
|----------|----------------|----------------|------------|
| **Code** | Any hardcoded secrets | Comments with placeholders | detect-secrets pre-commit |
| **.env** | Placeholder values in repo | Example file (.env.example) | Git config + detect-secrets |
| **Container Images** | Secrets in layers | Environment variable references | Trivy scanning |
| **Logs** | Sensitive data output | Masked tokens in logs | Code review |
| **Git History** | Any secret committed | None | Block on push |

### 1.2 Required Practices

- All secrets from environment variables (dotenv or Kubernetes secrets)
- Secret rotation every 90 days in production
- Different secrets for dev/staging/production
- Secrets stored in:
  - Local `.env` file (git-ignored)
  - CI/CD GitHub Secrets
  - Kubernetes Secrets (for K8s deployments)

### 1.3 Secret Baseline

**Protected:**
- `SECRET_KEY` (Flask app key) – ≥32 bytes
- `JWT_SECRET_KEY` (JWT signing key) – ≥32 bytes
- `DASHBOARD_PASSWORD` (Streamlit login)
- `TWILIO_SID`, `TWILIO_TOKEN` (SMS gateway)
- `API_CLIENTS` (client credentials)

**Not Secrets (OK to commit):**
- Configuration values (thresholds, timeouts)
- Model metadata (versions, sizes)
- Infrastructure IP ranges (documented)
- Public API endpoints

---

## 2. Code Security

### 2.1 Static Analysis (Bandit)

**Enforced Rules:**
- No hardcoded credentials
- No use of `pickle` (untrusted data)
- No direct shell execution without validation
- No eval() or exec()
- Weak crypto algorithms blocked (MD5, SHA1)
- SQL injection prevention (parameterized queries required)

**Run:** `make security` or `bandit -r backend/ -ll`

### 2.2 Import Security

**Enforced:**
- No use of outdated/deprecated libraries
- All dependencies pinned in requirements.txt
- Weekly dependency vulnerability scans

**Check:** `pip-audit` or `safety check`

### 2.3 Type Safety

**Enforced:**
- Type hints on all new functions
- No `Any` types without comment explaining why
- mypy checks prevent runtime type errors

**Run:** `make types` or `mypy backend/`

---

## 3. Container Security

### 3.1 Base Image Standards

**Enforced:**
- All images use `python:3.11-slim` or `python:3.10-slim` (not `latest`)
- Images pinned to specific digest SHA256
- Base images must be <200MB
- No root user (non-root UID 1000+)

**Examples:**
```dockerfile
FROM python:3.11-slim@sha256:abc123...  # ✅ Pinned
FROM python:3.11-slim                  # ❌ Floating tag
FROM python:3.11                        # ❌ Large image
FROM ubuntu:latest                      # ❌ Non-minimal
```

### 3.2 Container Scanning

**Tool:** Trivy  
**Scans:** OS packages, Python packages, vulnerabilities  
**Threshold:** 0 critical, 0 high severity  
**Frequency:** On every push + nightly

**Results:** Uploaded to GitHub Security tab

### 3.3 Container Runtime

**Enforced:**
- Read-only filesystem by default (with writable /tmp, /var/log)
- No CAP_SYS_ADMIN, CAP_NET_RAW
- Non-root process user
- Resource limits (CPU, memory)
- Health checks for all services

---

## 4. API Security

### 4.1 Authentication

**Enforced:**
- All API endpoints (except `/health`, `/docs`) require Bearer token
- JWT tokens signed with HS256 + ≥32 byte secret
- Token expiry: 1 hour default
- Refresh token rotation required

**Check:** `@require_auth` decorator on endpoints

### 4.2 Authorization

**Enforced:**
- Role-based access control (RBAC)
- Three roles: operator, admin, viewer
- Least privilege principle
- Audit log of all access

### 4.3 Rate Limiting

**Enforced:**
- Global: 200 req/min per IP
- Predict endpoints: 60 req/min per IP
- Brute-force protection: Exponential backoff after 5 failed auths
- Cross-worker coordination via Redis

**Check:** `/api/v1/predict/*` endpoints

### 4.4 CORS Policy

**Enforced:**
- Explicitly whitelisted origins only (no wildcard *)
- Production: HTTPS URLs only
- Development: localhost:8501 allowed
- No credentials in CORS headers

**Check:** `.env` `ALLOWED_ORIGINS` variable

---

## 5. Data Security

### 5.1 Audit Logging

**Enforced:**
- All actions logged to immutable SQLite database
- Timestamp, user, action, parameters, result
- SHAP explanations for ML-based decisions
- Integrity verification (detect tampering)

**Stored:** `AUDIT_DB_PATH` (default: `/app/audit/kira_audit.db`)

### 5.2 Data Retention

**Enforced:**
- Audit logs: 90 days minimum
- ML model artifacts: version controlled
- Health check logs: 30 days
- Failed auth attempts: 7 days

### 5.3 Sensitive Data Masking

**Enforced:**
- PII must be anonymized in logs
- API keys/tokens redacted in error messages
- Password hashes (never plain text)

---

## 6. Infrastructure Security

### 6.1 Redis Configuration

**Enforced:**
- Authentication required (password)
- Encryption in transit (TLS)
- Data persistence enabled
- No FLUSHALL access
- Regular backups

**Connection:** `redis://user:pass@host:6379/db`

### 6.2 Database Security

**Enforced:**
- SQLite with file permissions 0600 (read/write owner only)
- Regular backups
- Integrity checks on startup

### 6.3 Network Security

**Enforced:**
- All services on internal docker-compose network (no host network exposure)
- Explicit port bindings only
- No debug ports exposed
- TLS for external connections

---

## 7. Compliance & Auditing

### 7.1 Security Scanning

**Automated Checks:**
- ✅ Daily Trivy container scans
- ✅ Weekly dependency audits
- ✅ Pre-commit secret detection
- ✅ Per-commit code analysis

### 7.2 Access Control

**Requirements:**
- 2FA on all GitHub accounts
- Branch protection (require reviews)
- Signed commits (GPG)
- Audit log of all deployments

### 7.3 Incident Response

**Process:**
1. Detect security issue (scan, review, or report)
2. Classify severity (critical, high, medium, low)
3. Create GitHub Security Advisory
4. Fix and test
5. Deploy hotfix with priority
6. Post-incident review

---

## 8. Security Update Schedule

| Component | Check Frequency | Update Policy | Owner |
|-----------|-----------------|---------------|-------|
| **Base Images** | Weekly | Security patches within 48h | DevOps |
| **Python Packages** | Daily | Critical within 24h | DevOps |
| **Dependencies** | Weekly | Minor/major quarterly | Tech Lead |
| **Secrets Rotation** | Quarterly | Annual minimum | Security Team |
| **Security Scans** | Daily | Results reviewed weekly | Security Team |

---

## 9. Vulnerability Disclosure

**Report privately to:** security@example.com (set up on GitHub)  
**Do not:** Create public GitHub issues for security vulnerabilities

**Process:**
1. Describe vulnerability
2. Provide proof of concept
3. Suggest fix (if possible)
4. Allow 90 days for fix before disclosure

---

## 10. Training & Awareness

**Required for all developers:**
- ✅ OWASP Top 10 training
- ✅ Secure coding practices
- ✅ KIRA security policy (this document)
- ✅ Pre-commit hook setup
- ✅ Incident response procedures

---

## 11. Exception Process

**For security policy exceptions:**
1. Document justification in GitHub issue
2. Get approval from 2+ security team members
3. Create risk acceptance form
4. Schedule review in 30 days

**No exceptions for:**
- Hardcoded secrets
- Weak cryptography
- Root containers
- Disabled authentication

---

## Enforced Tools

| Tool | Purpose | Command |
|------|---------|---------|
| **detect-secrets** | Find committed secrets | `detect-secrets scan` |
| **Bandit** | Code security | `bandit -r backend/` |
| **Trivy** | Container scanning | `trivy fs .` |
| **mypy** | Type checking | `mypy backend/` |
| **Black** | Format enforcement | `black --check .` |
| **Pytest** | Test coverage | `pytest --cov=backend` |

---

**Last Review:** 2026-05-11  
**Next Review:** 2026-08-11 (quarterly)

For questions, contact the security team or open a discussion in the GitHub repository.
