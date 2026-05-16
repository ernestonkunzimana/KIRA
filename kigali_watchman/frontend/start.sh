#!/bin/bash
# KIRA Frontend Startup Script
# Runs the Streamlit dashboard with proper configuration

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔋 KIRA Frontend Startup${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi

# Virtual environment
if [ ! -d "venv" ]; then
    echo -e "${BLUE}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null || true

# Install requirements
echo -e "${BLUE}📥 Installing dependencies...${NC}"
pip install -q -r requirements.txt

# Check for .env
if [ ! -f ".env" ]; then
    echo -e "${BLUE}⚙️  Creating .env from template...${NC}"
    if [ -f ".env.template" ]; then
        cp .env.template .env
        echo -e "${GREEN}✅ .env created. Please review and adjust if needed.${NC}"
    fi
fi

# Check backend
API_URL="${KIRA_API_URL:-http://127.0.0.1:5001}"
echo -e "${BLUE}🔍 Checking backend at ${API_URL}...${NC}"

if ! curl -s -m 2 "${API_URL}/api/v1/health" > /dev/null 2>&1; then
    echo -e "${RED}⚠️  Backend not responding at ${API_URL}${NC}"
    echo -e "${BLUE}   Make sure backend is running:${NC}"
    echo -e "${BLUE}   cd ../backend && python main.py${NC}"
    echo ""
fi

# Start Streamlit
echo -e "${GREEN}✅ Starting KIRA Command Center...${NC}"
echo -e "${BLUE}📱 Dashboard: http://localhost:8501${NC}"
echo ""

streamlit run app.py --logger.level=info --client.showErrorDetails=false
