#!/bin/bash
set -e

TARGET_IP=$1
PORT=80

echo "=== Запуск верифікації розгортання на ${TARGET_IP}:${PORT} ==="

echo "Перевірка ендпоінту /health/alive..."
STATUS_ALIVE=$(curl -s -o /dev/null -w "%{http_code}" http://${TARGET_IP}:${PORT}/health/alive)

if [ "$STATUS_ALIVE" -eq 200 ]; then
    echo "Успішно: /health/alive повернув HTTP 200"
else
    echo "Помилка: /health/alive повернув HTTP $STATUS_ALIVE"
    exit 1
fi

echo "Перевірка заголовків відповіді Nginx..."
HEADERS=$(curl -s -I http://${TARGET_IP}:${PORT}/health/alive)

if echo "$HEADERS" | grep -iq "Server: nginx"; then
    echo "Успішно: Запит проходить через Nginx (Reverse Proxy)"
else
    echo "Помилка: Заголовок Server не містить nginx. Перевірте конфігурацію!"
    exit 1
fi

echo "=== Верифікація пройшла успішно! Проєкт працює стабільно. ==="
