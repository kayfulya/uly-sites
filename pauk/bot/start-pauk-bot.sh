#!/bin/bash
# Стартует Бота Свидетелей Паука в фоне.
# Если бот уже запущен — ничего не делает.

cd "/Users/ula/Documents/Personal/Pauk-respect/bot" || exit 1

if pgrep -f "Pauk-respect/bot/bot.py" >/dev/null; then
    echo "Бот уже работает." >> /tmp/pauk-bot.log
    exit 0
fi

nohup ./venv/bin/python bot.py >> /tmp/pauk-bot.log 2>&1 &
disown
