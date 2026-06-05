# tests/test_scenarios.py
import os
import sys
import tempfile
import re
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture(scope='function')
def app():
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

    import importlib
    for mod in ['app.models', 'app.utils', 'app.routes.main',
                'app.routes.admin', 'app.routes.api', 'app.routes.export',
                'app.routes.history', 'app']:
        if mod in sys.modules:
            del sys.modules[mod]

    from app import create_app
    flask_app = create_app()
    flask_app.config['TESTING'] = True

    @flask_app.before_request
    def fake_auth():
        from flask import request, g
        request.user_role = 'admin'
        g.station_id = int(request.args.get('station_id', 1))

    yield flask_app

    try:
        os.unlink(temp_db_path)
    except PermissionError:
        pass
    import shutil
    shutil.rmtree(temp_backup_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    return app.test_client()


def test_add_wagon_success(client):
    print("🚀 Запуск теста: добавление нового вагона")
    print("  Шаг 1: Отправляем данные нового вагона '12345678'...")
    response = client.post('/add?station_id=1', data={
        'number': '12345678', 'owner': 'ОАО РЖД', 'organization': 'Завод',
        'note': 'Уголь', 'track_id': '1',
        'cycle_days': '1', 'cycle_hours': '2', 'cycle_mins': '30'
    })
    print("    Статус ответа:", response.status_code)
    assert response.status_code == 302, "Сервер не отправил редирект – вагон, возможно, не добавлен"
    redirect_response = client.get(response.headers['Location'])
    assert redirect_response.status_code == 200
    page_text = redirect_response.data.decode('utf-8')
    assert 'Вагон 12345678 добавлен' in page_text
    print("    ✓ Сообщение об успехе найдено")
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM wagon_visits WHERE wagon_number = '12345678' AND station_id = 1")
    row = c.fetchone()
    conn.close()
    assert row is not None, "Вагон не найден в БД"
    assert row[9] == 'ОАО РЖД'
    assert row[6] == 1
    print("    ✓ Вагон успешно записан в базу")
    print("🏁 Тест завершён успешно\n")


def test_move_wagon_and_local_deadline(client):
    print("🚀 Запуск теста: перемещение вагона и локальный срок")
    client.post('/add?station_id=1', data={
        'number': '99999999', 'owner': 'ТК Тест', 'organization': 'Организация',
        'note': '', 'track_id': '1', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    }, follow_redirects=True)
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagon_visits WHERE wagon_number = '99999999' AND station_id = 1")
    wagon_id = c.fetchone()[0]
    conn.close()
    print(f"    Вагон добавлен, его ID = {wagon_id}")
    response = client.post('/move?station_id=1', data={
        'wagon_id': str(wagon_id), 'new_track_id': '3',
        'local_days': '0', 'local_hours': '1', 'local_mins': '30',
        'note': 'Ремонт'
    })
    assert response.status_code == 302
    redirect_response = client.get(response.headers['Location'])
    assert 'Вагон перемещен' in redirect_response.data.decode('utf-8')
    print("    ✓ Сообщение 'Вагон перемещен' найдено")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT track_id, local_departure_time, visit_count FROM wagon_visits WHERE id = ?", (wagon_id,))
    row = c.fetchone()
    conn.close()
    assert row[0] == 3
    assert row[1] is not None
    assert row[2] == 1
    print(f"    ✓ Путь изменён на 3, локальный срок установлен ({row[1]}), счётчик = 1")
    print("🏁 Тест завершён успешно\n")


def test_viewer_cannot_add_wagon(app):
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
        response = client.post('/add?station_id=1', data={
            'number': '12345678', 'owner': 'Кто-то', 'organization': 'Где-то', 'track_id': '1'
        }, environ_base={'REMOTE_ADDR': '10.0.0.99'})
        print(f"    Статус ответа: {response.status_code}")
        assert response.status_code == 403
        print("    ✓ Доступ запрещён (403)")
    print("🏁 Тест завершён успешно\n")


def test_depart_and_compact_track(client):
    print("🚀 Запуск теста: архивация и уплотнение пути")
    client.post('/add?station_id=1', data={
        'number': 'DEP001', 'owner': 'ТК А', 'organization': 'Орг А',
        'track_id': '8', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    client.post('/add?station_id=1', data={
        'number': 'DEP002', 'owner': 'ТК Б', 'organization': 'Орг Б',
        'track_id': '8', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, start_pos FROM wagon_visits WHERE wagon_number = 'DEP001' AND station_id = 1")
    dep001 = c.fetchone()
    c.execute("SELECT id, start_pos FROM wagon_visits WHERE wagon_number = 'DEP002' AND station_id = 1")
    dep002 = c.fetchone()
    conn.close()
    print(f"    DEP001 ID={dep001[0]}, позиция={dep001[1]}")
    print(f"    DEP002 ID={dep002[0]}, позиция={dep002[1]}")
    response = client.post(f'/depart/{dep001[0]}?station_id=1', follow_redirects=True)
    assert response.status_code == 200
    assert 'Вагон убран в архив' in response.data.decode('utf-8')
    print("    ✓ DEP001 отправлен в архив")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT start_pos FROM wagon_visits WHERE id = ?", (dep002[0],))
    new_pos = c.fetchone()[0]
    conn.close()
    assert new_pos == 0.0, f"Позиция после архивации должна быть 0, а равна {new_pos}"
    print(f"    ✓ Позиция DEP002 теперь {new_pos}")
    print("🏁 Тест завершён успешно\n")


def test_restore_from_archive(client):
    print("🚀 Запуск теста: восстановление вагона из архива")
    client.post('/add?station_id=1', data={
        'number': 'RESTORE1', 'owner': 'ТК В', 'organization': 'Орг В',
        'track_id': '1', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagon_visits WHERE wagon_number = 'RESTORE1' AND station_id = 1")
    wagon_id = c.fetchone()[0]
    conn.close()
    client.post(f'/depart/{wagon_id}?station_id=1')
    print("    Вагон отправлен в архив")
    response = client.post('/add?station_id=1', data={
        'number': 'RESTORE1', 'owner': 'Новая ТК', 'organization': 'Новая Орг',
        'track_id': '3', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'добавлен' in response.data.decode('utf-8')
    print("    ✓ Вагон добавлен как новый визит")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM wagon_visits WHERE wagon_number = 'RESTORE1' AND station_id = 1")
    count = c.fetchone()[0]
    conn.close()
    assert count == 2, f"Должно быть 2 визита, а найдено {count}"
    print(f"    ✓ Найдено {count} визита")
    print("🏁 Тест завершён успешно\n")


def test_compact_on_all_tracks(client):
    print("🚀 Запуск теста: уплотнение на всех путях")
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name FROM tracks WHERE station_id = 1 ORDER BY sort_order ASC")
    all_tracks = c.fetchall()
    conn.close()
    print(f"  Найдено путей: {len(all_tracks)}")
    for track_id, track_name in all_tracks:
        print(f"\n  === Проверяем путь #{track_id}: {track_name} ===")
        num1 = f"COMP{track_id}A"
        num2 = f"COMP{track_id}B"
        print(f"    Шаг 1: Добавляем вагоны '{num1}' и '{num2}'...")
        client.post('/add?station_id=1', data={
            'number': num1, 'owner': 'Тест', 'organization': 'Тест',
            'track_id': str(track_id), 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
        })
        client.post('/add?station_id=1', data={
            'number': num2, 'owner': 'Тест', 'organization': 'Тест',
            'track_id': str(track_id), 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
        })
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id, start_pos FROM wagon_visits WHERE wagon_number = ? AND station_id = 1", (num1,))
        row1 = c.fetchone()
        c.execute("SELECT id, start_pos FROM wagon_visits WHERE wagon_number = ? AND station_id = 1", (num2,))
        row2 = c.fetchone()
        conn.close()
        assert row1 is not None, f"Вагон {num1} не добавлен"
        assert row2 is not None, f"Вагон {num2} не добавлен"
        print(f"    Позиции: {num1} = {row1[1]}, {num2} = {row2[1]}")
        assert row2[1] > 0, f"Второй вагон должен быть не на нуле (получили {row2[1]})"
        print(f"    Шаг 2: Архивируем {num1}...")
        response = client.post(f'/depart/{row1[0]}?station_id=1', follow_redirects=True)
        assert response.status_code == 200
        assert 'Вагон убран в архив' in response.data.decode('utf-8')
        print("    ✓ Архивация выполнена")
        print(f"    Шаг 3: Проверяем позицию {num2}...")
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT start_pos FROM wagon_visits WHERE id = ?", (row2[0],))
        new_pos = c.fetchone()[0]
        conn.close()
        assert new_pos == 0.0, f"На пути '{track_name}' после архивации позиция должна быть 0, а равна {new_pos}"
        print(f"    ✓ Позиция теперь {new_pos}")
        print(f"  ✓ Путь #{track_id} проверен успешно")
    print("\n🏁 Все пути проверены, уплотнение работает корректно\n")


def test_move_compacts_old_track(client):
    print("🚀 Запуск теста: уплотнение после перемещения")
    SOURCE_TRACK = 3
    TARGET_TRACK = 4
    client.post('/add?station_id=1', data={
        'number': 'MOVE1', 'owner': 'ТК', 'organization': 'Орг',
        'track_id': str(SOURCE_TRACK), 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    client.post('/add?station_id=1', data={
        'number': 'MOVE2', 'owner': 'ТК', 'organization': 'Орг',
        'track_id': str(SOURCE_TRACK), 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, start_pos FROM wagon_visits WHERE wagon_number = 'MOVE1' AND station_id = 1")
    move1 = c.fetchone()
    c.execute("SELECT id, start_pos FROM wagon_visits WHERE wagon_number = 'MOVE2' AND station_id = 1")
    move2 = c.fetchone()
    conn.close()
    print(f"    MOVE1 ID={move1[0]}, позиция={move1[1]}")
    print(f"    MOVE2 ID={move2[0]}, позиция={move2[1]}")
    assert move2[1] > 0, "Второй вагон должен быть не на нуле"
    response = client.post('/move?station_id=1', data={
        'wagon_id': str(move1[0]), 'new_track_id': str(TARGET_TRACK),
        'local_days': '0', 'local_hours': '0', 'local_mins': '0', 'note': ''
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'Вагон перемещен' in response.data.decode('utf-8')
    print("    ✓ Перемещение выполнено")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT start_pos FROM wagon_visits WHERE id = ?", (move2[0],))
    new_pos = c.fetchone()[0]
    conn.close()
    assert new_pos == 0.0, f"После перемещения первого вагона второй должен сдвинуться на 0, а он на позиции {new_pos}"
    print(f"    ✓ Позиция MOVE2 теперь {new_pos}")
    print("🏁 Тест завершён успешно\n")


def test_move_middle_wagon_repositions_others(client):
    print("🚀 Запуск теста: перемещение среднего вагона и пересчёт позиций")
    SOURCE_TRACK = 5
    TARGET_TRACK = 6
    for num in ['WAG1', 'WAG2', 'WAG3']:
        client.post('/add?station_id=1', data={
            'number': num, 'owner': 'ТК', 'organization': 'Орг',
            'track_id': str(SOURCE_TRACK), 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
        }, follow_redirects=True)
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, start_pos FROM wagon_visits WHERE track_id = ? AND station_id = 1 ORDER BY start_pos", (SOURCE_TRACK,))
    rows = c.fetchall()
    conn.close()
    positions = {row[0]: row[1] for row in rows}
    print(f"    Позиции до перемещения: {positions}")
    assert positions.get('WAG1') == 0.0
    assert positions.get('WAG2') == 60.0
    assert positions.get('WAG3') == 120.0
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagon_visits WHERE wagon_number = 'WAG2' AND station_id = 1")
    w2_id = c.fetchone()[0]
    conn.close()
    response = client.post('/move?station_id=1', data={
        'wagon_id': str(w2_id), 'new_track_id': str(TARGET_TRACK),
        'local_days': '0', 'local_hours': '0', 'local_mins': '0', 'note': 'Переезд'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'Вагон перемещен' in response.data.decode('utf-8')
    print("    ✓ WAG2 перемещён")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, start_pos FROM wagon_visits WHERE track_id = ? AND station_id = 1 ORDER BY start_pos", (SOURCE_TRACK,))
    rows = c.fetchall()
    conn.close()
    new_positions = {row[0]: row[1] for row in rows}
    print(f"    Позиции после перемещения: {new_positions}")
    assert new_positions.get('WAG1') == 0.0, "WAG1 должен остаться на 0"
    assert new_positions.get('WAG3') == 60.0, f"WAG3 должен сдвинуться на 60, а он на {new_positions.get('WAG3')}"
    print("    ✓ Позиции пересчитаны корректно")
    print("🏁 Тест завершён успешно\n")


def test_local_deadline_cannot_start_before_arrival(client):
    print("🚀 Запуск теста: защита хронологии локального срока")
    client.post('/add?station_id=1', data={
        'number': 'PROTECT1', 'owner': 'ТК', 'organization': 'Орг',
        'track_id': '1', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0',
        'start_date': '2025-01-01', 'start_time': '12:00'
    }, follow_redirects=True)
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagon_visits WHERE wagon_number = 'PROTECT1' AND station_id = 1")
    wagon_id = c.fetchone()[0]
    conn.close()
    response = client.post('/move?station_id=1', data={
        'wagon_id': str(wagon_id), 'new_track_id': '2',
        'local_days': '0', 'local_hours': '1', 'local_mins': '0',
        'start_date': '2025-01-01', 'start_time': '11:00'
    }, follow_redirects=True)
    assert response.status_code == 200
    page_text = response.data.decode('utf-8')
    assert 'не может быть раньше' in page_text
    assert 'Вагон перемещен' not in page_text
    print("    ✓ Система вернула ошибку хронологии")
    print("🏁 Тест завершён успешно\n")


def test_export_active_wagons_to_excel(client):
    print("🚀 Запуск теста: экспорт активных вагонов в Excel")
    client.post('/add?station_id=1', data={
        'number': 'EX001', 'owner': 'ТК Экспорт', 'organization': 'Орг Экспорт',
        'track_id': '1', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    client.post('/add?station_id=1', data={
        'number': 'EX002', 'owner': 'Другая ТК', 'organization': 'Другая Орг',
        'track_id': '2', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    response = client.get('/export_excel?station_id=1')
    assert response.status_code == 200
    assert 'spreadsheetml' in response.content_type
    print("    ✓ Получен Excel-файл")
    import pandas as pd
    import io
    df = pd.read_excel(io.BytesIO(response.data))
    assert 'Номер вагона' in df.columns
    assert len(df) == 2
    assert df['Номер вагона'].iloc[0] == 'EX001'
    print(f"    ✓ Найдено {len(df)} записей: {df['Номер вагона'].tolist()}")
    print("🏁 Тест завершён успешно\n")


def test_export_individual_wagon_history(client):
    print("🚀 Запуск теста: экспорт истории одного вагона")
    client.post('/add?station_id=1', data={
        'number': 'EXHIST', 'owner': 'ТК История', 'organization': 'Орг История',
        'track_id': '1', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    }, follow_redirects=True)
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM wagon_visits WHERE wagon_number = 'EXHIST' AND station_id = 1")
    w_id = c.fetchone()[0]
    conn.close()
    client.post('/move?station_id=1', data={
        'wagon_id': str(w_id), 'new_track_id': '2',
        'local_days': '0', 'local_hours': '0', 'local_mins': '0', 'note': ''
    }, follow_redirects=True)
    response = client.get('/export_wagon_history/EXHIST?station_id=1')
    assert response.status_code == 200
    assert 'spreadsheetml' in response.content_type
    print("    ✓ Файл получен")
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
    print("🚀 Запуск теста: создание и скачивание резервной копии")
    response = client.post('/admin/backup?station_id=1')
    assert response.status_code == 200
    text = response.data.decode('utf-8')
    print("    Ответ сервера:", repr(text[:200]))
    assert '✅' in text
    match = re.search(r'Создана копия:\s*(.+?)(?:\n|$)', text)
    if not match:
        match = re.search(r':\s*(.+\.db)', text)
    assert match, f"Не удалось найти путь к файлу в ответе: {text[:200]}"
    full_path = match.group(1).strip()
    print(f"    Файл копии: {full_path}")
    assert os.path.exists(full_path)
    list_response = client.get('/admin/backups?station_id=1')
    assert list_response.status_code == 200
    list_text = list_response.data.decode('utf-8')
    file_name = os.path.basename(full_path)
    rel_match = re.search(r'href="/admin/download_backup\?rel_path=([^"]*' + re.escape(file_name) + r'[^"]*)"', list_text)
    if not rel_match:
        rel_match = re.search(r'href="/admin/download_backup\?rel_path=([^"]+)"', list_text)
    assert rel_match, f"Не найдена ссылка на скачивание. Ответ: {list_text[:500]}"
    rel_path = rel_match.group(1)
    print(f"    rel_path: {rel_path}")
    download_response = client.get(f'/admin/download_backup?rel_path={rel_path}&station_id=1')
    assert download_response.status_code == 200
    assert len(download_response.data) > 0
    print(f"    ✓ Файл скачан, размер {len(download_response.data)} байт")
    print("🏁 Тест завершён успешно\n")


def test_restore_backup_reverts_database(client):
    print("🚀 Запуск теста: восстановление из резервной копии")
    client.post('/add?station_id=1', data={
        'number': 'ORIGINAL', 'owner': 'До бэкапа', 'organization': 'Орг',
        'track_id': '1', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    resp = client.post('/admin/backup?station_id=1')
    text = resp.data.decode('utf-8')
    match = re.search(r'Создана копия:\s*(.+?)(?:\n|$)', text)
    if not match:
        match = re.search(r':\s*(.+\.db)', text)
    assert match, f"Не удалось найти путь: {text[:200]}"
    full_path = match.group(1).strip()
    print(f"    Путь к копии: {full_path}")
    client.post('/add?station_id=1', data={
        'number': 'AFTER_BACKUP', 'owner': 'После бэкапа', 'organization': 'Орг',
        'track_id': '1', 'cycle_days': '0', 'cycle_hours': '0', 'cycle_mins': '0'
    })
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM wagon_visits WHERE is_archived=0 AND station_id=1")
    count_before = c.fetchone()[0]
    conn.close()
    print(f"    Вагонов до восстановления: {count_before}")
    assert count_before == 2
    import config
    rel_path = os.path.relpath(full_path, config.BACKUP_DIR)
    print(f"    rel_path для восстановления: {rel_path}")
    restore_resp = client.post('/admin/restore?station_id=1', data={'rel_path': rel_path})
    assert restore_resp.status_code == 200
    print("    ✓ Восстановление выполнено")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number FROM wagon_visits WHERE is_archived=0 AND station_id=1")
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
    resp = client.get('/admin/settings?station_id=1')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert 'Настройки приложения' in html
    print("    ✓ Страница настроек загружена")

    print("  Шаг 2: Отправляем новые настройки (refresh_interval=10)...")
    resp = client.post('/admin/settings?station_id=1', data={
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
    # Теперь get_setting принимает station_id, передаём 1
    interval = get_setting('refresh_interval', '5', station_id=1)
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
        resp = viewer_client.get('/admin/settings?station_id=1', environ_base={'REMOTE_ADDR': '10.0.0.50'})
        assert resp.status_code == 403
    print("    ✓ Доступ запрещён (403)")
    print("🏁 Тест завершён успешно\n")


def test_add_and_delete_track_via_settings(client):
    print("🚀 Запуск теста: добавление и удаление пути через настройки")
    resp = client.post('/admin/settings?station_id=1', data={
        'action': 'add_track', 'track_name': 'Тестовый путь',
        'track_length': '500', 'track_type': 'normal'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert 'Тестовый путь' in resp.data.decode('utf-8') and 'добавлен' in resp.data.decode('utf-8')
    print("    ✓ Путь добавлен")
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM tracks WHERE name='Тестовый путь' AND station_id=1")
    track_id = c.fetchone()
    conn.close()
    assert track_id is not None, "Путь не найден в БД"
    track_id = track_id[0]
    print(f"    ID нового пути: {track_id}")
    resp = client.post('/admin/settings?station_id=1', data={
        'action': 'delete_track', 'track_id': str(track_id)
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert 'Путь удалён' in resp.data.decode('utf-8')
    print("    ✓ Путь удалён")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM tracks WHERE name='Тестовый путь' AND station_id=1")
    assert c.fetchone() is None, "Путь остался в БД"
    conn.close()
    print("🏁 Тест завершён успешно\n")


def test_reorder_tracks_via_save_order(client):
    print("🚀 Запуск теста: изменение порядка путей")
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, sort_order FROM tracks WHERE station_id=1 ORDER BY sort_order ASC")
    original = c.fetchall()
    conn.close()
    print(f"    Исходный порядок: {[(t[0], t[1]) for t in original]}")
    new_order = [t[0] for t in original]
    new_order[0], new_order[1] = new_order[1], new_order[0]
    print(f"    Новый порядок: {new_order}")
    response = client.post('/admin/tracks/save_order?station_id=1',
                           json={'order': new_order},
                           content_type='application/json')
    assert response.status_code == 200
    result = response.get_json()
    assert result.get('success') is True, f"Сохранение не удалось: {result}"
    print("    ✓ Порядок сохранён")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, sort_order FROM tracks WHERE id IN (?, ?) AND station_id=1 ORDER BY sort_order ASC",
              (original[0][0], original[1][0]))
    updated = c.fetchall()
    conn.close()
    print(f"    Обновлённый порядок: {updated}")
    assert updated[0][0] == original[1][0]
    assert updated[1][0] == original[0][0]
    print("    ✓ Порядок путей успешно изменён")
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ip_users (ip_address, username, role, access_allowed) VALUES (?,?,?,?)",
              ('10.0.0.60', 'viewer_order', 'viewer', 1))
    conn.commit()
    conn.close()
    with client.application.test_client() as viewer_client:
        resp = viewer_client.post('/admin/tracks/save_order?station_id=1',
                                   json={'order': new_order},
                                   content_type='application/json',
                                   environ_base={'REMOTE_ADDR': '10.0.0.60'})
        assert resp.status_code == 403
    print("    ✓ Доступ запрещён (403)")
    print("🏁 Тест завершён успешно\n")


def test_rename_track_via_settings(client):
    print("🚀 Запуск теста: переименование пути")
    from app.models import get_conn
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name FROM tracks WHERE station_id=1 ORDER BY sort_order ASC LIMIT 1")
    track_id, old_name = c.fetchone()
    conn.close()
    print(f"    Будем менять путь #{track_id} '{old_name}'")
    new_name = old_name + " (переименован)"
    new_length = "750.0"
    resp = client.post('/admin/settings?station_id=1', data={
        'action': 'edit_track', 'track_id': str(track_id),
        'track_name': new_name, 'track_length': new_length, 'track_type': 'normal'
    }, follow_redirects=True)
    assert resp.status_code == 200
    resp_text = resp.data.decode('utf-8')
    assert (new_name in resp_text or 'обновлён' in resp_text or 'изменён' in resp_text or 'Путь' in resp_text)
    print("    ✓ Путь обновлён")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, total_length FROM tracks WHERE id = ?", (track_id,))
    name, length = c.fetchone()
    conn.close()
    assert name == new_name, f"Имя не обновилось: ожидалось '{new_name}', получено '{name}'"
    assert float(length) == 750.0, f"Длина не обновилась: ожидалось 750.0, получено {length}"
    print(f"    ✓ Имя: '{name}', длина: {length}")
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ip_users (ip_address, username, role, access_allowed) VALUES (?,?,?,?)",
              ('10.0.0.70', 'viewer_rename', 'viewer', 1))
    conn.commit()
    conn.close()
    with client.application.test_client() as viewer_client:
        resp = viewer_client.post('/admin/settings?station_id=1', data={
            'action': 'edit_track', 'track_id': str(track_id),
            'track_name': 'Взлом', 'track_length': '100', 'track_type': 'normal'
        }, environ_base={'REMOTE_ADDR': '10.0.0.70'})
        assert resp.status_code == 403
    print("    ✓ Доступ запрещён (403)")
    print("🏁 Тест завершён успешно\n")