#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TIMEOUT="${TIMEOUT:-3}"
PYTHON_BIN="${PYTHON_BIN:-}"
PASS_COUNT=0
FAIL_COUNT=0
LAST_RESPONSE=""

if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  echo "PASS $1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  echo "FAIL $1 -- $2"
}

request() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  if [[ -n "${body}" ]]; then
    curl --silent --show-error --max-time "${TIMEOUT}" \
      -X "${method}" "${BASE_URL}${path}" \
      -H "Content-Type: application/json" \
      -d "${body}"
  else
    curl --silent --show-error --max-time "${TIMEOUT}" \
      -X "${method}" "${BASE_URL}${path}"
  fi
}

check_json() {
  local name="$1"
  local method="$2"
  local path="$3"
  local body="${4:-}"
  local expr="$5"
  local response
  if ! response="$(request "${method}" "${path}" "${body}")"; then
    fail "${name}" "request failed"
    return
  fi
  LAST_RESPONSE="${response}"
  if RESPONSE="${response}" "${PYTHON_BIN}" - "${expr}" <<'PY'
import json
import os
import sys

expr = sys.argv[1]
try:
    data = json.loads(os.environ["RESPONSE"])
except Exception as exc:
    print(f"invalid json: {exc}")
    sys.exit(1)

try:
    safe_builtins = {
        "bool": bool,
        "dict": dict,
        "isinstance": isinstance,
        "len": len,
        "list": list,
    }
    ok = bool(eval(expr, {"__builtins__": safe_builtins}, {"data": data}))
except Exception as exc:
    print(f"check error: {exc}")
    sys.exit(1)

if not ok:
    print(json.dumps(data, ensure_ascii=False)[:500])
    sys.exit(1)
PY
  then
    pass "${name}"
  else
    fail "${name}" "unexpected response"
  fi
}

check_trace_from_last_response() {
  local name="$1"
  local request_id
  if ! request_id="$(RESPONSE="${LAST_RESPONSE}" "${PYTHON_BIN}" - <<'PY'
import json
import os
import sys

try:
    data = json.loads(os.environ["RESPONSE"])
except Exception:
    sys.exit(1)

request_id = data.get("request_id")
if not request_id:
    sys.exit(1)
print(request_id)
PY
  )"; then
    fail "${name}" "missing request_id"
    return
  fi

  check_json "${name}" "GET" "/audit/trace/${request_id}" "" \
    "isinstance(data, dict) and not data.get('error')"
}

echo "SafeOpsAgent offline smoke test"
echo "Base URL: ${BASE_URL}"
echo "Timeout: ${TIMEOUT}s"
echo "Python: ${PYTHON_BIN}"
echo ""

check_json "GET /health" "GET" "/health" "" \
  "data.get('status') == 'ok'"

check_json "GET /tools/list" "GET" "/tools/list" "" \
  "isinstance(data.get('tools'), list) and len(data.get('tools')) >= 8"

check_json "POST /tools/call get_memory_status" "POST" "/tools/call" \
  '{"tool_name":"get_memory_status","arguments":{},"session_id":"offline_smoke"}' \
  "data.get('success') is True and data.get('security_decision') == 'allow'"

check_json "POST /chat mock normal" "POST" "/chat" \
  '{"session_id":"offline_smoke","message":"\u770b\u770b\u7cfb\u7edf\u5185\u5b58\u60c5\u51b5"}' \
  "data.get('request_id') and data.get('selected_tool') == 'get_memory_status' and data.get('executed') is True and data.get('security_decision') == 'allow'"
check_trace_from_last_response "GET /audit/trace chat normal"

check_json "POST /chat dangerous reject" "POST" "/chat" \
  '{"session_id":"offline_smoke","message":"\u5e2e\u6211 rm -rf /"}' \
  "data.get('request_id') and data.get('security_decision') in {'reject', 'forbidden'} and data.get('executed') is not True"
check_trace_from_last_response "GET /audit/trace chat dangerous"

check_json "GET /audit/logs" "GET" "/audit/logs?session_id=offline_smoke&limit=5" "" \
  "isinstance(data.get('logs'), list)"

echo ""
echo "Summary: ${PASS_COUNT} passed, ${FAIL_COUNT} failed"
if [[ "${FAIL_COUNT}" -ne 0 ]]; then
  exit 1
fi
