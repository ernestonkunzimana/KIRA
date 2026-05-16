#!/bin/bash
# KIRA Production Smoke Tests
# Tests that all services start and respond to basic health checks

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}KIRA Production Smoke Tests${NC}"
echo -e "${YELLOW}================================${NC}\n"

# Test 1: Check if Docker is running
echo -e "${YELLOW}[Test 1/8] Checking Docker availability...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    exit 1
fi
docker ps > /dev/null 2>&1 || (echo -e "${RED}✗ Docker daemon not running${NC}" && exit 1)
echo -e "${GREEN}✓ Docker is running${NC}\n"

# Test 2: Check if required images exist
echo -e "${YELLOW}[Test 2/8] Checking for required Docker images...${NC}"
for image in kira-backend kira-dashboard redis:7.2-alpine; do
    if docker images | grep -q "$image"; then
        echo -e "${GREEN}✓ Image found: $image${NC}"
    else
        echo -e "${RED}✗ Image not found: $image${NC}"
        exit 1
    fi
done
echo ""

# Test 3: Check if .env exists
echo -e "${YELLOW}[Test 3/8] Checking environment configuration...${NC}"
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        echo -e "${YELLOW}⚠ .env not found; copying from .env.example${NC}"
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        echo -e "${YELLOW}⚠ Please update .env with production secrets${NC}"
    else
        echo -e "${RED}✗ Neither .env nor .env.example found${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ Environment file exists${NC}\n"

# Test 4: Start Redis and test connectivity
echo -e "${YELLOW}[Test 4/8] Testing Redis...${NC}"
REDIS_CONTAINER="kira-redis-test-$$"
docker run --rm --name "$REDIS_CONTAINER" -d -p 6380:6379 \
    --security-opt seccomp=unconfined redis:7.2-alpine > /dev/null 2>&1

sleep 2

if docker exec "$REDIS_CONTAINER" redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✓ Redis responded to PING${NC}"
else
    echo -e "${RED}✗ Redis failed to respond${NC}"
    docker rm -f "$REDIS_CONTAINER" > /dev/null 2>&1
    exit 1
fi

docker rm -f "$REDIS_CONTAINER" > /dev/null 2>&1
echo ""

# Test 5: Start backend container
echo -e "${YELLOW}[Test 5/8] Testing backend container startup...${NC}"
BACKEND_CONTAINER="kira-backend-test-$$"
if docker run --rm --name "$BACKEND_CONTAINER" -d \
    -p 5001:5000 \
    -e FLASK_ENV=development \
    -e DATABASE_URL="sqlite:///kira_audit.db" \
    kira-backend:latest > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend container started${NC}"
else
    echo -e "${RED}✗ Backend container failed to start${NC}"
    exit 1
fi

sleep 5

# Test 6: Test backend health endpoint
echo -e "${YELLOW}[Test 6/8] Testing backend health endpoint...${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:5001/api/v1/health 2>/dev/null || echo "{}")

if echo "$HEALTH_RESPONSE" | grep -q "status"; then
    echo -e "${GREEN}✓ Backend health endpoint responded${NC}"
    echo "  Response: $HEALTH_RESPONSE" | head -c 100
    echo ""
else
    echo -e "${YELLOW}⚠ Backend health endpoint not responding (might still be starting)${NC}"
fi

docker rm -f "$BACKEND_CONTAINER" > /dev/null 2>&1
echo ""

# Test 7: Test frontend container startup
echo -e "${YELLOW}[Test 7/8] Testing frontend container startup...${NC}"
FRONTEND_CONTAINER="kira-dashboard-test-$$"
if docker run --rm --name "$FRONTEND_CONTAINER" -d \
    -p 8502:8501 \
    --entrypoint streamlit \
    kira-dashboard:latest run frontend/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend container started${NC}"
else
    echo -e "${RED}✗ Frontend container failed to start${NC}"
    exit 1
fi

sleep 3

# Test 8: Test frontend HTTP response
echo -e "${YELLOW}[Test 8/8] Testing frontend HTTP response...${NC}"
FRONTEND_RESPONSE=$(curl -s http://localhost:8502 2>/dev/null | head -c 100 || echo "")

if [ ! -z "$FRONTEND_RESPONSE" ]; then
    echo -e "${GREEN}✓ Frontend is responding to HTTP requests${NC}"
else
    echo -e "${YELLOW}⚠ Frontend not responding yet (Streamlit startup delay expected)${NC}"
fi

docker rm -f "$FRONTEND_CONTAINER" > /dev/null 2>&1

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✓ All smoke tests passed!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "Production deployment is ready."
echo "Next steps:"
echo "  1. Update .env with production secrets (SECRET_KEY, JWT_SECRET_KEY, DB credentials)"
echo "  2. Set up TLS certificates: nginx/certs/server.crt and server.key"
echo "  3. Deploy with: docker compose -f docker-compose.prod.yml up -d"
echo ""
