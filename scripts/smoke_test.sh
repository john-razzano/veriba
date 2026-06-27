#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

register_response="$(
  curl -sS -X POST "$BASE_URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
      "email":"owner@example.com",
      "password":"supersecret",
      "name":"Jane Owner",
      "practice_name":"Luxe Aesthetics",
      "practice_location":"Reno, NV",
      "practice_website":"luxeaesthetics.com"
    }'
)"

echo "Register response:"
echo "$register_response"

access_token="$(printf '%s' "$register_response" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["access_token"])')"

session_response="$(
  curl -sS -X POST "$BASE_URL/api/sessions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $access_token" \
    -d '{
      "patient_initials":"AM",
      "treatment":"Botox - Forehead",
      "category":"Botox",
      "status":"draft"
    }'
)"

echo
echo "Create session response:"
echo "$session_response"

health_response="$(curl -sS "$BASE_URL/api/health")"

echo
echo "Health response:"
echo "$health_response"

