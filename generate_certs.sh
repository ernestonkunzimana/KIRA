#!/bin/bash

# Target directory for generated certificates
CERT_DIR="./certs"
mkdir -p "$CERT_DIR"

echo "[1/4] Generating local Certificate Authority (CA)..."
# Create CA private key
openssl genrsa -out "$CERT_DIR/ca.key" 4096
# Create self-signed CA certificate (Valid for 3 years)
openssl req -new -x509 -days 1095 -key "$CERT_DIR/ca.key" -out "$CERT_DIR/ca.crt" \
    -subj "/C=RW/L=Kigali/O=Industrial-PhD-CPS/CN=Edge-Root-CA"

echo "[2/4] Generating Server (MQTT Broker) Certificates..."
# Create Server private key
openssl genrsa -out "$CERT_DIR/server.key" 2048
# Create Server Certificate Signing Request (CSR)
openssl req -new -key "$CERT_DIR/server.key" -out "$CERT_DIR/server.csr" \
    -subj "/C=RW/L=Kigali/O=Industrial-PhD-CPS/CN=mqtt-broker"
# Sign the Server certificate using our local CA
openssl x509 -req -days 365 -in "$CERT_DIR/server.csr" -CA "$CERT_DIR/ca.crt" \
    -CAkey "$CERT_DIR/ca.key" -CAcreateserial -out "$CERT_DIR/server.crt"

echo "[3/4] Generating Client (IoT Node / AI Agent) Certificates..."
# Create Client private key
openssl genrsa -out "$CERT_DIR/client.key" 2048
# Create Client CSR (The CN becomes the authorized MQTT username)
openssl req -new -key "$CERT_DIR/client.key" -out "$CERT_DIR/client.csr" \
    -subj "/C=RW/L=Kigali/O=Industrial-PhD-CPS/CN=trusted-edge-client"
# Sign the Client certificate using our local CA
openssl x509 -req -days 365 -in "$CERT_DIR/client.csr" -CA "$CERT_DIR/ca.crt" \
    -CAkey "$CERT_DIR/ca.key" -CAcreateserial -out "$CERT_DIR/client.crt"

echo "[4/4] Hardening file permissions..."
# Restrict read/write privileges on sensitive keys
chmod 600 "$CERT_DIR"/*.key
chmod 644 "$CERT_DIR"/*.crt

# Clean up intermediary sign requests
rm "$CERT_DIR"/*.csr "$CERT_DIR"/*.srl

echo "[SUCCESS] Cryptographic assets generated inside '$CERT_DIR/' directory."
