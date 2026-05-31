import sys
import argparse
import mysql.connector
import os
import time
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime

app = Flask(__name__)

# ПАРСИНГ АРГУМЕНТІВ КОМАНДНОГО РЯДКА ТА ЗМІННИХ ОТОЧЕННЯ
parser = argparse.ArgumentParser(description="MyWebApp: Simple Inventory Service")
parser.add_argument('--port', type=int, default=int(os.environ.get('APP_PORT', 8000)), help="Порт застосунку")
parser.add_argument('--db-host', type=str, default=os.environ.get('DB_HOST', 'localhost'), help="Хост MariaDB")
parser.add_argument('--db-user', type=str, default=os.environ.get('DB_USER', 'inventory_user'),
                    help="Користувач MariaDB")
parser.add_argument('--db-password', type=str, default=os.environ.get('DB_PASSWORD', 'password123'),
                    help="Пароль MariaDB")
parser.add_argument('--db-name', type=str, default=os.environ.get('DB_NAME', 'inventory_db'), help="Назва бази даних")

args, unknown = parser.parse_known_args()

# Формуємо конфігурацію підключення до MariaDB
db_config = {
    'host': args.db_host,
    'user': args.db_user,
    'password': args.db_password,
    'database': args.db_name
}


def get_db_connection():
    """Функція для підключення до бази даних."""
    return mysql.connector.connect(**db_config)


# СКРИПТ МІГРАЦІЇ БАЗИ ДАНИХ
def run_migrations():
    """Автоматично створює таблицю для інвентарю при старті з механізмом повторних спроб."""
    print("Очікування готовності бази даних для виконання міграцій...")
    retries = 10
    while retries > 0:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    quantity INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            cursor.close()
            conn.close()
            print("Міграцію бази даних успішно виконано.")
            return
        except Exception as e:
            retries -= 1
            print(f"База даних ще не готова (очікування портів). Спроб залишилось: {retries}. Помилка: {e}")
            time.sleep(3)
    print("Критична помилка: Не вдалося підключитися до БД для виконання міграцій!", file=sys.stderr)


# Запускаємо міграцію одразу при ініціалізації застосунку
run_migrations()


# ХЕЛСЧЕКИ
@app.route('/health/alive', methods=['GET'])
def health_alive():
    """Завжди повертає HTTP 200 OK з вмістом ОК."""
    return "OK", 200


@app.route('/health/ready', methods=['GET'])
def health_ready():
    """Перевіряє підключення до БД. Якщо успішно - 200, якщо ні - 500."""
    try:
        conn = get_db_connection()
        conn.ping(reconnect=True)
        conn.close()
        return "OK", 200
    except Exception as e:
        return f"Сервіс не готовий (відсутнє підключення до БД): {str(e)}", 500


# КОРЕНЕВИЙ ЕНДПОІНТ
@app.route('/', methods=['GET'])
def root_endpoint():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body>
        <h1>Оберіть ендпоінт бізнес-логіки (Варіант 8 - Simple Inventory)</h1>
        <ul>
            <li><a href="/items">GET /items</a> - Перегляд списку предметів</li>
            <li>POST /items - Додати новий предмет</li>
        </ul>
    </body>
    </html>
    """
    # Додаємо charset=utf-8 у заголовок відповіді
    return render_template_string(html_content), 200, {'Content-Type': 'text/html; charset=utf-8'}


# БІЗНЕС-ЛОГІКА
def render_by_accept_header(data, html_template):
    accept_header = request.headers.get('Accept', '')
    if 'application/json' in accept_header:
        return jsonify(data)
    else:
        full_html = f'<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>{html_template}</body></html>'
        # Повертаємо заголовок із правильним кодуванням для кирилиці
        return render_template_string(full_html, data=data), 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/items', methods=['GET', 'POST'])
def manage_items():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Створення нового запису в інвентарі
        if request.is_json:
            req_data = request.get_json()
            name = req_data.get('name')
            quantity = req_data.get('quantity')
        else:
            name = request.form.get('name')
            quantity = request.form.get('quantity')

        cursor.execute("INSERT INTO inventory_items (name, quantity) VALUES (%s, %s)", (name, quantity))
        conn.commit()
        new_id = cursor.lastrowid

        cursor.close()
        conn.close()
        return jsonify({"message": "Запис успішно створено", "id": new_id}), 201

    else:
        # GET /items - вивести список усіх предметів (тільки id, name)
        # text2
        cursor.execute("SELECT id, name FROM inventory_items")
        items = cursor.fetchall()
        cursor.close()
        conn.close()

        html_template = """
        <h1>Список предметів в інвентарі</h1>
        <table border="1">
            <tr><th>ID</th><th>Назва</th></tr>
            {% for item in data %}
            <tr><td>{{ item.id }}</td><td>{{ item.name }}</td></tr>
            {% endfor %}
        </table>
        """
        return render_by_accept_header(items, html_template)


@app.route('/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    # GET /items/<id> - детальна інформація по запису в інвентарі
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, quantity, created_at FROM inventory_items WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    cursor.close()
    conn.close()

    if not item:
        return jsonify({"error": "Предмет не знайдено"}), 404

    # Перетворюємо об'єкт datetime на рядок для коректного відображення
    if isinstance(item['created_at'], datetime):
        item['created_at'] = item['created_at'].strftime('%Y-%m-%d %H:%M:%S')

    html_template = """
    <h1>Детальна інформація про предмет</h1>
    <table border="1">
        <tr><th>Поле</th><th>Значення</th></tr>
        <tr><td><b>ID</b></td><td>{{ data.id }}</td></tr>
        <tr><td><b>Назва</b></td><td>{{ data.name }}</td></tr>
        <tr><td><b>Кількість</b></td><td>{{ data.quantity }}</td></tr>
        <tr><td><b>Дата створення</b></td><td>{{ data.created_at }}</td></tr>
    </table>
    <br>
    <a href="/items">Назад до списку</a>
    """
    return render_by_accept_header(item, html_template)


# Цей блок спрацює, лише якщо запустити застосунок вручну через `python3 app.py`
if __name__ == '__main__':
    print(f"Локальний запуск застосунку на порту {args.port}...")
    app.run(host='127.0.0.1', port=args.port)
