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

# 1. Create opsagent user
if ! id opsagent &>/dev/null; then
    useradd -r -s /bin/false -M opsagent
    echo "[OK] Created opsagent user"
else
    echo "[SKIP] opsagent user exists"
fi

# 2. Create directories
mkdir -p "${INSTALL_ROOT}" "${INSTALL_ROOT}/data" /var/log/safeopsagent "${ENV_DIR}"
chown opsagent:opsagent /var/log/safeopsagent "${INSTALL_ROOT}/data"
chmod 750 "${ENV_DIR}"

# 2.1 Create default environment file if absent
if [ ! -f "${ENV_FILE}" ]; then
    cat > "${ENV_FILE}" <<'EOF'
MODEL_PROVIDER=offline_safe
MODEL_API_BASE=
MODEL_API_KEY=
MODEL_NAME=
BACKEND_URL=http://127.0.0.1:8000
EOF
    chown root:opsagent "${ENV_FILE}"
    chmod 640 "${ENV_FILE}"
    echo "[OK] Created ${ENV_FILE}"
else
    echo "[SKIP] ${ENV_FILE} exists"
fi

# 3. Create venv
if [ ! -d "${INSTALL_ROOT}/venv" ]; then
    python3 -m venv "${INSTALL_ROOT}/venv"
    echo "[OK] Created venv"
fi

# 4. Install the minimal Kylin backend dependencies.
# The primary UI is the Vue console served by FastAPI at /console/.
# Streamlit and developer test dependencies remain opt-in.
source "${INSTALL_ROOT}/venv/bin/activate"
pip install -r "${PROJECT_ROOT}/backend/requirements-kylin.txt"

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
chown -R opsagent:opsagent "${INSTALL_ROOT}"

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
