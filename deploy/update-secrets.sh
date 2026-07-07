#!/usr/bin/env bash
# One-command swap of placeholder secrets for real ones + restart + live log check.
#
# Usage:
#   sudo ./deploy/update-secrets.sh /path/to/real.env [/path/to/real_service_account.json]
#
# /path/to/real.env should be a filled-in copy of .env.placeholder (same keys,
# real values). The optional second argument is the Google service-account
# JSON key for Agent 4's Google Sheets access.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/aimarket-agents}"
APP_USER="${APP_USER:-aimarket}"
NEW_ENV_FILE="${1:-}"
NEW_SERVICE_ACCOUNT_FILE="${2:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Запустите через sudo: sudo ./deploy/update-secrets.sh /path/to/real.env" >&2
  exit 1
fi

if [[ -z "${NEW_ENV_FILE}" || ! -f "${NEW_ENV_FILE}" ]]; then
  echo "Укажите путь к заполненному .env первым аргументом." >&2
  echo "Пример: sudo ./deploy/update-secrets.sh ./real.env ./real_service_account.json" >&2
  exit 1
fi

if grep -qi 'PLACEHOLDER\|placeholder-replace-me\|sk-placeholder' "${NEW_ENV_FILE}"; then
  echo "Внимание: в ${NEW_ENV_FILE} остались значения-заглушки. Продолжаю всё равно," >&2
  echo "но агенты не заработают, пока все поля не будут реальными." >&2
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

echo "==> Бэкап текущего .env -> ${APP_DIR}/.env.bak.${TIMESTAMP}"
if [[ -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/.env" "${APP_DIR}/.env.bak.${TIMESTAMP}"
fi

echo "==> Устанавливаю новый .env"
cp "${NEW_ENV_FILE}" "${APP_DIR}/.env"

if [[ -n "${NEW_SERVICE_ACCOUNT_FILE}" ]]; then
  echo "==> Устанавливаю новый service_account.json"
  cp "${NEW_SERVICE_ACCOUNT_FILE}" "${APP_DIR}/service_account.json"
fi

chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env"
[[ -n "${NEW_SERVICE_ACCOUNT_FILE}" ]] && chown "${APP_USER}:${APP_USER}" "${APP_DIR}/service_account.json"
chmod 600 "${APP_DIR}/.env"

echo "==> Перезапуск сервисов"
systemctl restart aimarket-agent4-bot aimarket-agent5-qa-bot aimarket-agent5-scheduler

echo "==> Жду 5 секунд и смотрю живой статус..."
sleep 5
for svc in aimarket-agent4-bot aimarket-agent5-qa-bot aimarket-agent5-scheduler; do
  echo "--- ${svc} ---"
  systemctl --no-pager --lines=10 status "${svc}" || true
  echo
done

cat <<EOF
Готово. Проверка вживую:
  journalctl -u aimarket-agent4-bot -f       # написать боту в Telegram и смотреть сюда
  journalctl -u aimarket-agent5-qa-bot -f    # задать вопрос по метрикам
  journalctl -u aimarket-agent5-scheduler -f # ждать 06:00 / воскресенье 09:00, или запустить руками:
    sudo -u ${APP_USER} ${APP_DIR}/venv/bin/python -m agent5_marketing_analytics.sync
    sudo -u ${APP_USER} ${APP_DIR}/venv/bin/python -m agent5_marketing_analytics.weekly_report

Откат к предыдущим значениям, если что-то не так:
  sudo cp ${APP_DIR}/.env.bak.${TIMESTAMP} ${APP_DIR}/.env
  sudo systemctl restart aimarket-agent4-bot aimarket-agent5-qa-bot aimarket-agent5-scheduler
EOF
