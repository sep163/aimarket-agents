#!/usr/bin/env bash
# First-time (and repeatable) deploy of aimarket-agents onto a Linux server
# with systemd. Safe to re-run: it never overwrites an existing .env, and it
# re-syncs code + dependencies + systemd units every time.
#
# Usage (run this from inside the extracted aimarket-agents/ folder on the server):
#   sudo ./deploy/deploy.sh
#
# Optional env vars to override defaults:
#   APP_DIR=/opt/aimarket-agents APP_USER=aimarket sudo -E ./deploy/deploy.sh

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aimarket-agents}"
APP_USER="${APP_USER:-aimarket}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите через sudo: sudo ./deploy/deploy.sh" >&2
  exit 1
fi

echo "==> Системный пользователь ${APP_USER}"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --shell /usr/sbin/nologin --home-dir "${APP_DIR}" --create-home "${APP_USER}"
  echo "    создан"
else
  echo "    уже существует"
fi

echo "==> Код в ${APP_DIR}"
mkdir -p "${APP_DIR}"
if [[ "${SOURCE_DIR}" != "${APP_DIR}" ]]; then
  rsync -a --delete \
    --exclude 'venv' \
    --exclude '.env' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '.git' \
    "${SOURCE_DIR}/" "${APP_DIR}/"
fi

echo "==> Виртуальное окружение"
if [[ ! -d "${APP_DIR}/venv" ]]; then
  python3 -m venv "${APP_DIR}/venv"
fi
"${APP_DIR}/venv/bin/pip" install --quiet --upgrade pip
"${APP_DIR}/venv/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"

echo "==> .env"
if [[ ! -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/.env.placeholder" "${APP_DIR}/.env"
  echo "    создан из .env.placeholder (заглушки - замените реальными секретами через deploy/update-secrets.sh)"
else
  echo "    уже существует, не трогаю"
fi

echo "==> Права"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "==> systemd юниты"
cp "${APP_DIR}/systemd/"*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now aimarket-agent4-bot aimarket-agent5-qa-bot aimarket-agent5-scheduler

echo "==> Готово. Статус через 3 секунды:"
sleep 3
for svc in aimarket-agent4-bot aimarket-agent5-qa-bot aimarket-agent5-scheduler; do
  echo "--- ${svc} ---"
  systemctl --no-pager --lines=5 status "${svc}" || true
done

cat <<'EOF'

Ожидаемое поведение с заглушками из .env.placeholder:
  - aimarket-agent5-scheduler: active (running), просто ждёт расписания.
  - aimarket-agent4-bot / aimarket-agent5-qa-bot: active (running), но раз в
    30 секунд пишут в лог "Bot polling stopped (often an invalid or
    placeholder ... TOKEN)" - это ожидаемо, не баг.

Логи любого сервиса:
  journalctl -u aimarket-agent4-bot -f

Когда будут реальные секреты - смотрите deploy/update-secrets.sh.
EOF
