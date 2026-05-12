import tempfile
import os
import sys
import importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Сначала создаём временную базу и настраиваем config
tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
tmp_db.close()
temp_db_path = tmp_db.name
temp_dir = os.path.dirname(temp_db_path)
temp_backup_dir = os.path.join(temp_dir, 'backups_test')
os.makedirs(temp_backup_dir, exist_ok=True)

import config
config.DB_NAME = temp_db_path
config.BASE_DIR = temp_dir
config.BACKUP_DIR = temp_backup_dir

# Перезагружаем модули, которые уже импортировали старые значения
# Удаляем их из кэша и импортируем заново
for mod in ['app.models', 'app.utils', 'app.routes.main', 'app.routes.admin',
            'app.routes.api', 'app.routes.export', 'app.routes.history', 'app']:
    if mod in sys.modules:
        del sys.modules[mod]

# Теперь импортируем create_app и models заново
from app import create_app
import app.models as models

def test_add_wagon_success():
    app = create_app()
    app.config['TESTING'] = True

    # Отключаем проверку прав доступа
    @app.before_request
    def fake_auth():
        from flask import request
        request.user_role = 'admin'

    with app.test_client() as client:
        # Пробуем добавить вагон
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

        if response.status_code == 200:
            page_text = response.data.decode('utf-8')
            if 'alert-error' in page_text:
                import re
                match = re.search(r'alert-error[^>]*>([^<]+)', page_text)
                error_msg = match.group(1) if match else page_text[:2000]
                raise AssertionError(f"Ошибка при добавлении: {error_msg}")
            else:
                raise AssertionError(f"Неожиданный ответ (200):\n{page_text[:2000]}")

        # Успешное добавление возвращает редирект (302)
        assert response.status_code == 302
        redirect_response = client.get(response.headers['Location'])
        assert redirect_response.status_code == 200
        assert 'Вагон 12345678 добавлен' in redirect_response.data.decode('utf-8')

        # Проверяем наличие в БД
        conn = models.get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM wagons WHERE wagon_number = '12345678'")
        row = c.fetchone()
        conn.close()
        assert row is not None
        assert row[4] == 'ОАО РЖД'
        assert row[7] == 1

    # Убираем временные файлы
    os.unlink(temp_db_path)
    import shutil
    shutil.rmtree(temp_backup_dir, ignore_errors=True)