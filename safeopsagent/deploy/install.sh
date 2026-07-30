#!/bin/bash
# SafeOpsAgent deployment script
# Run as root on Kylin V11 / LoongArch or generic Linux

set -e

echo "=== SafeOpsAgent Deployment ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALL_ROOT="/opt/safeopsagent"
ENV_DIR="/etc/safeops-agent"
ENV_FILE="${ENV_DIR}/env.conf"
SYSTEMD_DIR="/etc/systemd/system"
AGENT_UNIT_FILE="${SYSTEMD_DIR}/safeops-agent.service"
WEB_UNIT_FILE="${SYSTEMD_DIR}/safeops-web.service"
HEALTH_URL="http://127.0.0.1:8000/health"
HEALTH_TIMEOUT_SECONDS=30
MANAGED_ITEMS=(venv backend frontend deploy config scripts docs README.md .env.example)

if [ "${PROJECT_ROOT}" = "${INSTALL_ROOT}" ]; then
    echo "[ERROR] Run this installer from an extracted delivery tree, not from ${INSTALL_ROOT}." >&2
    exit 1
fi

read_env_value() {
    local key="$1"
    sed -n "s/^${key}=//p" "${ENV_FILE}" | tail -n 1
}

validate_auth_values() {
    local username="$1"
    local password_hash="$2"
    local session_secret="$3"

    if [[ ! "${username}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]; then
        echo "[ERROR] Console username must use 1-64 letters, digits, dot, underscore, or hyphen." >&2
        return 1
    fi

    if ! python3 - "${password_hash}" <<'PY'
import base64
import binascii
import re
import sys


def decode_base64url(value: str) -> bytes:
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError
    padded = value + "=" * (-len(value) % 4)
    return base64.b64decode(padded, altchars=b"-_", validate=True)


try:
    scheme, iterations_text, salt_text, digest_text = sys.argv[1].split("$")
    if not re.fullmatch(r"[0-9]+", iterations_text):
        raise ValueError
    iterations = int(iterations_text)
    salt = decode_base64url(salt_text)
    digest = decode_base64url(digest_text)
    valid = (
        scheme == "pbkdf2_sha256"
        and 200_000 <= iterations <= 2_000_000
        and 8 <= len(salt) <= 64
        and len(digest) == 32
    )
except (ValueError, binascii.Error):
    valid = False

raise SystemExit(0 if valid else 1)
PY
    then
        echo "[ERROR] Console password verifier must use PBKDF2-SHA256 with 200000-2000000 iterations, an 8-64 byte salt, and a 32 byte digest." >&2
        return 1
    fi

    if ! python3 - "${session_secret}" <<'PY'
import re
import sys


secret = sys.argv[1]
valid = bool(re.fullmatch(r"[A-Za-z0-9_-]{32,256}", secret))
if valid and len(set(secret)) < 8:
    valid = False
if valid:
    for width in range(1, len(secret) // 2 + 1):
        if len(secret) % width == 0 and secret == secret[:width] * (len(secret) // width):
            valid = False
            break

raise SystemExit(0 if valid else 1)
PY
    then
        echo "[ERROR] Console session secret must contain 32-256 URL-safe characters and must not use an obvious repeated or low-diversity pattern." >&2
        return 1
    fi
}

validate_auth_file() {
    if [ "$(read_env_value CONSOLE_AUTH_ENABLED)" != "1" ]; then
        echo "[ERROR] ${ENV_FILE} must contain CONSOLE_AUTH_ENABLED=1." >&2
        return 1
    fi
    validate_auth_values \
        "$(read_env_value CONSOLE_AUTH_USERNAME)" \
        "$(read_env_value CONSOLE_AUTH_PASSWORD_HASH)" \
        "$(read_env_value CONSOLE_AUTH_SESSION_SECRET)"
}

# 1. Create opsagent user
if ! id opsagent &>/dev/null; then
    useradd -r -s /bin/false -M opsagent
    echo "[OK] Created opsagent user"
else
    echo "[SKIP] opsagent user exists"
fi

# 2. Create directories
if [ -L "${INSTALL_ROOT}" ] || [ -L "${INSTALL_ROOT}/data" ] \
    || [ -L /var/log/safeopsagent ] || [ -L "${ENV_DIR}" ] \
    || [ -L "${ENV_FILE}" ]; then
    echo "[ERROR] Refusing to install through a symbolic-link managed directory." >&2
    exit 1
fi
mkdir -p "${INSTALL_ROOT}" "${INSTALL_ROOT}/data" /var/log/safeopsagent "${ENV_DIR}"
chown root:root "${INSTALL_ROOT}"
chown -R opsagent:opsagent /var/log/safeopsagent "${INSTALL_ROOT}/data"
chmod 755 "${INSTALL_ROOT}"
chmod 750 /var/log/safeopsagent "${INSTALL_ROOT}/data"
chmod 750 "${ENV_DIR}"

# 2.1 Create default environment file if absent
if [ ! -f "${ENV_FILE}" ]; then
    console_username="${CONSOLE_AUTH_USERNAME:-operator}"
    console_password_hash="${CONSOLE_AUTH_PASSWORD_HASH:-}"
    if [ -z "${console_password_hash}" ]; then
        if [ ! -t 0 ]; then
            echo "[ERROR] Non-interactive install requires CONSOLE_AUTH_PASSWORD_HASH." >&2
            echo "        Generate it with: python scripts/hash_console_password.py" >&2
            exit 1
        fi
        console_password_hash="$(python3 "${PROJECT_ROOT}/scripts/hash_console_password.py" --value-only)"
    fi
    console_session_secret="${CONSOLE_AUTH_SESSION_SECRET:-}"
    if [ -z "${console_session_secret}" ]; then
        console_session_secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
    fi
    validate_auth_values "${console_username}" "${console_password_hash}" "${console_session_secret}"

    umask 027
    cat > "${ENV_FILE}" <<EOF
MODEL_PROVIDER=offline_safe
MODEL_API_BASE=
MODEL_API_KEY=
MODEL_NAME=
BACKEND_URL=http://127.0.0.1:8000
CONSOLE_AUTH_ENABLED=1
CONSOLE_AUTH_USERNAME=${console_username}
CONSOLE_AUTH_PASSWORD_HASH=${console_password_hash}
CONSOLE_AUTH_SESSION_SECRET=${console_session_secret}
CONSOLE_AUTH_SECURE_COOKIE=0
CONSOLE_AUTH_ALLOW_INSECURE_NON_LOOPBACK=0
EOF
    chown root:opsagent "${ENV_FILE}"
    chmod 640 "${ENV_FILE}"
    echo "[OK] Created ${ENV_FILE} with console authentication for ${console_username}"
else
    validate_auth_file
    echo "[SKIP] ${ENV_FILE} exists"
fi

# 3. Prepare the new environment and release before stopping a running service.
# A dependency or copy failure therefore leaves the current deployment intact.
STAGE_ROOT="$(mktemp -d "${INSTALL_ROOT}/.install-stage.XXXXXX")"
BACKUP_ROOT=""
PRESERVE_BACKUP=0
ACTIVATION_STARTED=0
ACTIVATION_COMMITTED=0
ROLLBACK_ATTEMPTED=0
BACKED_UP_ITEMS=()
ACTIVATED_ITEMS=()

cleanup_stage() {
    case "${STAGE_ROOT:-}" in
        "${INSTALL_ROOT}"/.install-stage.*)
            if [ -d "${STAGE_ROOT}" ] && [ ! -L "${STAGE_ROOT}" ]; then
                rm -rf -- "${STAGE_ROOT}"
            fi
            ;;
    esac
}

cleanup_backup() {
    case "${BACKUP_ROOT:-}" in
        "${INSTALL_ROOT}"/.install-backup.*)
            if [ -d "${BACKUP_ROOT}" ] && [ ! -L "${BACKUP_ROOT}" ]; then
                rm -rf -- "${BACKUP_ROOT}"
            fi
            ;;
    esac
}

restore_previous_release() {
    local rollback_failed=0
    local item

    ROLLBACK_ATTEMPTED=1
    set +e
    echo "[ROLLBACK] Restoring the previous SafeOpsAgent release" >&2

    systemctl stop safeops-web >/dev/null 2>&1 || true
    systemctl stop safeops-agent >/dev/null 2>&1 || true

    # Remove an enablement link created by this attempted install while the
    # new unit still exists. The original enablement is restored below.
    if [ "${agent_enable_touched:-0}" -eq 1 ] && [ "${agent_was_enabled:-0}" -eq 0 ]; then
        systemctl disable safeops-agent >/dev/null 2>&1 || rollback_failed=1
    fi

    for item in "${ACTIVATED_ITEMS[@]}"; do
        rm -rf -- "${INSTALL_ROOT}/${item}" || rollback_failed=1
    done
    for item in "${BACKED_UP_ITEMS[@]}"; do
        if [ -e "${BACKUP_ROOT}/${item}" ] || [ -L "${BACKUP_ROOT}/${item}" ]; then
            mv -- "${BACKUP_ROOT}/${item}" "${INSTALL_ROOT}/${item}" || rollback_failed=1
        else
            echo "[ROLLBACK] Missing backup item: ${item}" >&2
            rollback_failed=1
        fi
    done

    if [ "${units_touched:-0}" -eq 1 ]; then
        rm -f -- "${AGENT_UNIT_FILE}" "${WEB_UNIT_FILE}" || rollback_failed=1
        if [ "${agent_unit_was_present:-0}" -eq 1 ]; then
            cp -a -- "${BACKUP_ROOT}/systemd/safeops-agent.service" \
                "${AGENT_UNIT_FILE}" || rollback_failed=1
        fi
        if [ "${web_unit_was_present:-0}" -eq 1 ]; then
            cp -a -- "${BACKUP_ROOT}/systemd/safeops-web.service" \
                "${WEB_UNIT_FILE}" || rollback_failed=1
        fi
    fi

    systemctl daemon-reload || rollback_failed=1

    if [ "${agent_was_enabled:-0}" -eq 1 ]; then
        systemctl enable safeops-agent >/dev/null 2>&1 || rollback_failed=1
    else
        systemctl disable safeops-agent >/dev/null 2>&1 || true
    fi
    if [ "${web_was_enabled:-0}" -eq 1 ]; then
        systemctl enable safeops-web >/dev/null 2>&1 || rollback_failed=1
    else
        systemctl disable safeops-web >/dev/null 2>&1 || true
    fi

    if [ "${agent_was_active:-0}" -eq 1 ]; then
        systemctl start safeops-agent || rollback_failed=1
    fi
    if [ "${web_was_active:-0}" -eq 1 ]; then
        systemctl start safeops-web || rollback_failed=1
    fi

    if [ "${rollback_failed}" -eq 0 ]; then
        echo "[ROLLBACK] Previous release and service state restored" >&2
        PRESERVE_BACKUP=0
        if cleanup_backup; then
            BACKUP_ROOT=""
            return 0
        fi
        echo "[ROLLBACK] Restored the release, but could not remove ${BACKUP_ROOT}." >&2
        rollback_failed=1
    fi

    echo "[ROLLBACK] Automatic restoration was incomplete." >&2
    echo "[ROLLBACK] Backup retained at ${BACKUP_ROOT} for manual recovery." >&2
    PRESERVE_BACKUP=1
    return 1
}

on_exit() {
    local exit_status=$?

    trap - EXIT
    set +e
    if [ "${ACTIVATION_STARTED}" -eq 1 ] \
        && [ "${ACTIVATION_COMMITTED}" -eq 0 ] \
        && [ "${ROLLBACK_ATTEMPTED}" -eq 0 ]; then
        restore_previous_release || exit_status=1
    fi
    cleanup_stage
    if [ "${PRESERVE_BACKUP}" -eq 0 ]; then
        cleanup_backup
    fi
    exit "${exit_status}"
}

trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

python3 -m venv "${STAGE_ROOT}/venv"
chown -R root:root "${STAGE_ROOT}/venv"

# 4. Install the minimal Kylin backend dependencies into the staged venv.
# The primary UI is the Vue console served by FastAPI at /console/.
# Streamlit and developer test dependencies remain opt-in.
"${STAGE_ROOT}/venv/bin/python" -m pip install \
    -r "${PROJECT_ROOT}/backend/requirements-kylin.txt"

# 5. Stage project files. Runtime data remains outside this replacement set.
for directory in backend frontend deploy config scripts docs; do
    cp -r "${PROJECT_ROOT}/${directory}" "${STAGE_ROOT}/${directory}"
done
cp "${PROJECT_ROOT}/README.md" "${STAGE_ROOT}/README.md"
cp "${PROJECT_ROOT}/.env.example" "${STAGE_ROOT}/.env.example"
chown -R root:root "${STAGE_ROOT}"
chmod -R go-w "${STAGE_ROOT}"

for item in "${MANAGED_ITEMS[@]}"; do
    if [ ! -e "${STAGE_ROOT}/${item}" ] && [ ! -L "${STAGE_ROOT}/${item}" ]; then
        echo "[ERROR] Staged release is missing ${item}." >&2
        exit 1
    fi
done

for unit_file in "${AGENT_UNIT_FILE}" "${WEB_UNIT_FILE}"; do
    if [ -e "${unit_file}" ] && [ ! -f "${unit_file}" ] && [ ! -L "${unit_file}" ]; then
        echo "[ERROR] Refusing to replace non-file systemd path: ${unit_file}" >&2
        exit 1
    fi
done

BACKUP_ROOT="$(mktemp -d "${INSTALL_ROOT}/.install-backup.XXXXXX")"
mkdir "${BACKUP_ROOT}/systemd"
agent_unit_was_present=0
web_unit_was_present=0
if [ -e "${AGENT_UNIT_FILE}" ] || [ -L "${AGENT_UNIT_FILE}" ]; then
    cp -a -- "${AGENT_UNIT_FILE}" "${BACKUP_ROOT}/systemd/safeops-agent.service"
    agent_unit_was_present=1
fi
if [ -e "${WEB_UNIT_FILE}" ] || [ -L "${WEB_UNIT_FILE}" ]; then
    cp -a -- "${WEB_UNIT_FILE}" "${BACKUP_ROOT}/systemd/safeops-web.service"
    web_unit_was_present=1
fi

agent_was_active=0
web_was_active=0
agent_was_enabled=0
web_was_enabled=0
systemctl is-active --quiet safeops-agent && agent_was_active=1
systemctl is-active --quiet safeops-web && web_was_active=1
systemctl is-enabled --quiet safeops-agent && agent_was_enabled=1
systemctl is-enabled --quiet safeops-web && web_was_enabled=1

wait_for_backend_health() {
    python3 - "${HEALTH_URL}" "${HEALTH_TIMEOUT_SECONDS}" <<'PY'
import sys
import time
import urllib.error
import urllib.request


url = sys.argv[1]
timeout_seconds = float(sys.argv[2])
deadline = time.monotonic() + timeout_seconds
last_error = "health check did not run"

while True:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        break
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=min(2.0, remaining)) as response:
            if response.status == 200:
                raise SystemExit(0)
            last_error = f"HTTP {response.status}"
    except (OSError, urllib.error.URLError) as exc:
        last_error = str(exc)
    time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))

print(f"backend health check failed: {last_error}", file=sys.stderr)
raise SystemExit(1)
PY
}

activate_release() {
    local item

    ACTIVATION_STARTED=1
    PRESERVE_BACKUP=1

    if [ "${web_was_active}" -eq 1 ]; then
        systemctl stop safeops-web || return 1
    fi
    if [ "${agent_was_active}" -eq 1 ]; then
        systemctl stop safeops-agent || return 1
    fi

    for item in "${MANAGED_ITEMS[@]}"; do
        if [ -e "${INSTALL_ROOT}/${item}" ] || [ -L "${INSTALL_ROOT}/${item}" ]; then
            mv -- "${INSTALL_ROOT}/${item}" "${BACKUP_ROOT}/${item}" || return 1
            BACKED_UP_ITEMS+=("${item}")
        fi
    done
    for item in "${MANAGED_ITEMS[@]}"; do
        mv -- "${STAGE_ROOT}/${item}" "${INSTALL_ROOT}/${item}" || return 1
        ACTIVATED_ITEMS+=("${item}")
    done
    rmdir "${STAGE_ROOT}" || return 1
    STAGE_ROOT=""

    units_touched=1
    rm -f -- "${AGENT_UNIT_FILE}" "${WEB_UNIT_FILE}" || return 1
    install -o root -g root -m 0644 \
        "${INSTALL_ROOT}/deploy/safeops-agent.service" "${AGENT_UNIT_FILE}" || return 1
    install -o root -g root -m 0644 \
        "${INSTALL_ROOT}/deploy/safeops-web.service" "${WEB_UNIT_FILE}" || return 1
    systemctl daemon-reload || return 1

    agent_enable_touched=1
    systemctl enable safeops-agent || return 1
    systemctl start safeops-agent || return 1
    wait_for_backend_health || return 1
    if [ "${web_was_active}" -eq 1 ]; then
        systemctl start safeops-web || return 1
    fi

    ACTIVATION_COMMITTED=1
    PRESERVE_BACKUP=0
    if cleanup_backup; then
        BACKUP_ROOT=""
    else
        echo "[WARN] Healthy release is active, but ${BACKUP_ROOT} could not be removed." >&2
        PRESERVE_BACKUP=1
    fi
    echo "[OK] Activated staged release and passed backend health check"
    return 0
}

activation_status=0
activate_release || activation_status=$?
if [ "${activation_status}" -ne 0 ]; then
    echo "[ERROR] Release activation failed; starting rollback." >&2
    restore_previous_release || true
    exit "${activation_status}"
fi

# 6. Sudoers
echo "[SKIP] sudoers template is not installed by default"
echo "       Review deploy/sudoers.safeops-agent manually before granting extra privileges"

# 7. The systemd units were installed as part of the release transaction.

# 8. The backend and its same-origin Vue console are now healthy.
# Streamlit is retained as an optional development frontend and is not enabled
# by default, avoiding pyarrow/Streamlit runtime requirements on LoongArch64.

echo "=== Deployment Complete ==="
echo "API:  ${HEALTH_URL}"
echo "Web:  http://127.0.0.1:8000/console/"
echo "Optional Streamlit service was not enabled."
echo "Streamlit is an optional fallback frontend, not the default Kylin entry point."
echo "To enable it after reviewing dependencies:"
echo "  /opt/safeopsagent/venv/bin/pip install -r /opt/safeopsagent/backend/requirements.txt"
echo "  systemctl enable --now safeops-web"
echo "Optional test dependencies:"
echo "  /opt/safeopsagent/venv/bin/pip install -r /opt/safeopsagent/backend/requirements-dev.txt"
