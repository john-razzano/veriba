#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

EMAIL="gallery-test-$(date +%s)@example.com"
PASSWORD="supersecret"

python3 -c "from PIL import Image; Image.new('RGB', (12, 12), color=(235, 225, 220)).save('$TMP_DIR/test.jpg', format='JPEG')"
CAPTURE_HASH="$(sha256sum "$TMP_DIR/test.jpg" | awk '{print $1}')"

register_body="$(
  curl -sS -X POST "$BASE_URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{
      \"email\":\"$EMAIL\",
      \"password\":\"$PASSWORD\",
      \"name\":\"Gallery Agent\",
      \"practice_name\":\"Radiant Atelier\",
      \"practice_location\":\"Newport Beach, CA\",
      \"practice_website\":\"radiantatelier.com\"
    }"
)"

ACCESS_TOKEN="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["access_token"])' "$register_body")"
PRACTICE_SLUG="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["practice"]["widget_slug"])' "$register_body")"

session_body="$(
  curl -sS -X POST "$BASE_URL/api/sessions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d '{
      "patient_initials":"JR",
      "treatment":"Lip Filler Refinement",
      "category":"Fillers",
      "status":"draft"
    }'
)"
SESSION_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["id"])' "$session_body")"

curl -sS -X POST "$BASE_URL/api/sessions/$SESSION_ID/images/before" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@$TMP_DIR/test.jpg;type=image/jpeg" \
  -F "capture_hash=$CAPTURE_HASH" > /dev/null

curl -sS -X POST "$BASE_URL/api/sessions/$SESSION_ID/images/after" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@$TMP_DIR/test.jpg;type=image/jpeg" > /dev/null

curl -sS -X POST "$BASE_URL/api/sessions/$SESSION_ID/consent" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "consent_tier":"full",
    "signature_svg":"M10 35 Q30 10 50 30 T90 25"
  }' > /dev/null

curl -sS -X POST "$BASE_URL/api/sessions/$SESSION_ID/publish" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "destinations":["widget","gallery"],
    "treatment_details":"Subtle volume and contour balancing"
  }' > /dev/null

home_html="$(curl -sS "$BASE_URL/")"
python3 -c 'import sys; html=sys.argv[1]; assert "Veriba Gallery" in html; print("Home page OK")' "$home_html"

gallery_html="$(curl -sS "$BASE_URL/gallery/")"
python3 -c 'import sys; html=sys.argv[1]; assert "Search the live public archive." in html; print("Gallery page shell OK")' "$gallery_html"

home_body="$(curl -sS "$BASE_URL/api/gallery/home")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["featured_sessions"]; assert payload["featured_practices"]; print("Public gallery home API OK")' "$home_body"

sessions_body="$(curl -sS "$BASE_URL/api/gallery/sessions")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["total"] >= 1; assert any(item["id"] == sys.argv[2] for item in payload["sessions"]); print("Public gallery sessions API OK")' "$sessions_body" "$SESSION_ID"

session_detail_body="$(curl -sS "$BASE_URL/api/gallery/sessions/$SESSION_ID")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["session"]["id"] == sys.argv[2]; assert payload["practice"]["widget_slug"] == sys.argv[3]; print("Public case study API OK")' "$session_detail_body" "$SESSION_ID" "$PRACTICE_SLUG"

practice_body="$(curl -sS "$BASE_URL/api/gallery/practices/$PRACTICE_SLUG")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["practice"]["widget_slug"] == sys.argv[2]; assert payload["sessions"]; print("Public provider API OK")' "$practice_body" "$PRACTICE_SLUG"

provider_html_headers="$(curl -sSI "$BASE_URL/provider/?slug=$PRACTICE_SLUG")"
python3 -c 'import sys; assert "200 OK" in sys.argv[1]; print("Provider page shell OK")' "$provider_html_headers"

case_html_headers="$(curl -sSI "$BASE_URL/case-study/?id=$SESSION_ID")"
python3 -c 'import sys; assert "200 OK" in sys.argv[1]; print("Case-study page shell OK")' "$case_html_headers"

echo
echo "Gallery smoke test completed successfully."
echo "Practice slug: $PRACTICE_SLUG"
echo "Session id: $SESSION_ID"
