#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"

EMAIL="medspa-test-$(date +%s)@example.com"
PASSWORD="supersecret"

studio_html="$(curl -sS "$BASE_URL/medspa/")"
python3 -c 'import sys; html=sys.argv[1]; assert "Veriba Medspa Studio" in html; print("Medspa studio shell OK")' "$studio_html"

cases_html="$(curl -sS "$BASE_URL/medspa/cases/")"
python3 -c 'import sys; html=sys.argv[1]; assert "Medspa Cases | Veriba Studio" in html; print("Medspa cases shell OK")' "$cases_html"

credits_html="$(curl -sS "$BASE_URL/medspa/credits/")"
python3 -c 'import sys; html=sys.argv[1]; assert "Medspa Credits | Veriba Studio" in html; print("Medspa credits shell OK")' "$credits_html"

settings_html="$(curl -sS "$BASE_URL/medspa/settings/")"
python3 -c 'import sys; html=sys.argv[1]; assert "Medspa Settings | Veriba Studio" in html; print("Medspa settings shell OK")' "$settings_html"

register_body="$(
  curl -sS -X POST "$BASE_URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{
      \"email\":\"$EMAIL\",
      \"password\":\"$PASSWORD\",
      \"name\":\"Studio Owner\",
      \"practice_name\":\"Studio Pulse\",
      \"practice_location\":\"Scottsdale, AZ\",
      \"practice_website\":\"studiopulse.com\"
    }"
)"

ACCESS_TOKEN="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["access_token"])' "$register_body")"

me_body="$(curl -sS "$BASE_URL/api/users/me" -H "Authorization: Bearer $ACCESS_TOKEN")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["email"].endswith("@example.com"); print("Owner profile API OK")' "$me_body"

practice_body="$(curl -sS "$BASE_URL/api/practices/me" -H "Authorization: Bearer $ACCESS_TOKEN")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["name"] == "Studio Pulse"; print("Practice profile API OK")' "$practice_body"

practice_stats_body="$(curl -sS "$BASE_URL/api/practices/me/stats" -H "Authorization: Bearer $ACCESS_TOKEN")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert "total_published" in payload; print("Practice stats API OK")' "$practice_stats_body"

create_session_body="$(
  curl -sS -X POST "$BASE_URL/api/sessions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d '{
      "patient_initials":"SP",
      "treatment":"Morpheus8 Refresh",
      "category":"Skin",
      "status":"draft"
    }'
)"

SESSION_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["id"])' "$create_session_body")"

sessions_body="$(curl -sS "$BASE_URL/api/sessions?limit=20" -H "Authorization: Bearer $ACCESS_TOKEN")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert any(item["id"] == sys.argv[2] for item in payload["sessions"]); print("Session list API OK")' "$sessions_body" "$SESSION_ID"

credits_body="$(curl -sS "$BASE_URL/api/credits/stats" -H "Authorization: Bearer $ACCESS_TOKEN")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert "total_issued" in payload; print("Credit stats API OK")' "$credits_body"

echo
echo "Medspa admin smoke test completed successfully."
echo "Session id: $SESSION_ID"
