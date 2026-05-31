#!/bin/bash
set -e

RAW_IMAGE_TAG=$1
CONTAINER_NAME="simple-inventory"
PORT=5000

IMAGE_TAG=$(echo "$RAW_IMAGE_TAG" | tr '[:upper:]' '[:lower:]')

echo "=== Оновлення середовища на Target Node ==="
sudo systemctl start docker

echo "=== Авторизація в GitHub Container Registry ==="
echo "${GITHUB_TOKEN}" | docker login ghcr.io -u "${GITHUB_ACTOR}" --password-stdin

echo "=== Стягування нового образу (Lowercase): ${IMAGE_TAG} ==="
docker pull "${IMAGE_TAG}"

echo "=== Створення та налаштування Systemd-юніта для керування контейнером ==="
sudo bash -c "cat <<EOF > /etc/systemd/system/${CONTAINER_NAME}.service
[Unit]
Description=Flask Simple Inventory App in Docker
After=docker.service
Requires=docker.service

[Service]
TimeoutStartSec=0
Restart=always
ExecStartPre=-/usr/bin/docker stop ${CONTAINER_NAME}
ExecStartPre=-/usr/bin/docker rm ${CONTAINER_NAME}
ExecStart=/usr/bin/docker run --name ${CONTAINER_NAME} -p ${PORT}:5000 --network=host ${IMAGE_TAG}
ExecStop=/usr/bin/docker stop ${CONTAINER_NAME}

[Install]
WantedBy=multi-user.target
EOF"

echo "=== Перезапуск Systemd та запуск сервісу ==="
sudo systemctl daemon-reload
sudo systemctl enable ${CONTAINER_NAME}.service
sudo systemctl restart ${CONTAINER_NAME}.service

echo "=== Деплой успішно завершено! ==="
