#!/bin/bash

# BratBot API Test Script
# Usage: ./test-api.sh "your message" [brat_level]
# brat_level: 1 (subtle), 2 (snarky), 3 (full brat) - default 3

API_URL="https://REDACTED-POD-ID-8000.proxy.runpod.net"
MESSAGE="${1:-can you help me?}"
BRAT_LEVEL="${2:-3}"

echo "Testing BratBot API at: $API_URL"
echo "Message: $MESSAGE | Brat Level: $BRAT_LEVEL"
echo "=================================================="

echo ""
echo "Health check:"
curl -s "$API_URL/health"
echo ""

echo ""
echo "Chat (/chat):"
curl -s -X POST "$API_URL/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$MESSAGE\", \"brat_level\": $BRAT_LEVEL}"
echo ""
echo "=================================================="
