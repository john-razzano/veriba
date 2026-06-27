#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"

./scripts/seed_internal_admin.sh > /dev/null

portal_html="$(curl -sS "$BASE_URL/veriba-admin/")"
python3 -c 'import sys; html=sys.argv[1]; assert "Veriba Internal Admin" in html; print("Internal admin shell OK")' "$portal_html"

login_body="$(
  curl -sS -X POST "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
      "email":"admin@veriba-internal.studio",
      "password":"veriba-internal-2026"
    }'
)"

ACCESS_TOKEN="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["access_token"])' "$login_body")"

overview_body="$(curl -sS "$BASE_URL/api/internal/overview" -H "Authorization: Bearer $ACCESS_TOKEN")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert "practice_count" in payload; print("Internal overview API OK")' "$overview_body"

EMAIL="internal-portal-$(date +%s)@veriba-demo.studio"
create_body="$(
  curl -sS -X POST "$BASE_URL/api/internal/practices" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d "{
      \"practice_name\":\"North Star Aesthetics\",
      \"practice_location\":\"Seattle, WA\",
      \"practice_website\":\"northstaraesthetics.com\",
      \"owner_name\":\"Taylor North\",
      \"owner_email\":\"$EMAIL\",
      \"owner_password\":\"supersecret\",
      \"auto_publish\":false
    }"
)"

PRACTICE_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["practice"]["id"])' "$create_body")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["practice"]["name"] == "North Star Aesthetics"; print("Internal practice creation OK")' "$create_body"

detail_body="$(curl -sS "$BASE_URL/api/internal/practices/$PRACTICE_ID" -H "Authorization: Bearer $ACCESS_TOKEN")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["practice"]["name"] == "North Star Aesthetics"; print("Internal practice detail OK")' "$detail_body"

echo
echo "Internal admin smoke test completed successfully."
echo "Practice id: $PRACTICE_ID"
