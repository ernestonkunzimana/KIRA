#!/bin/bash
# KIRA PostgreSQL Setup
# Initializes PostgreSQL database and runs migrations

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}KIRA PostgreSQL Setup${NC}"
echo -e "${YELLOW}================================${NC}\n"

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo -e "${RED}✗ PostgreSQL client (psql) not found${NC}"
    echo "Install with: sudo apt-get install postgresql-client"
    exit 1
fi

# Get environment variables
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-kira_prod}"
DB_USER="${DB_USER:-kira}"
DB_PASSWORD="${DB_PASSWORD:-}"

echo -e "${YELLOW}Database Configuration:${NC}"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

# Test connection
echo -e "${YELLOW}Testing PostgreSQL connection...${NC}"
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Connected to PostgreSQL${NC}\n"
else
    echo -e "${RED}✗ Failed to connect to PostgreSQL${NC}"
    echo "Please check your database credentials in .env"
    exit 1
fi

# Create database if not exists
echo -e "${YELLOW}Creating database...${NC}"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
    "CREATE DATABASE $DB_NAME;" 2>/dev/null || \
    echo -e "${YELLOW}⚠ Database already exists (or permission denied)${NC}"

echo -e "${GREEN}✓ Database ready${NC}\n"

# Create tables (example audit table)
echo -e "${YELLOW}Creating tables...${NC}"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << 'EOF'
-- Audit trail table
CREATE TABLE IF NOT EXISTS audit_trail (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tower_id VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    predicted_class VARCHAR(50),
    confidence FLOAT,
    manual_override BOOLEAN DEFAULT FALSE,
    override_reason TEXT,
    user_id VARCHAR(100),
    system_status VARCHAR(50),
    metadata JSONB
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_audit_tower_id ON audit_trail(tower_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_trail(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_trail(action);

-- Health metrics table
CREATE TABLE IF NOT EXISTS health_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    service_name VARCHAR(100),
    status VARCHAR(20),
    response_time_ms FLOAT,
    error_count INTEGER,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_health_timestamp ON health_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_health_service ON health_metrics(service_name);

-- Model versions table
CREATE TABLE IF NOT EXISTS model_versions (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    accuracy FLOAT,
    f1_score FLOAT,
    deployment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT FALSE,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_model_name ON model_versions(model_name);
CREATE INDEX IF NOT EXISTS idx_model_active ON model_versions(is_active);

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO "kira";
EOF

echo -e "${GREEN}✓ Tables created${NC}\n"

# Test table access
echo -e "${YELLOW}Testing table access...${NC}"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
    "SELECT COUNT(*) FROM audit_trail;" > /dev/null

echo -e "${GREEN}✓ Table access verified${NC}\n"

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}PostgreSQL setup complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "Next steps:"
echo "1. Update DATABASE_URL in .env:"
echo "   DATABASE_URL=\"postgresql://$DB_USER:password@$DB_HOST:$DB_PORT/$DB_NAME\""
echo "2. Start services: docker compose -f docker-compose.prod.yml up -d"
echo ""
