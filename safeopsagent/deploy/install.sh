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
        console_password_hash="$(python3 "${PROJECT_ROOT}/scripts/hash_console_password.py")"
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

# 3. Recreate the root-owned venv on every install. Never execute files from a
# service-account-writable environment during a privileged upgrade.
rm -rf -- "${INSTALL_ROOT}/venv"
python3 -m venv "${INSTALL_ROOT}/venv"
chown -R root:root "${INSTALL_ROOT}/venv"
echo "[OK] Recreated venv"

# 4. Install the minimal Kylin backend dependencies.
# The primary UI is the Vue console served by FastAPI at /console/.
# Streamlit and developer test dependencies remain opt-in.
"${INSTALL_ROOT}/venv/bin/python" -m pip install \
    -r "${PROJECT_ROOT}/backend/requirements-kylin.txt"

# 5. Copy project
rm -rf "${INSTALL_ROOT}/backend" "${INSTALL_ROOT}/frontend" "${INSTALL_ROOT}/deploy" \
       "${INSTALL_ROOT}/config" "${INSTALL_ROOT}/scripts" "${INSTALL_ROOT}/docs"
cp -r "${PROJECT_ROOT}/backend" "${INSTALL_ROOT}/"
cp -r "${PROJECT_ROOT}/frontend" "${INSTALL_ROOT}/"
cp -r "${PROJECT_ROOT}/deploy" "${INSTALL_ROOT}/"
cp -r "${PROJECT_ROOT}/config" "${INSTALL_ROOT}/"
cp -r "${PROJECT_ROOT}/scripts" "${INSTALL_ROOT}/"
cp -r "${PROJECT_ROOT}/docs" "${INSTALL_ROOT}/"
cp "${PROJECT_ROOT}/README.md" "${INSTALL_ROOT}/"
cp "${PROJECT_ROOT}/.env.example" "${INSTALL_ROOT}/"
chown -R root:root "${INSTALL_ROOT}"
chmod -R go-w "${INSTALL_ROOT}"
chown -R opsagent:opsagent "${INSTALL_ROOT}/data" /var/log/safeopsagent

# 6. Sudoers
echo "[SKIP] sudoers template is not installed by default"
echo "       Review deploy/sudoers.safeops-agent manually before granting extra privileges"

# 7. Systemd
cp "${PROJECT_ROOT}/deploy/safeops-agent.service" /etc/systemd/system/
cp "${PROJECT_ROOT}/deploy/safeops-web.service" /etc/systemd/system/
systemctl daemon-reload

# 8. Start the backend and its same-origin Vue console.
# Streamlit is retained as an optional development frontend and is not enabled
# by default, avoiding pyarrow/Streamlit runtime requirements on LoongArch64.
systemctl enable safeops-agent
systemctl start safeops-agent

echo "=== Deployment Complete ==="
echo "API:  http://127.0.0.1:8000/health"
echo "Web:  http://127.0.0.1:8000/console/"
echo "Optional Streamlit service was not enabled."
echo "Streamlit is an optional fallback frontend, not the default Kylin entry point."
echo "To enable it after reviewing dependencies:"
echo "  /opt/safeopsagent/venv/bin/pip install -r /opt/safeopsagent/backend/requirements.txt"
echo "  systemctl enable --now safeops-web"
echo "Optional test dependencies:"
echo "  /opt/safeopsagent/venv/bin/pip install -r /opt/safeopsagent/backend/requirements-dev.txt"
