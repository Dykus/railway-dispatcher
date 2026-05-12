# tests/test_scenarios.py
import os
import sys
import tempfile
import pytest

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Перед импортом приложения настраиваем временную базу данных и папку бэкапов
@pytest.fixture(scope='function')
def app():
    """Создаёт новое приложение с временной БД для каждого теста."""
    tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp_db.close()
    temp_db_path = tmp_db.name
    temp_dir = os.path.dirname(temp_db_path)
    temp_backup_dir = os.path.join(temp_dir, 'backups_test')
    os.makedirs(temp_backup_dir, exist_ok=True)

    # Подменяем пути в конфигурации
    import config
    config.DB_NAME = temp_db_path
    config.BASE_DIR = temp_dir
    config.BACKUP_DIR = temp_backup_dir

    # Перезагружаем модули, которые могли запомнить старые значения
    import importlib
    for mod in ['app.models', 'app.utils', 'app.routes.main',
                'app.routes.admin', 'app.routes.api', 'app.routes.export',
                'app.routes.history', 'app']:
        if mod in sys.modules:
            del sys.modules[mod]

    from app import create_app
    flask_app = create_app()
    flask_app.config['TESTING'] = True

    # Отключаем проверку прав доступа (для тестов логики)
    @flask_app.before_request
    def fake_auth():
        from flask import request
        request.user_role = 'admin'

    yield flask_app

    # Убираем временные файлы после теста
    os.unlink(temp_db_path)
    import shutil
    shutil.rmtree(temp_backup_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    """Тестовый клиент, связанный с текущим приложением."""
    return app.test_client()


# ==================== САМИ ПРОВЕРКИ ====================

def test_add_wagon_success(client):
    """Добавление вагона должно завершаться успехом."""
    response = client.post('/add', data={
        'number': '12345678',
        'owner': 'ОАО РЖД',
        'organization': 'Завод',
        'note': 'Уголь',
        'track_id': '1',
        'cycle_days': '1',
        'cycle_hours': '2',
        'cycle_mins': '30'
    })

    # Успешное добавление возвращает редирект
    assert response.status_code == 302
    redirect_response = client.get(response.headers['Location'])
    assert redirect_response.status_code == 200
    assert 'Вагон 12345678 добавлен' in redirect_response.data.decode('utf-8')

    # Проверяем, что вагон записался в базу
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM wagons WHERE wagon_number = '12345678'")
    row = c.fetchone()
    conn.close()
    assert row is not None
    assert row[4] == 'ОАО РЖД'   # владелец
    assert row[7] == 1           # ID пути


def test_move_wagon_and_local_deadline(client):
    """Перемещение вагона должно менять путь и устанавливать локальный срок."""
    # 1. Добавляем тестовый вагон
    client.post('/add', data={
        'number': '99999999',
        'owner': 'ТК Тест',
        'organization': 'Организация',
        'note': '',
        'track_id': '1',
        'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    }, follow_redirects=True)

    # 2. Узнаём его ID
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagons WHERE wagon_number = '99999999'")
    wagon_id = c.fetchone()[0]
    conn.close()

    # 3. Перемещаем на путь 3 с локальным сроком 1.5 часа
    response = client.post('/move', data={
        'wagon_id': str(wagon_id),
        'new_track_id': '3',
        'local_days': '0',
        'local_hours': '1',
        'local_mins': '30',
        'note': 'Ремонт'
    })

    assert response.status_code == 302
    redirect_response = client.get(response.headers['Location'])
    assert 'Вагон перемещен' in redirect_response.data.decode('utf-8')

    # 4. Проверяем изменения в базе
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT track_id, local_departure_time, visit_count FROM wagons WHERE id = ?", (wagon_id,))
    row = c.fetchone()
    conn.close()
    assert row[0] == 3           # новый путь
    assert row[1] is not None    # локальный срок установлен
    assert row[2] == 1           # счётчик посещений увеличился (путь не возвратный)


def test_viewer_cannot_add_wagon(app):
    """Роль viewer не должна иметь права добавлять вагоны."""
    # Временно переопределяем before_request для проверки прав
    @app.before_request
    def set_viewer_role():
        from flask import request
        request.user_role = 'viewer'

    with app.test_client() as client:
        response = client.post('/add', data={
            'number': '12345678',
            'owner': 'Кто-то',
            'organization': 'Где-то',
            'track_id': '1'
        })
        assert response.status_code == 403