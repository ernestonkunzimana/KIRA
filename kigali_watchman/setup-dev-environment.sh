#!/bin/bash
# setup-dev-environment.sh - Phase 6 Development Environment Setup
# This script configures pre-commit hooks and development tools

set -e

echo "🚀 KIRA Phase 6 Development Environment Setup"
echo "=============================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✓ Python version: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" < "3.10" ]]; then
    echo "❌ Python 3.10+ required (you have $PYTHON_VERSION)"
    exit 1
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt 2>/dev/null || echo "  (backend/requirements.txt not found, skipping)"
pip install black isort pylint flake8 bandit pytest pytest-cov pytest-timeout mypy pre-commit

# Setup pre-commit hooks
echo ""
echo "🪝 Setting up pre-commit hooks..."
pre-commit install

# Run initial checks
echo ""
echo "✅ Validation checks..."
make check-config 2>/dev/null || echo "  (Note: .env file may need configuration)"

# Final status
echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "  • Configure .env file: cp .env.example .env"
echo "  • Run tests: make test"
echo "  • Check everything: make check-all"
echo "  • View help: make help"
echo ""
echo "For more info, see: VALIDATION.md"
