#!/usr/bin/env bash
# Smoke test for cdisc-concept-curation.
# Boots the Flask app on a throwaway SQLite DB and exercises the main routes.
set -u

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PORT="${SMOKE_PORT:-9881}"
BASE="http://127.0.0.1:${PORT}"
TMP_DIR="$(mktemp -d)"
DB_PATH="${TMP_DIR}/smoke.db"
SERVER_LOG="${TMP_DIR}/server.log"
PASS=0
FAIL=0
SERVER_PID=""

cleanup() {
    if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
        kill "${SERVER_PID}" 2>/dev/null
        wait "${SERVER_PID}" 2>/dev/null
    fi
    rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

check() {
    local label="$1" expected="$2" actual="$3"
    if [[ "${actual}" == "${expected}" ]]; then
        echo "PASS  ${label} (${actual})"
        PASS=$((PASS + 1))
    else
        echo "FAIL  ${label} (expected ${expected}, got ${actual})"
        FAIL=$((FAIL + 1))
    fi
}

get_code() {
    curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$1"
}

post_code() {
    local url="$1"; shift
    curl -s -o /dev/null -w '%{http_code}' --max-time 30 -X POST "$@" "${url}"
}

cd "${REPO_DIR}"
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Starting server on port ${PORT} (throwaway DB: ${DB_PATH})"
DATABASE_URL="sqlite:///${DB_PATH}" PORT="${PORT}" CDISC_API_KEY="" \
    python app.py >"${SERVER_LOG}" 2>&1 &
SERVER_PID=$!

# Wait for readiness (BC list is DB-only, no external calls)
ready=0
for _ in $(seq 1 30); do
    if [[ "$(get_code "${BASE}/bc/")" == "200" ]]; then
        ready=1
        break
    fi
    sleep 0.5
done
if [[ "${ready}" != "1" ]]; then
    echo "FAIL  server did not become ready; log tail:"
    tail -20 "${SERVER_LOG}"
    exit 1
fi

check "GET  /bc/ (list)"                 200 "$(get_code "${BASE}/bc/")"
check "GET  /bc/new (form)"              200 "$(get_code "${BASE}/bc/new")"
check "POST /bc/ (create SMOKE001)"      302 "$(post_code "${BASE}/bc/" \
    --data-urlencode 'bc_id=SMOKE001' \
    --data-urlencode 'short_name=Smoke Test BC' \
    --data-urlencode 'definition=Created by smoke.sh' \
    --data-urlencode 'submitter=smoke')"
check "GET  /bc/SMOKE001 (detail)"       200 "$(get_code "${BASE}/bc/SMOKE001")"
check "POST /bc/SMOKE001/submit"         302 "$(post_code "${BASE}/bc/SMOKE001/submit")"
check "GET  /governance/board"           200 "$(get_code "${BASE}/governance/board")"
check "GET  /ncit/mapping"               200 "$(get_code "${BASE}/ncit/mapping")"
check "GET  /ncit/search (no term)"      200 "$(get_code "${BASE}/ncit/search")"
check "GET  /audit/"                     200 "$(get_code "${BASE}/audit/")"
check "GET  /ingestion/"                 200 "$(get_code "${BASE}/ingestion/")"
check "GET  /specializations/"           200 "$(get_code "${BASE}/specializations/")"
check "GET  /bc/export (json)"           200 "$(get_code "${BASE}/bc/export")"
check "POST /bc/SMOKE001/delete"         302 "$(post_code "${BASE}/bc/SMOKE001/delete")"
check "GET  / (dashboard, degraded API)" 200 "$(get_code "${BASE}/")"

echo
echo "Smoke result: ${PASS} passed, ${FAIL} failed"
[[ "${FAIL}" == "0" ]]
