#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

EMAIL="frontend-test-$(date +%s)@example.com"
PASSWORD="supersecret"

python3 -c "from PIL import Image; Image.new('RGB', (10, 10), color=(240, 240, 240)).save('$TMP_DIR/test.jpg', format='JPEG')"
CAPTURE_HASH="$(sha256sum "$TMP_DIR/test.jpg" | awk '{print $1}')"

health_body="$(curl -sS "$BASE_URL/api/health")"
python3 -c "import json,sys; payload=json.loads(sys.argv[1]); assert payload['success'] is True; print('Health OK') " "$health_body"

register_body="$(
  curl -sS -X POST "$BASE_URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{
      \"email\":\"$EMAIL\",
      \"password\":\"$PASSWORD\",
      \"name\":\"Frontend Agent\",
      \"practice_name\":\"Widget Clinic\",
      \"practice_location\":\"Reno, NV\",
      \"practice_website\":\"widgetclinic.com\"
    }"
)"

ACCESS_TOKEN="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["access_token"])' "$register_body")"
PRACTICE_SLUG="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["practice"]["widget_slug"])' "$register_body")"

session_body="$(
  curl -sS -X POST "$BASE_URL/api/sessions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d '{
      "patient_initials":"AM",
      "treatment":"Botox - Forehead",
      "category":"Botox",
      "status":"draft"
    }'
)"

SESSION_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["data"]["id"])' "$session_body")"

before_body="$(
  curl -sS -X POST "$BASE_URL/api/sessions/$SESSION_ID/images/before" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -F "file=@$TMP_DIR/test.jpg;type=image/jpeg" \
    -F "capture_hash=$CAPTURE_HASH" \
    -F "capture_lat=39.5296" \
    -F "capture_lng=-119.8138"
)"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["hash_match"] is True; print("Before upload OK")' "$before_body"

after_body="$(
  curl -sS -X POST "$BASE_URL/api/sessions/$SESSION_ID/images/after" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -F "file=@$TMP_DIR/test.jpg;type=image/jpeg"
)"
python3 -c 'import json,sys; assert json.loads(sys.argv[1])["success"] is True; print("After upload OK")' "$after_body"

consent_body="$(
  curl -sS -X POST "$BASE_URL/api/sessions/$SESSION_ID/consent" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d '{
      "consent_tier":"full",
      "signature_svg":"M10 35 Q30 10 50 30 T90 25"
    }'
)"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["session_status"] == "ready_to_publish"; print("Consent OK")' "$consent_body"

publish_body="$(
  curl -sS -X POST "$BASE_URL/api/sessions/$SESSION_ID/publish" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d '{
      "destinations":["widget","gallery"],
      "treatment_details":"20 units, horizontal forehead lines"
    }'
)"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["status"] == "published"; assert payload["seo"]["url_slug"]; print("Publish OK")' "$publish_body"

seo_body="$(curl -sS -H "Authorization: Bearer $ACCESS_TOKEN" "$BASE_URL/api/sessions/$SESSION_ID/seo")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["filename"]; print("SEO OK")' "$seo_body"

gallery_body="$(curl -sS "$BASE_URL/api/widget/$PRACTICE_SLUG/gallery")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["total"] >= 1; assert payload["sessions"][0]["id"]; print("Widget gallery OK")' "$gallery_body"

detail_body="$(curl -sS "$BASE_URL/api/widget/$PRACTICE_SLUG/session/$SESSION_ID")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]["session"]; assert payload["id"]; print("Widget detail OK")' "$detail_body"

view_body="$(curl -sS -X POST "$BASE_URL/api/widget/$PRACTICE_SLUG/session/$SESSION_ID/view")"
python3 -c 'import json,sys; payload=json.loads(sys.argv[1])["data"]; assert payload["recorded"] is True; print("Widget view tracking OK")' "$view_body"

echo
echo "Deep smoke test completed successfully."
echo "Practice slug: $PRACTICE_SLUG"
echo "Session id: $SESSION_ID"
