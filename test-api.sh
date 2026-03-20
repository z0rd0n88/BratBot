#!/bin/bash

# BratBot API Test Script
# Usage: ./test-api.sh ["your message"] [brat_level]
# brat_level: 1 (subtle), 2 (snarky), 3 (full brat) - default 3

API_URL="https://28ca8h1pwx7l7j-8000.proxy.runpod.net"
MESSAGE="${1:-can you help me?}"
BRAT_LEVEL="${2:-3}"

echo "Testing BratBot API at: $API_URL"
echo "Message: $MESSAGE | Brat Level: $BRAT_LEVEL"
echo "=================================================="

echo ""
echo "1. Health Check:"
curl -s "$API_URL/health" -w "\n   Status: %{http_code}\n"

echo ""
echo "2. BratChat (/bratchat):"
curl -s -X POST "$API_URL/bratchat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$MESSAGE\", \"brat_level\": $BRAT_LEVEL}" \
  -w "\n   Status: %{http_code}\n"

echo ""
echo "3. CamiChat (/camichat):"
curl -s -X POST "$API_URL/camichat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$MESSAGE\"}" \
  -w "\n   Status: %{http_code}\n"

echo ""
echo "=================================================="
