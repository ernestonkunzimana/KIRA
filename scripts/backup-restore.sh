#!/bin/bash
# KIRA Backup & Disaster Recovery
# Backs up database, models, and configuration

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}KIRA Backup & Recovery${NC}"
echo -e "${YELLOW}================================${NC}\n"

if [ "$1" == "restore" ]; then
    echo -e "${YELLOW}[RESTORE MODE]${NC}"
    BACKUP_FILE="$2"
    
    if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
        echo -e "${RED}✗ Backup file not found: $BACKUP_FILE${NC}"
        echo "Usage: $0 restore /path/to/backup.tar.gz"
        exit 1
    fi
    
    echo "Extracting backup: $BACKUP_FILE"
    tar -xzf "$BACKUP_FILE" -C "$PROJECT_ROOT" 2>/dev/null || true
    echo -e "${GREEN}✓ Backup restored${NC}"
    
    # Restore database
    if [ -f "$BACKUP_DIR/database.sql" ]; then
        echo "Restoring database..."
        DB_HOST="${DB_HOST:-localhost}"
        DB_PORT="${DB_PORT:-5432}"
        DB_USER="${DB_USER:-kira}"
        DB_NAME="${DB_NAME:-kira_prod}"
        
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_DIR/database.sql"
        echo -e "${GREEN}✓ Database restored${NC}"
    fi
    
    exit 0
fi

# Backup mode
echo -e "${YELLOW}[BACKUP MODE]${NC}\n"

# Backup database
echo -e "${YELLOW}Backing up database...${NC}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-kira}"
DB_NAME="${DB_NAME:-kira_prod}"

if command -v pg_dump &> /dev/null; then
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        > "$BACKUP_DIR/database_${TIMESTAMP}.sql" 2>/dev/null && \
        echo -e "${GREEN}✓ Database backed up${NC}" || \
        echo -e "${YELLOW}⚠ Database backup skipped (connection failed)${NC}"
else
    echo -e "${YELLOW}⚠ pg_dump not available; skipping database backup${NC}"
fi

# Backup models
echo -e "${YELLOW}Backing up ML models...${NC}"
if [ -d "$PROJECT_ROOT/kigali_watchman/backend/models" ]; then
    tar -czf "$BACKUP_DIR/models_${TIMESTAMP}.tar.gz" \
        -C "$PROJECT_ROOT/kigali_watchman/backend" models/ 2>/dev/null && \
        echo -e "${GREEN}✓ Models backed up${NC}"
fi

# Backup configuration
echo -e "${YELLOW}Backing up configuration...${NC}"
mkdir -p "$BACKUP_DIR/config_${TIMESTAMP}"
cp "$PROJECT_ROOT/.env" "$BACKUP_DIR/config_${TIMESTAMP}/.env.backup" 2>/dev/null || \
    echo -e "${YELLOW}⚠ .env backup skipped${NC}"
cp "$PROJECT_ROOT/docker-compose.prod.yml" \
    "$BACKUP_DIR/config_${TIMESTAMP}/docker-compose.prod.yml" 2>/dev/null && \
    echo -e "${GREEN}✓ Configuration backed up${NC}"

# Backup certificates
echo -e "${YELLOW}Backing up certificates...${NC}"
if [ -d "$PROJECT_ROOT/nginx/certs" ]; then
    tar -czf "$BACKUP_DIR/certs_${TIMESTAMP}.tar.gz" \
        -C "$PROJECT_ROOT/nginx" certs/ 2>/dev/null && \
        echo -e "${GREEN}✓ Certificates backed up${NC}"
fi

# Create comprehensive backup archive
echo -e "${YELLOW}Creating full backup archive...${NC}"
ARCHIVE_NAME="kira_backup_${TIMESTAMP}.tar.gz"
tar -czf "$BACKUP_DIR/$ARCHIVE_NAME" \
    -C "$BACKUP_DIR" \
    database_${TIMESTAMP}.sql \
    models_${TIMESTAMP}.tar.gz \
    config_${TIMESTAMP} \
    certs_${TIMESTAMP}.tar.gz \
    2>/dev/null && \
    echo -e "${GREEN}✓ Full backup created: $ARCHIVE_NAME${NC}"

# Cleanup old backups (keep last 30 days)
echo -e "${YELLOW}Cleaning up old backups...${NC}"
find "$BACKUP_DIR" -name "kira_backup_*.tar.gz" -mtime +30 -delete 2>/dev/null && \
    echo -e "${GREEN}✓ Old backups removed${NC}"

# Show backup summary
echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Backup completed!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "Backup location: $BACKUP_DIR"
echo "Archive: $ARCHIVE_NAME"
ls -lh "$BACKUP_DIR/$ARCHIVE_NAME" 2>/dev/null || true
echo ""
echo "To restore from backup:"
echo "  $0 restore $BACKUP_DIR/$ARCHIVE_NAME"
echo ""
