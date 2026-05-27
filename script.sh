#!/bin/bash

# Вихід при будь-якій помилці
set -e

# Визначаємо папку, де зараз лежить сам скрипт і код застосунку
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "=== Етап 1: Оновлення системи та встановлення пакетів ==="
sudo apt update && sudo apt upgrade -y
sudo apt install -y mariadb-server nginx python3 python3-pip git gunicorn

# Встановлення необхідних бібліотек для Python
sudo pip3 install Flask mysql-connector-python --break-system-packages

echo "=== Етап 2: Створення користувачів та налаштування прав ==="
# Функція для безпечного створення користувача
create_user_if_not_exists() {
    local username=$1
    local is_system=$2
    
    if id "$username" &>/dev/null; then
        echo "Користувач $username вже існує, пропускаємо створення."
    else
        if [ "$is_system" = "system" ]; then
            sudo useradd -r -s /usr/sbin/nologin "$username"
            echo "Системного користувача $username успішно створено."
        else
            if [ "$username" = "operator" ]; then
                sudo useradd -m -g operator -s /bin/bash "$username"
            else
                sudo useradd -m -s /bin/bash "$username"
            fi
            echo "Користувача $username успішно створено."
        fi
    fi
}

create_user_if_not_exists "student" "regular"
create_user_if_not_exists "teacher" "regular"
create_user_if_not_exists "app" "system"
create_user_if_not_exists "operator" "regular"

# Додавання до групи sudo
sudo usermod -aG sudo student
sudo usermod -aG sudo teacher

# Встановлення паролів за замовчуванням
echo "student:12345678" | sudo chpasswd
echo "teacher:12345678" | sudo chpasswd
echo "operator:12345678" | sudo chpasswd

# Примусова зміна пароля при першому вході
sudo passwd -e student
sudo passwd -e teacher
sudo passwd -e operator

echo "=== Етап 3: Обмеження прав для operator через sudo ==="
cat << 'EOF' | sudo tee /etc/sudoers.d/operator
operator ALL=(ALL) NOPASSWD: /usr/bin/systemctl start mywebapp, \
                             /usr/bin/systemctl stop mywebapp, \
                             /usr/bin/systemctl restart mywebapp, \
                             /usr/bin/systemctl status mywebapp, \
                             /usr/bin/systemctl reload nginx
EOF
sudo chmod 0440 /etc/sudoers.d/operator

echo "=== Етап 4: Налаштування бази даних MariaDB ==="
sudo mysql -e "CREATE DATABASE IF NOT EXISTS inventory_db;"
sudo mysql -e "CREATE USER IF NOT EXISTS 'inventory_user'@'localhost' IDENTIFIED BY 'password123';"
sudo mysql -e "GRANT ALL PRIVILEGES ON inventory_db.* TO 'inventory_user'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

echo "=== Етап 5: Копіювання файлів застосунку та налаштування прав доступу ==="
# Відкриваємо доступ до домашньої папки student для користувача app
sudo chmod 755 /home/student

# Створюємо робочу директорію сервісу
sudo mkdir -p /home/student/mywebapp

# Копіюємо код застосунку
if [ -f "$PROJECT_DIR/app.py" ]; then
    sudo cp "$PROJECT_DIR/app.py" /home/student/mywebapp/app.py
else
    echo "Помилка: файл app.py не знайдено поруч зі скриптом!"
    exit 1
fi

# Налаштовуємо права: папка та файли мають бути доступні для читання користувачу app
sudo chown -R student:student /home/student/mywebapp
sudo chmod 755 /home/student/mywebapp
sudo chmod 644 /home/student/mywebapp/app.py

echo "=== Етап 6: Створення Systemd-юнітів (Socket Activation) ==="
cat << 'EOF' | sudo tee /etc/systemd/system/mywebapp.socket
[Unit]
Description=Socket for MyWebApp

[Socket]
ListenStream=127.0.0.1:8000

[Install]
WantedBy=sockets.target
EOF

# Визначаємо точний шлях до gunicorn
GUNICORN_PATH=$(which gunicorn || echo "/usr/bin/gunicorn")

cat << EOF | sudo tee /etc/systemd/system/mywebapp.service
[Unit]
Description=MyWebApp Simple Inventory Service
After=network.target mariadb.service
Requires=mywebapp.socket

[Service]
Type=simple
User=app
Group=app
WorkingDirectory=/home/student/mywebapp
ExecStart=$GUNICORN_PATH --workers 2 app:app
Restart=always
EOF

# Перезавантажуємо systemd та запускаємо сокет
sudo systemctl daemon-reload
sudo systemctl reset-failed mywebapp.service mywebapp.socket
sudo systemctl enable --now mywebapp.socket

echo "=== Етап 7: Налаштування Nginx як Reverse Proxy ==="
cat << 'EOF' | sudo tee /etc/nginx/sites-available/mywebapp
server {
    listen 80;
    server_name localhost;

    access_log /var/log/nginx/mywebapp_access.log;
    error_log /var/log/nginx/mywebapp_error.log;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/mywebapp /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl restart nginx

echo "=== Етап 8: Створення обов'язкових файлів (gradebook) ==="
echo "8" | sudo tee /home/student/gradebook
sudo chown student:student /home/student/gradebook
sudo chmod 644 /home/student/gradebook

echo "======================================================="
echo " РОЗГОРТАННЯ ЗАВЕРШЕНО УСПІШНО!                        "
echo "======================================================="
