#!/bin/bash

# BratBot API Test Script
# Usage: ./test-api.sh ["your message"] [brat_level]
# brat_level: 1 (subtle), 2 (snarky), 3 (full brat) - default 3

API_URL="https://REDACTED-POD-ID-8000.proxy.runpod.net"
MESSAGE="${1:-can you help me?}"
BRAT_LEVEL="${2:-3}"

echo "Testing BratBot API at: $API_URL"
echo "Message: $MESSAGE | Brat Level: $BRAT_LEVEL"
echo "=================================================="

echo ""
echo "1. Health Check:"
curl -s "$API_URL/health" -w "\n   Status: %{http_code}\n"


# Build JSON payloads via Python to safely encode all special characters
# (apostrophes, quotes, backslashes, unicode, etc.)
BRATCHAT_PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({'message': sys.argv[1], 'brat_level': int(sys.argv[2])}))
" "$MESSAGE" "$BRAT_LEVEL")

CAMICHAT_PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({'message': sys.argv[1]}))
" "$MESSAGE")

echo ""
echo "2. BratChat (/bratchat):"
curl -s -X POST "$API_URL/bratchat" \
  -H "Content-Type: application/json" \
  -d "$BRATCHAT_PAYLOAD" \
  -w "\n   Status: %{http_code}\n"

echo ""
echo "3. CamiChat (/camichat):"
curl -s -X POST "$API_URL/camichat" \
  -H "Content-Type: application/json" \
  -d "$CAMICHAT_PAYLOAD" \
  -w "\n   Status: %{http_code}\n"

echo ""
echo "=================================================="
