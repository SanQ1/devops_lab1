import pytest
from unittest.mock import MagicMock, patch
from app import app


# Фікстура pytest, яка створює тестового клієнта Flask.
@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


# 1. ТЕСТ ДЛЯ ЕНДПОІНТУ /health/alive
def test_health_alive(client):
    """Перевіряє, що хелсчек alive завжди повертає статус 200 та текст OK."""
    response = client.get('/health/alive')
    assert response.status_code == 200
    assert response.data.decode('utf-8') == "OK"


# 2. ТЕСТ ДЛЯ ЕНДПОІНТУ /health/ready 
@patch('app.get_db_connection')
def test_health_ready_success(mock_get_db, client):
    """Імітує успішне підключення до БД. Ендпоінт має повернути 200."""
    mock_conn = MagicMock()
    mock_get_db.return_value = mock_conn
    
    response = client.get('/health/ready')
    assert response.status_code == 200
    assert response.data.decode('utf-8') == "OK"
    mock_conn.ping.assert_called_once_with(reconnect=True)


# 3. ТЕСТ ДЛЯ ЕНДПОІНТУ /health/ready (ПОМИЛКА БД)
@patch('app.get_db_connection')
def test_health_ready_failure(mock_get_db, client):
    """Імітує падіння бази даних. Ендпоінт має повернути 500."""
    mock_get_db.side_effect = Exception("Connection refused")
    
    response = client.get('/health/ready')
    assert response.status_code == 500
    assert "Сервіс не готовий" in response.data.decode('utf-8')


# 4. ТЕСТ ДЛЯ КОРЕНЕВОГО МАРШРУТУ /
def test_root_endpoint(client):
    """Перевіряє кореневу HTML-сторінку на наявність правильних заголовків."""
    response = client.get('/')
    assert response.status_code == 200
    assert "Simple Inventory" in response.data.decode('utf-8')
    assert response.headers['Content-Type'] == 'text/html; charset=utf-8'


# 5. ТЕСТ ДЛЯ GET /items 
@patch('app.get_db_connection')
def test_get_items_json(mock_get_db, client):
    """Перевіряє віддачу списку інвентарю у форматі JSON за наявності Accept header."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {"id": 1, "name": "Switch Cisco"},
        {"id": 2, "name": "Server HP"}
    ]
    mock_conn.cursor.return_value = mock_cursor
    mock_get_db.return_value = mock_conn

    response = client.get('/items', headers={"Accept": "application/json"})
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data) == 2
    assert json_data[0]['name'] == "Switch Cisco"
    assert json_data[1]['id'] == 2


# 6. ТЕСТ ДЛЯ GET /items 
@patch('app.get_db_connection')
def test_get_items_html(mock_get_db, client):
    """Перевіряє віддачу списку інвентарю у вигляді HTML-таблиці за замовчуванням."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [{"id": 1, "name": "Switch Cisco"}]
    mock_conn.cursor.return_value = mock_cursor
    mock_get_db.return_value = mock_conn

    response = client.get('/items')
    
    assert response.status_code == 200
    html_content = response.data.decode('utf-8')
    assert "<h1>Список предметів в інвентарі</h1>" in html_content
    assert "<td>Switch Cisco</td>" in html_content


# 7. ТЕСТ ДЛЯ POST /items (СТВОРЕННЯ НОВОГО ПРЕДМЕТА ЧЕРЕЗ JSON)
@patch('app.get_db_connection')
def test_post_item_json(mock_get_db, client):
    """Перевіряє успішне додавання нового предмета в базу даних."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.lastrowid = 42  
    mock_conn.cursor.return_value = mock_cursor
    mock_get_db.return_value = mock_conn

    test_data = {"name": "Router Mikrotik", "quantity": 5}
    response = client.post('/items', json=test_data)
    
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['id'] == 42
    assert json_data['message'] == "Запис успішно створено"
    
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
