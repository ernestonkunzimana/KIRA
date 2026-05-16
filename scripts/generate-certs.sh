#!/bin/bash
# KIRA TLS Certificate Generation
# Generates self-signed certificates for development or provides Let's Encrypt setup

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CERT_DIR="$PROJECT_ROOT/nginx/certs"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}KIRA TLS Certificate Setup${NC}"
echo -e "${YELLOW}================================${NC}\n"

# Create certificates directory
mkdir -p "$CERT_DIR"

# Determine which mode to use
if [ "$1" == "production" ]; then
    echo -e "${YELLOW}[PRODUCTION MODE]${NC}"
    echo "For production, use Let's Encrypt:"
    echo ""
    echo "1. Install certbot:"
    echo "   sudo apt-get install certbot certbot-nginx"
    echo ""
    echo "2. Generate certificate (replace example.com with your domain):"
    echo "   sudo certbot certonly --standalone -d kira.example.com -d www.kira.example.com"
    echo ""
    echo "3. Copy certificates to nginx/certs:"
    echo "   sudo cp /etc/letsencrypt/live/kira.example.com/fullchain.pem $CERT_DIR/server.crt"
    echo "   sudo cp /etc/letsencrypt/live/kira.example.com/privkey.pem $CERT_DIR/server.key"
    echo "   sudo chown \$USER:\$USER $CERT_DIR/server.*"
    echo ""
    echo "4. Set renewal reminder:"
    echo "   sudo systemctl enable certbot.timer"
    echo ""
    exit 0
fi

# Development mode: Generate self-signed certificate
echo -e "${YELLOW}[DEVELOPMENT MODE]${NC}"
echo "Generating self-signed certificate for development..."
echo ""

CERT_FILE="$CERT_DIR/server.crt"
KEY_FILE="$CERT_DIR/server.key"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo -e "${GREEN}✓ Certificates already exist:${NC}"
    echo "  - $CERT_FILE"
    echo "  - $KEY_FILE"
    echo ""
    exit 0
fi

# Generate self-signed certificate (valid for 365 days)
openssl req -x509 -newkey rsa:4096 -keyout "$KEY_FILE" -out "$CERT_FILE" \
    -days 365 -nodes \
    -subj "/C=RW/ST=Kigali/L=Kigali/O=KIRA/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:127.0.0.1,DNS:kira.local,DNS:kira.example.com"

chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

echo -e "${GREEN}✓ Self-signed certificates generated:${NC}"
echo "  - Certificate: $CERT_FILE"
echo "  - Private Key: $KEY_FILE"
echo ""
echo "Certificate Details:"
openssl x509 -in "$CERT_FILE" -text -noout | grep -E "Subject:|Issuer:|Not Before|Not After|DNS:" || true
echo ""
echo -e "${YELLOW}Note:${NC} This certificate is self-signed and will trigger browser warnings."
echo "For production, use Let's Encrypt: ./scripts/generate-certs.sh production"
echo ""
