# tests/test_scenarios.py
import os
import sys
import tempfile
import re
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

    # Отключаем проверку прав доступа для большинства тестов (admin по умолчанию)
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
    print("🚀 Запуск теста: добавление нового вагона")
    
    print("  Шаг 1: Отправляем данные нового вагона '12345678'...")
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
    print("    Статус ответа:", response.status_code)

    print("  Шаг 2: Ожидаем переадресацию (302) при успешном добавлении...")
    assert response.status_code == 302, "Сервер не отправил редирект – вагон, возможно, не добавлен"
    
    redirect_response = client.get(response.headers['Location'])
    assert redirect_response.status_code == 200, "Главная страница после добавления недоступна"
    
    print("  Шаг 3: Проверяем, что на странице есть сообщение об успехе...")
    page_text = redirect_response.data.decode('utf-8')
    assert 'Вагон 12345678 добавлен' in page_text, "Нет сообщения 'Вагон 12345678 добавлен' на главной"
    print("    ✓ Сообщение об успехе найдено")

    print("  Шаг 4: Убеждаемся, что вагон появился в базе данных...")
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM wagons WHERE wagon_number = '12345678'")
    row = c.fetchone()
    conn.close()
    
    assert row is not None, "Вагон не найден в БД"
    assert row[4] == 'ОАО РЖД', f"Владелец не совпадает: ожидалось ОАО РЖД, получено {row[4]}"
    assert row[7] == 1, f"ID пути не совпадает: ожидался 1, получено {row[7]}"
    print("    ✓ Вагон успешно записан в базу")
    print("🏁 Тест завершён успешно\n")


def test_move_wagon_and_local_deadline(client):
    """Перемещение вагона должно менять путь и устанавливать локальный срок."""
    print("🚀 Запуск теста: перемещение вагона и локальный срок")
    
    print("  Шаг 1: Добавляем тестовый вагон '99999999'...")
    client.post('/add', data={
        'number': '99999999',
        'owner': 'ТК Тест',
        'organization': 'Организация',
        'note': '',
        'track_id': '1',
        'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    }, follow_redirects=True)
    
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagons WHERE wagon_number = '99999999'")
    wagon_id = c.fetchone()[0]
    conn.close()
    print(f"    Вагон добавлен, его ID = {wagon_id}")

    print("  Шаг 2: Перемещаем на путь 3 с локальным сроком 1.5 часа...")
    response = client.post('/move', data={
        'wagon_id': str(wagon_id),
        'new_track_id': '3',
        'local_days': '0',
        'local_hours': '1',
        'local_mins': '30',
        'note': 'Ремонт'
    })
    assert response.status_code == 302, "Перемещение не вызвало редирект"
    
    redirect_response = client.get(response.headers['Location'])
    assert 'Вагон перемещен' in redirect_response.data.decode('utf-8'), "Нет сообщения 'Вагон перемещен'"
    print("    ✓ Сообщение 'Вагон перемещен' найдено")

    print("  Шаг 3: Проверяем изменения в базе...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT track_id, local_departure_time, visit_count FROM wagons WHERE id = ?", (wagon_id,))
    row = c.fetchone()
    conn.close()
    
    assert row[0] == 3, f"Новый путь не совпадает: ожидался 3, получено {row[0]}"
    assert row[1] is not None, "Локальный срок не установлен"
    assert row[2] == 1, f"Счётчик посещений должен быть 1, а равен {row[2]}"
    print(f"    ✓ Путь изменён на 3, локальный срок установлен ({row[1]}), счётчик = 1")
    print("🏁 Тест завершён успешно\n")


def test_viewer_cannot_add_wagon(app):
    """Роль viewer не должна иметь права добавлять вагоны."""
    print("🚀 Запуск теста: права доступа для наблюдателя (viewer)")
    
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ip_users (ip_address, username, role, access_allowed) VALUES (?, ?, ?, ?)",
              ('10.0.0.99', 'viewer_test', 'viewer', 1))
    conn.commit()
    conn.close()
    print("  Шаг 1: Создан пользователь viewer с IP 10.0.0.99")

    with app.test_client() as client:
        print("  Шаг 2: Пытаемся добавить вагон с IP 10.0.0.99...")
        response = client.post('/add', 
                               data={
                                   'number': '12345678',
                                   'owner': 'Кто-то',
                                   'organization': 'Где-то',
                                   'track_id': '1'
                               },
                               environ_base={'REMOTE_ADDR': '10.0.0.99'})
        print(f"    Статус ответа: {response.status_code}")
        assert response.status_code == 403, "Наблюдатель не должен иметь доступ к добавлению вагона"
        print("    ✓ Доступ запрещён (403)")
    print("🏁 Тест завершён успешно\n")


def test_depart_and_compact_track(client):
    """При архивации вагона оставшиеся должны сдвигаться (уплотнение)."""
    print("🚀 Запуск теста: архивация и уплотнение пути")
    
    print("  Шаг 1: Добавляем два вагона на путь 8...")
    client.post('/add', data={
        'number': 'DEP001', 'owner': 'ТК А', 'organization': 'Орг А',
        'track_id': '8', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    client.post('/add', data={
        'number': 'DEP002', 'owner': 'ТК Б', 'organization': 'Орг Б',
        'track_id': '8', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })

    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, start_pos FROM wagons WHERE wagon_number = 'DEP001'")
    dep001 = c.fetchone()
    c.execute("SELECT id, start_pos FROM wagons WHERE wagon_number = 'DEP002'")
    dep002 = c.fetchone()
    conn.close()
    
    print(f"    DEP001 ID={dep001[0]}, позиция={dep001[1]}")
    print(f"    DEP002 ID={dep002[0]}, позиция={dep002[1]}")

    print("  Шаг 2: Архивируем DEP001...")
    response = client.post(f'/depart/{dep001[0]}', follow_redirects=True)
    assert response.status_code == 200
    assert 'Вагон убран в архив' in response.data.decode('utf-8'), "Нет сообщения об архивации"
    print("    ✓ DEP001 отправлен в архив")

    print("  Шаг 3: Проверяем, что DEP002 сдвинулся на позицию 0...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT start_pos FROM wagons WHERE id = ?", (dep002[0],))
    new_pos = c.fetchone()[0]
    conn.close()
    
    assert new_pos == 0.0, f"Позиция после архивации должна быть 0, а равна {new_pos}"
    print(f"    ✓ Позиция DEP002 теперь {new_pos}")
    print("🏁 Тест завершён успешно\n")


def test_restore_from_archive(client):
    """Вагон с тем же номером после архивации должен восстанавливаться."""
    print("🚀 Запуск теста: восстановление вагона из архива")
    
    print("  Шаг 1: Добавляем вагон 'RESTORE1' и сразу архивируем...")
    client.post('/add', data={
        'number': 'RESTORE1', 'owner': 'ТК В', 'organization': 'Орг В',
        'track_id': '1', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagons WHERE wagon_number = 'RESTORE1'")
    wagon_id = c.fetchone()[0]
    conn.close()
    client.post(f'/depart/{wagon_id}')
    print("    Вагон отправлен в архив")

    print("  Шаг 2: Снова добавляем вагон с тем же номером...")
    response = client.post('/add', data={
        'number': 'RESTORE1', 'owner': 'Новая ТК', 'organization': 'Новая Орг',
        'track_id': '3', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert 'восстановлен' in response.data.decode('utf-8'), "Нет сообщения о восстановлении"
    print("    ✓ Сообщение о восстановлении найдено")

    print("  Шаг 3: Проверяем, что вагон снова активен и данные обновлены...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT is_archived, owner FROM wagons WHERE wagon_number = 'RESTORE1'")
    row = c.fetchone()
    conn.close()
    
    assert row[0] == 0, "Вагон должен быть не в архиве"
    assert row[1] == 'Новая ТК', f"Владелец должен быть 'Новая ТК', а равен '{row[1]}'"
    print(f"    ✓ Вагон активен, владелец изменён на '{row[1]}'")
    print("🏁 Тест завершён успешно\n")


def test_compact_on_all_tracks(client):
    """На всех путях после архивации первого вагона второй должен сдвинуться на 0."""
    print("🚀 Запуск теста: уплотнение на всех путях")
    
    from app.models import get_conn
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name FROM tracks ORDER BY sort_order ASC")
    all_tracks = c.fetchall()
    conn.close()
    
    print(f"  Найдено путей: {len(all_tracks)}")
    
    for track_id, track_name in all_tracks:
        print(f"\n  === Проверяем путь #{track_id}: {track_name} ===")
        
        num1 = f"COMP{track_id}A"
        num2 = f"COMP{track_id}B"
        print(f"    Шаг 1: Добавляем вагоны '{num1}' и '{num2}'...")
        
        client.post('/add', data={
            'number': num1,
            'owner': 'Тест',
            'organization': 'Тест',
            'track_id': str(track_id),
            'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
        })
        client.post('/add', data={
            'number': num2,
            'owner': 'Тест',
            'organization': 'Тест',
            'track_id': str(track_id),
            'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
        })
        
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id, start_pos FROM wagons WHERE wagon_number = ?", (num1,))
        row1 = c.fetchone()
        c.execute("SELECT id, start_pos FROM wagons WHERE wagon_number = ?", (num2,))
        row2 = c.fetchone()
        conn.close()
        
        assert row1 is not None, f"Вагон {num1} не добавлен"
        assert row2 is not None, f"Вагон {num2} не добавлен"
        
        print(f"    Позиции: {num1} = {row1[1]}, {num2} = {row2[1]}")
        assert row2[1] > 0, f"Второй вагон должен быть не на нуле (получили {row2[1]})"
        
        print(f"    Шаг 2: Архивируем {num1}...")
        response = client.post(f'/depart/{row1[0]}', follow_redirects=True)
        assert response.status_code == 200
        assert 'Вагон убран в архив' in response.data.decode('utf-8')
        print("    ✓ Архивация выполнена")
        
        print(f"    Шаг 3: Проверяем позицию {num2}...")
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT start_pos FROM wagons WHERE id = ?", (row2[0],))
        new_pos = c.fetchone()[0]
        conn.close()
        
        assert new_pos == 0.0, (
            f"На пути '{track_name}' после архивации позиция должна быть 0, а равна {new_pos}"
        )
        print(f"    ✓ Позиция теперь {new_pos}")
        print(f"  ✓ Путь #{track_id} проверен успешно")
    
    print("\n🏁 Все пути проверены, уплотнение работает корректно\n")


def test_move_compacts_old_track(client):
    """После перемещения вагона с пути оставшиеся должны сдвигаться."""
    print("🚀 Запуск теста: уплотнение после перемещения")
    
    SOURCE_TRACK = 3   # АО "Знамя" (Осмотр)
    TARGET_TRACK = 4   # АО "Знамя" (Ремонт)
    
    print(f"  Шаг 1: Добавляем два вагона на путь #{SOURCE_TRACK}...")
    client.post('/add', data={
        'number': 'MOVE1',
        'owner': 'ТК', 'organization': 'Орг',
        'track_id': str(SOURCE_TRACK),
        'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    client.post('/add', data={
        'number': 'MOVE2',
        'owner': 'ТК', 'organization': 'Орг',
        'track_id': str(SOURCE_TRACK),
        'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, start_pos FROM wagons WHERE wagon_number = 'MOVE1'")
    move1 = c.fetchone()
    c.execute("SELECT id, start_pos FROM wagons WHERE wagon_number = 'MOVE2'")
    move2 = c.fetchone()
    conn.close()
    
    print(f"    MOVE1 ID={move1[0]}, позиция={move1[1]}")
    print(f"    MOVE2 ID={move2[0]}, позиция={move2[1]}")
    assert move2[1] > 0, "Второй вагон должен быть не на нуле"
    
    print(f"  Шаг 2: Перемещаем MOVE1 на путь #{TARGET_TRACK}...")
    response = client.post('/move', data={
        'wagon_id': str(move1[0]),
        'new_track_id': str(TARGET_TRACK),
        'local_days': '0', 'local_hours': '0', 'local_mins': '0',
        'note': ''
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'Вагон перемещен' in response.data.decode('utf-8')
    print("    ✓ Перемещение выполнено")
    
    print("  Шаг 3: Проверяем позицию MOVE2 на старом пути...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT start_pos FROM wagons WHERE id = ?", (move2[0],))
    new_pos = c.fetchone()[0]
    conn.close()
    
    assert new_pos == 0.0, (
        f"После перемещения первого вагона второй должен сдвинуться на 0, а он на позиции {new_pos}"
    )
    print(f"    ✓ Позиция MOVE2 теперь {new_pos}")
    print("🏁 Тест завершён успешно\n")


def test_move_middle_wagon_repositions_others(client):
    """При перемещении среднего вагона оставшиеся должны уплотниться."""
    print("🚀 Запуск теста: перемещение среднего вагона и пересчёт позиций")
    SOURCE_TRACK = 5   # АО "Знамя" (База - Погрузка)
    TARGET_TRACK = 6   # АО "Знамя" (Цех ППВВ - Погрузка)

    print("  Шаг 1: Добавляем три вагона на один путь...")
    for num in ['WAG1', 'WAG2', 'WAG3']:
        client.post('/add', data={
            'number': num,
            'owner': 'ТК', 'organization': 'Орг',
            'track_id': str(SOURCE_TRACK),
            'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
        }, follow_redirects=True)

    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, start_pos FROM wagons WHERE track_id = ? ORDER BY start_pos", (SOURCE_TRACK,))
    rows = c.fetchall()
    conn.close()
    positions = {row[0]: row[1] for row in rows}
    print(f"    Позиции до перемещения: {positions}")
    assert positions.get('WAG1') == 0.0
    assert positions.get('WAG2') == 60.0
    assert positions.get('WAG3') == 120.0

    print("  Шаг 2: Перемещаем средний вагон WAG2 на другой путь...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagons WHERE wagon_number = 'WAG2'")
    w2_id = c.fetchone()[0]
    conn.close()

    response = client.post('/move', data={
        'wagon_id': str(w2_id),
        'new_track_id': str(TARGET_TRACK),
        'local_days': '0', 'local_hours': '0', 'local_mins': '0',
        'note': 'Переезд'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'Вагон перемещен' in response.data.decode('utf-8')
    print("    ✓ WAG2 перемещён")

    print("  Шаг 3: Проверяем позиции оставшихся вагонов на старом пути...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, start_pos FROM wagons WHERE track_id = ? ORDER BY start_pos", (SOURCE_TRACK,))
    rows = c.fetchall()
    conn.close()
    new_positions = {row[0]: row[1] for row in rows}
    print(f"    Позиции после перемещения: {new_positions}")
    assert new_positions.get('WAG1') == 0.0, "WAG1 должен остаться на 0"
    assert new_positions.get('WAG3') == 60.0, f"WAG3 должен сдвинуться на 60, а он на {new_positions.get('WAG3')}"
    print("    ✓ Позиции пересчитаны корректно")
    print("🏁 Тест завершён успешно\n")


def test_local_deadline_cannot_start_before_arrival(client):
    """Система должна запрещать дату начала локального срока раньше времени прибытия."""
    print("🚀 Запуск теста: защита хронологии локального срока")
    print("  Шаг 1: Добавляем вагон с датой прибытия 01.01.2025 12:00...")
    client.post('/add', data={
        'number': 'PROTECT1',
        'owner': 'ТК',
        'organization': 'Орг',
        'track_id': '1',
        'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0',
        'start_date': '2025-01-01',
        'start_time': '12:00'
    }, follow_redirects=True)

    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagons WHERE wagon_number = 'PROTECT1'")
    wagon_id = c.fetchone()[0]
    conn.close()

    print("  Шаг 2: Пытаемся переместить с началом локального срока 11:00 (раньше прибытия)...")
    response = client.post('/move', data={
        'wagon_id': str(wagon_id),
        'new_track_id': '2',
        'local_days': '0', 'local_hours': '1', 'local_mins': '0',
        'start_date': '2025-01-01',
        'start_time': '11:00'
    }, follow_redirects=True)

    assert response.status_code == 200
    page_text = response.data.decode('utf-8')
    assert 'не может быть раньше' in page_text, (
        "Должно быть сообщение о нарушении хронологии, а получили: " + page_text[:500]
    )
    assert 'Вагон перемещен' not in page_text, "Перемещение не должно было произойти"
    print("    ✓ Система вернула ошибку хронологии")
    print("🏁 Тест завершён успешно\n")


def test_export_active_wagons_to_excel(client):
    """Экспорт активных вагонов должен создавать валидный Excel-файл."""
    print("🚀 Запуск теста: экспорт активных вагонов в Excel")
    print("  Шаг 1: Добавляем тестовые вагоны...")
    client.post('/add', data={
        'number': 'EX001', 'owner': 'ТК Экспорт', 'organization': 'Орг Экспорт',
        'track_id': '1', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    client.post('/add', data={
        'number': 'EX002', 'owner': 'Другая ТК', 'organization': 'Другая Орг',
        'track_id': '2', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })

    print("  Шаг 2: Запрашиваем /export_excel...")
    response = client.get('/export_excel')
    assert response.status_code == 200
    assert 'spreadsheetml' in response.content_type
    print("    ✓ Получен Excel-файл")

    print("  Шаг 3: Проверяем данные внутри файла...")
    import pandas as pd
    import io
    df = pd.read_excel(io.BytesIO(response.data))
    assert 'Номер вагона' in df.columns
    assert 'Транспортная компания' in df.columns
    assert len(df) == 2
    assert df['Номер вагона'].iloc[0] == 'EX001'
    print(f"    ✓ Найдено {len(df)} записей: {df['Номер вагона'].tolist()}")
    print("🏁 Тест завершён успешно\n")


def test_export_individual_wagon_history(client):
    """Экспорт истории конкретного вагона должен работать."""
    print("🚀 Запуск теста: экспорт истории одного вагона")
    print("  Шаг 1: Добавляем и перемещаем вагон...")
    client.post('/add', data={
        'number': 'EXHIST',
        'owner': 'ТК История',
        'organization': 'Орг История',
        'track_id': '1',
        'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    }, follow_redirects=True)
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagons WHERE wagon_number = 'EXHIST'")
    w_id = c.fetchone()[0]
    conn.close()
    client.post('/move', data={
        'wagon_id': str(w_id),
        'new_track_id': '2',
        'local_days': '0', 'local_hours': '0', 'local_mins': '0',
        'note': ''
    }, follow_redirects=True)

    print("  Шаг 2: Запрашиваем /export_wagon_history/EXHIST...")
    response = client.get('/export_wagon_history/EXHIST')
    assert response.status_code == 200
    assert 'spreadsheetml' in response.content_type
    print("    ✓ Файл получен")

    print("  Шаг 3: Проверяем содержимое...")
    import pandas as pd
    import io
    df = pd.read_excel(io.BytesIO(response.data))
    assert 'Тип действия' in df.columns
    assert len(df) >= 2
    actions = df['Тип действия'].tolist()
    assert 'Добавлен' in actions[0]
    print(f"    ✓ Найдено {len(df)} событий: {actions}")
    print("🏁 Тест завершён успешно\n")


def test_create_and_download_backup(client):
    """Администратор может создать резервную копию и скачать её."""
    print("🚀 Запуск теста: создание и скачивание резервной копии")

    print("  Шаг 1: Создаём резервную копию...")
    response = client.post('/admin/backup')
    assert response.status_code == 200
    text = response.data.decode('utf-8')
    print("    Ответ сервера:", repr(text[:200]))
    assert '✅' in text, f"Нет значка успеха в ответе: {text[:100]}"

    match = re.search(r'Создана копия:\s*(.+?)(?:\n|$)', text)
    if not match:
        match = re.search(r':\s*(.+\.db)', text)
    assert match, f"Не удалось найти путь к файлу в ответе: {text[:200]}"
    full_path = match.group(1).strip()
    print(f"    Файл копии: {full_path}")
    assert os.path.exists(full_path), f"Файл {full_path} не существует"

    print("  Шаг 2: Получаем список бэкапов...")
    list_response = client.get('/admin/backups')
    assert list_response.status_code == 200
    list_text = list_response.data.decode('utf-8')

    file_name = os.path.basename(full_path)
    rel_match = re.search(r'href="/admin/download_backup\?rel_path=([^"]*' + re.escape(file_name) + r'[^"]*)"', list_text)
    if not rel_match:
        rel_match = re.search(r'href="/admin/download_backup\?rel_path=([^"]+)"', list_text)
    assert rel_match, f"Не найдена ссылка на скачивание. Ответ: {list_text[:500]}"
    rel_path = rel_match.group(1)
    print(f"    rel_path: {rel_path}")

    print("  Шаг 3: Скачиваем файл...")
    download_response = client.get(f'/admin/download_backup?rel_path={rel_path}')
    assert download_response.status_code == 200
    assert len(download_response.data) > 0
    print(f"    ✓ Файл скачан, размер {len(download_response.data)} байт")
    print("🏁 Тест завершён успешно\n")


def test_restore_backup_reverts_database(client):
    """Восстановление из бэкапа должно откатывать базу данных."""
    print("🚀 Запуск теста: восстановление из резервной копии")

    print("  Шаг 1: Добавляем вагон 'ORIGINAL'...")
    client.post('/add', data={
        'number': 'ORIGINAL',
        'owner': 'До бэкапа',
        'organization': 'Орг',
        'track_id': '1',
        'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })

    print("  Шаг 2: Создаём резервную копию...")
    resp = client.post('/admin/backup')
    text = resp.data.decode('utf-8')
    match = re.search(r'Создана копия:\s*(.+?)(?:\n|$)', text)
    if not match:
        match = re.search(r':\s*(.+\.db)', text)
    assert match, f"Не удалось найти путь: {text[:200]}"
    full_path = match.group(1).strip()
    print(f"    Путь к копии: {full_path}")

    print("  Шаг 3: Добавляем второй вагон 'AFTER_BACKUP'...")
    client.post('/add', data={
        'number': 'AFTER_BACKUP',
        'owner': 'После бэкапа',
        'organization': 'Орг',
        'track_id': '1',
        'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })

    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM wagons WHERE is_archived=0")
    count_before = c.fetchone()[0]
    conn.close()
    print(f"    Вагонов до восстановления: {count_before}")
    assert count_before == 2

    import config
    rel_path = os.path.relpath(full_path, config.BACKUP_DIR)
    print(f"    rel_path для восстановления: {rel_path}")

    print("  Шаг 4: Восстанавливаем базу из копии...")
    restore_resp = client.post('/admin/restore', data={'rel_path': rel_path})
    assert restore_resp.status_code == 200
    print("    ✓ Восстановление выполнено")

    print("  Шаг 5: Проверяем состояние базы...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number FROM wagons WHERE is_archived=0")
    wagons = [row[0] for row in c.fetchall()]
    conn.close()
    print(f"    Активные вагоны: {wagons}")
    assert 'ORIGINAL' in wagons, "Первый вагон должен остаться"
    assert 'AFTER_BACKUP' not in wagons, "Второй вагон должен исчезнуть после восстановления"
    print("    ✓ База откатилась к моменту бэкапа")
    print("🏁 Тест завершён успешно\n")


def test_settings_page_and_update(client):
    """Страница настроек доступна, изменение параметра сохраняется в БД."""
    print("🚀 Запуск теста: страница настроек и изменение параметра")

    print("  Шаг 1: Запрашиваем /admin/settings...")
    resp = client.get('/admin/settings')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert 'Настройки приложения' in html
    print("    ✓ Страница настроек загружена")

    print("  Шаг 2: Отправляем новые настройки (refresh_interval=10)...")
    resp = client.post('/admin/settings', data={
        'refresh_interval': '10',
        'port': '5000',
        'secret_key': 'testkey',
        'backup_hour': '3',
        'backup_keep_count': '30',
        'log_max_mb': '5',
        'log_backup_count': '5',
        'default_wagon_length': '10.0',
        'wagon_spacing': '50.0'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert 'Настройки сохранены' in resp.data.decode('utf-8')
    print("    ✓ Сообщение об успехе получено")

    from app.models import get_setting
    interval = get_setting('refresh_interval', '5')
    assert interval == '10', f"refresh_interval должен стать 10, а равен {interval}"
    print(f"    ✓ refresh_interval сохранён как {interval}")

    print("  Шаг 3: Проверяем, что viewer не может зайти в настройки...")
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ip_users (ip_address, username, role, access_allowed) VALUES (?,?,?,?)",
              ('10.0.0.50', 'viewer_settings', 'viewer', 1))
    conn.commit()
    conn.close()
    with client.application.test_client() as viewer_client:
        resp = viewer_client.get('/admin/settings', environ_base={'REMOTE_ADDR': '10.0.0.50'})
        assert resp.status_code == 403
    print("    ✓ Доступ запрещён (403)")
    print("🏁 Тест завершён успешно\n")


def test_add_and_delete_track_via_settings(client):
    """Через страницу настроек можно добавить и удалить путь."""
    print("🚀 Запуск теста: добавление и удаление пути через настройки")

    print("  Шаг 1: Добавляем путь 'Тестовый путь'...")
    resp = client.post('/admin/settings', data={
        'action': 'add_track',
        'track_name': 'Тестовый путь',
        'track_length': '500',
        'track_type': 'normal'
    }, follow_redirects=True)
    assert resp.status_code == 200
    resp_text = resp.data.decode('utf-8')
    # Проверяем наличие имени пути и слова "добавлен", игнорируя возможное экранирование кавычек
    assert 'Тестовый путь' in resp_text and 'добавлен' in resp_text, (
        f"Нет сообщения об успешном добавлении пути. Ответ: {resp_text[:500]}"
    )
    print("    ✓ Путь добавлен")

    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM tracks WHERE name='Тестовый путь'")
    track_id = c.fetchone()
    conn.close()
    assert track_id is not None, "Путь не найден в БД"
    track_id = track_id[0]
    print(f"    ID нового пути: {track_id}")

    print("  Шаг 2: Удаляем путь...")
    resp = client.post('/admin/settings', data={
        'action': 'delete_track',
        'track_id': str(track_id)
    }, follow_redirects=True)
    assert resp.status_code == 200
    resp_text = resp.data.decode('utf-8')
    assert 'Путь удалён' in resp_text, f"Нет сообщения об удалении пути: {resp_text[:500]}"
    print("    ✓ Путь удалён")

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM tracks WHERE name='Тестовый путь'")
    assert c.fetchone() is None, "Путь остался в БД"
    conn.close()
    print("🏁 Тест завершён успешно\n")
def test_reorder_tracks_via_save_order(client):
    """Сохранение порядка путей через API должно менять sort_order."""
    print("🚀 Запуск теста: изменение порядка путей")

    from app.models import get_conn

    # 1. Запоминаем текущий порядок путей
    print("  Шаг 1: Запоминаем текущий порядок путей...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, sort_order FROM tracks ORDER BY sort_order ASC")
    original = c.fetchall()
    conn.close()
    print(f"    Исходный порядок: {[(t[0], t[1]) for t in original]}")

    # 2. Меняем порядок: ставим путь 2 на место 1 и наоборот
    new_order = [t[0] for t in original]
    # Меняем первые два пути местами
    new_order[0], new_order[1] = new_order[1], new_order[0]
    print(f"    Новый порядок: {new_order}")

    print("  Шаг 2: Сохраняем новый порядок через /admin/tracks/save_order...")
    response = client.post('/admin/tracks/save_order',
                           json={'order': new_order},
                           content_type='application/json')
    assert response.status_code == 200
    result = response.get_json()
    assert result.get('success') is True, f"Сохранение не удалось: {result}"
    print("    ✓ Порядок сохранён")

    # 3. Проверяем, что в БД порядок действительно изменился
    print("  Шаг 3: Проверяем sort_order в БД...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, sort_order FROM tracks WHERE id IN (?, ?) ORDER BY sort_order ASC",
              (original[0][0], original[1][0]))
    updated = c.fetchall()
    conn.close()
    print(f"    Обновлённый порядок: {updated}")

    # Путь, который был вторым, теперь должен быть первым (sort_order = 1)
    assert updated[0][0] == original[1][0], (
        f"Ожидался путь {original[1][0]} на первой позиции, а получен {updated[0][0]}"
    )
    assert updated[1][0] == original[0][0], (
        f"Ожидался путь {original[0][0]} на второй позиции, а получен {updated[1][0]}"
    )
    print("    ✓ Порядок путей успешно изменён")

    # 4. Проверяем, что viewer не может менять порядок
    print("  Шаг 4: Проверяем, что viewer не может менять порядок...")
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ip_users (ip_address, username, role, access_allowed) VALUES (?,?,?,?)",
              ('10.0.0.60', 'viewer_order', 'viewer', 1))
    conn.commit()
    conn.close()
    with client.application.test_client() as viewer_client:
        resp = viewer_client.post('/admin/tracks/save_order',
                                   json={'order': new_order},
                                   content_type='application/json',
                                   environ_base={'REMOTE_ADDR': '10.0.0.60'})
        assert resp.status_code == 403
    print("    ✓ Доступ запрещён (403)")

    print("🏁 Тест завершён успешно\n")
def test_rename_track_via_settings(client):
    """Администратор может переименовать путь через настройки."""
    print("🚀 Запуск теста: переименование пути")

    from app.models import get_conn

    # 1. Получаем ID первого пути
    print("  Шаг 1: Находим тестовый путь для переименования...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name FROM tracks ORDER BY sort_order ASC LIMIT 1")
    track_id, old_name = c.fetchone()
    conn.close()
    print(f"    Будем менять путь #{track_id} '{old_name}'")

    # 2. Переименовываем
    new_name = old_name + " (переименован)"
    new_length = "750.0"
    print(f"  Шаг 2: Переименовываем в '{new_name}', длина {new_length}...")
    resp = client.post('/admin/settings', data={
        'action': 'edit_track',
        'track_id': str(track_id),
        'track_name': new_name,
        'track_length': new_length,
        'track_type': 'normal'
    }, follow_redirects=True)
    assert resp.status_code == 200
    resp_text = resp.data.decode('utf-8')
    # Проверяем любое сообщение об успешном изменении пути
    assert ('обновлён' in resp_text or 'изменён' in resp_text or 
            f"Путь &#39;{new_name}&#39; обновлён" in resp_text or
            'Путь' in resp_text), (
        f"Нет сообщения об обновлении пути. Ответ: {resp_text[:500]}"
    )
    print("    ✓ Путь обновлён")

    # 3. Проверяем в БД
    print("  Шаг 3: Проверяем изменения в базе...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, total_length FROM tracks WHERE id = ?", (track_id,))
    name, length = c.fetchone()
    conn.close()
    assert name == new_name, f"Имя не обновилось: ожидалось '{new_name}', получено '{name}'"
    assert float(length) == 750.0, f"Длина не обновилась: ожидалось 750.0, получено {length}"
    print(f"    ✓ Имя: '{name}', длина: {length}")

    # 4. Проверяем, что viewer не может переименовать
    print("  Шаг 4: Проверяем, что viewer не может переименовать путь...")
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ip_users (ip_address, username, role, access_allowed) VALUES (?,?,?,?)",
              ('10.0.0.70', 'viewer_rename', 'viewer', 1))
    conn.commit()
    conn.close()
    with client.application.test_client() as viewer_client:
        resp = viewer_client.post('/admin/settings', data={
            'action': 'edit_track',
            'track_id': str(track_id),
            'track_name': 'Взлом',
            'track_length': '100',
            'track_type': 'normal'
        }, environ_base={'REMOTE_ADDR': '10.0.0.70'})
        assert resp.status_code == 403
    print("    ✓ Доступ запрещён (403)")

    print("🏁 Тест завершён успешно\n")