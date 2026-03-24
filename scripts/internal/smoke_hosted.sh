#!/usr/bin/env bash
# smoke_hosted.sh — Local Docker smoke test for the Bid Euchre browser game.
#
# Builds the Docker image, starts a container with SQLite (no Postgres
# required), validates the health/landing endpoint and match creation
# flow, then cleans up.
#
# Usage:
#   bash scripts/internal/smoke_hosted.sh
#
# Options (via env):
#   IMAGE_NAME    Docker image tag (default: bideuchre-web-smoke)
#   CONTAINER     Container name   (default: bideuchre-smoke-test)
#   PORT          Host port        (default: 8199)
#   SKIP_BUILD    Set to 1 to reuse an existing image
#
# Exit codes:
#   0  All checks passed
#   1  A check failed or an unexpected error occurred

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
IMAGE_NAME="${IMAGE_NAME:-bideuchre-web-smoke}"
CONTAINER="${CONTAINER:-bideuchre-smoke-test}"
PORT="${PORT:-8199}"
BASE_URL="http://localhost:${PORT}"
MAX_WAIT=15          # seconds to wait for container startup

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { printf '  ✓ %s\n' "$*"; }
fail()  { printf '  ✗ %s\n' "$*" >&2; cleanup; exit 1; }
step()  { printf '\n── %s ──\n' "$*"; }

cleanup() {
    if docker ps -q --filter "name=${CONTAINER}" 2>/dev/null | grep -q .; then
        docker stop "${CONTAINER}" >/dev/null 2>&1 || true
    fi
    # --rm flag on docker run handles removal, but belt-and-suspenders:
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
}

# Always clean up, even on failure or interrupt
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Step 1: Build Docker image
# ---------------------------------------------------------------------------
step "Build Docker image"

if [ "${SKIP_BUILD:-0}" = "1" ]; then
    info "SKIP_BUILD=1 — reusing existing image ${IMAGE_NAME}"
else
    docker build -t "${IMAGE_NAME}" . \
        || fail "Docker build failed"
    info "Image built: ${IMAGE_NAME}"
fi

# ---------------------------------------------------------------------------
# Step 2: Start container (SQLite, no Postgres)
# ---------------------------------------------------------------------------
step "Start container"

# Remove any leftover container from a previous failed run
docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true

docker run --rm -d \
    --name "${CONTAINER}" \
    -p "${PORT}:8000" \
    -e DATABASE_URL="sqlite:///hosted_play.db" \
    -e SECRET_KEY="smoke-test-key" \
    -e DEBUG=1 \
    "${IMAGE_NAME}" \
    || fail "Container failed to start"

info "Container started: ${CONTAINER} (port ${PORT})"

# ---------------------------------------------------------------------------
# Step 3: Wait for health / readiness
# ---------------------------------------------------------------------------
step "Wait for app readiness"

elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    if curl -sf "${BASE_URL}/" >/dev/null 2>&1; then
        break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done

if [ $elapsed -ge $MAX_WAIT ]; then
    echo "Container logs:" >&2
    docker logs "${CONTAINER}" 2>&1 | tail -30 >&2
    fail "App did not become ready within ${MAX_WAIT}s"
fi

info "App ready after ${elapsed}s"

# ---------------------------------------------------------------------------
# Step 4: Hit landing page (health check)
# ---------------------------------------------------------------------------
step "Landing page check"

HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/")
[ "$HTTP_CODE" = "200" ] || fail "Landing page returned HTTP ${HTTP_CODE} (expected 200)"

BODY=$(curl -s "${BASE_URL}/")
echo "$BODY" | grep -qi "Bid Euchre" \
    || fail "Landing page body does not contain 'Bid Euchre'"

info "GET / → 200, body contains 'Bid Euchre'"

# ---------------------------------------------------------------------------
# Step 5: Create a match via POST /new
# ---------------------------------------------------------------------------
step "Create match"

# POST /new returns 302 redirect to /play/<uuid>
RESPONSE_HEADERS=$(curl -s -D - -o /dev/null -X POST "${BASE_URL}/new")
HTTP_CODE=$(echo "$RESPONSE_HEADERS" | grep -i "^HTTP/" | tail -1 | awk '{print $2}')

# Accept 302 (redirect) or 307 (temporary redirect)
case "$HTTP_CODE" in
    302|307)
        info "POST /new → HTTP ${HTTP_CODE}"
        ;;
    *)
        fail "POST /new returned HTTP ${HTTP_CODE} (expected 302 or 307)"
        ;;
esac

# Extract the Location header to get the play URL
LOCATION=$(echo "$RESPONSE_HEADERS" | grep -i "^location:" | sed 's/^[Ll]ocation: *//;s/\r$//')
[ -n "$LOCATION" ] || fail "POST /new did not return a Location header"
info "Location: ${LOCATION}"

# ---------------------------------------------------------------------------
# Step 6: Verify the play page loads
# ---------------------------------------------------------------------------
step "Verify play page"

# The location may be relative or absolute
if echo "$LOCATION" | grep -q "^/"; then
    PLAY_URL="${BASE_URL}${LOCATION}"
else
    PLAY_URL="${LOCATION}"
fi

HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "${PLAY_URL}")
[ "$HTTP_CODE" = "200" ] || fail "Play page returned HTTP ${HTTP_CODE} (expected 200)"

PLAY_BODY=$(curl -s "${PLAY_URL}")
echo "$PLAY_BODY" | grep -qi "nickname" \
    || fail "Play page does not contain 'nickname' prompt"

info "GET ${LOCATION} → 200, nickname prompt present"

# ---------------------------------------------------------------------------
# Step 7: Container logs — no errors
# ---------------------------------------------------------------------------
step "Check container logs"

LOG_ERRORS=$(docker logs "${CONTAINER}" 2>&1 | grep -ci "error\|traceback\|exception" || true)
if [ "$LOG_ERRORS" -gt 0 ]; then
    echo "Container logs (last 20 lines):" >&2
    docker logs "${CONTAINER}" 2>&1 | tail -20 >&2
    fail "Found ${LOG_ERRORS} error/traceback lines in container logs"
fi

info "No errors in container logs"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
step "All smoke tests passed"
echo ""
echo "Image:     ${IMAGE_NAME}"
echo "Container: ${CONTAINER} (cleaning up)"
echo ""
