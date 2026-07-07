# Деплой на сервер

## Шаг 1: сейчас, с заглушками

На сервере (по SSH, из-под пользователя с sudo):

```bash
# перенести код на сервер (один из вариантов)
scp aimarket-agents-v2.zip you@server:/tmp/
ssh you@server
unzip /tmp/aimarket-agents-v2.zip -d ~/
cd ~/aimarket-agents

# сам деплой - идемпотентно, можно перезапускать
sudo ./deploy/deploy.sh
```

Что произойдёт:

- создаётся системный пользователь `aimarket`, код копируется в `/opt/aimarket-agents`
- ставится venv и зависимости
- `.env` создаётся из `.env.placeholder` (заглушки), если ещё не существует
- ставятся и включаются три systemd-сервиса: `aimarket-agent4-bot`, `aimarket-agent5-qa-bot`, `aimarket-agent5-scheduler`

Ожидаемое поведение с заглушками:

- `aimarket-agent5-scheduler` - `active (running)` сразу, просто ждёт расписания (06:00 синк, вс 09:00 отчёт).
- `aimarket-agent4-bot` и `aimarket-agent5-qa-bot` - тоже `active (running)` (не крашатся и не перезапускаются в цикле), но раз в 30 секунд тихо пишут в лог "Bot polling stopped (often an invalid or placeholder ... TOKEN)" - это ожидаемо: процесс поднялся, дошёл до Telegram API, и корректно ждёт настоящий токен.

Проверить:

```bash
sudo systemctl status aimarket-agent4-bot aimarket-agent5-qa-bot aimarket-agent5-scheduler
journalctl -u aimarket-agent4-bot -n 20
```

## Шаг 2: позже, одной командой - реальные секреты

Заполните `.env.placeholder` реальными значениями в отдельном файле (например `real.env`, не в репозитории) и, если нужно, подготовьте реальный `service_account.json` для Google Sheets. Затем на сервере:

```bash
sudo ./deploy/update-secrets.sh /path/to/real.env /path/to/service_account.json
```

Скрипт сам: бэкапит текущий `.env` с таймстемпом, ставит новый `.env` (и файл сервисного аккаунта, если передан), перезапускает все три сервиса и через 5 секунд печатает их живой статус - сразу видно, поднялись ли боты по-настоящему.

Дальше проверка вживую:

```bash
journalctl -u aimarket-agent4-bot -f       # написать боту в Telegram, смотреть сюда
journalctl -u aimarket-agent5-qa-bot -f    # задать вопрос по метрикам
sudo -u aimarket /opt/aimarket-agents/venv/bin/python -m agent5_marketing_analytics.sync            # синк руками, не дожидаясь 06:00
sudo -u aimarket /opt/aimarket-agents/venv/bin/python -m agent5_marketing_analytics.weekly_report    # отчёт руками, не дожидаясь воскресенья
```

Откат при проблеме:

```bash
sudo cp /opt/aimarket-agents/.env.bak.<таймстемп-из-вывода-скрипта> /opt/aimarket-agents/.env
sudo systemctl restart aimarket-agent4-bot aimarket-agent5-qa-bot aimarket-agent5-scheduler
```

## Важное ограничение

У меня (Claude) нет SSH-доступа или другого способа выполнять команды на вашем реальном сервере - я не подключён ни к какому серверному/SSH-коннектору, а инструменты управления экраном не позволяют печатать в Terminal (только кликать). Поэтому `deploy.sh` и `update-secrets.sh` нужно запускать вам самим по SSH - я их подготовил и проверил (синтаксис, идемпотентность, вся бизнес-логика внутри агентов), но выполнить два `sudo ./deploy/...` на сервере можете только вы. Если хотите, чтобы я мог делать это сам в следующий раз - скажите, через что у вас есть доступ к серверу (обычный SSH, панель хостинга, что-то ещё), поищу подходящий коннектор.
