# app/models.py
# -*- coding: utf-8 -*-
"""
Модели данных и функции работы с базой данных.
"""

import os
import glob
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_NAME, BACKUP_DIR, CHANGELOG_PATH
from app.utils import (
    get_conn, is_return_track, clean_note_for_db, log_action, format_date
)


# ==================== ИНИЦИАЛИЗАЦИЯ БД ====================
def init_db():
    """Создаёт таблицы, если их нет, и заполняет начальными данными."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL")
    
    c.execute('''CREATE TABLE IF NOT EXISTS movement_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wagon_number TEXT, action_type TEXT, from_track TEXT, to_track TEXT, note TEXT, timestamp TEXT
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS archived_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wagon_number TEXT, action_type TEXT, from_track TEXT, to_track TEXT, note TEXT, timestamp TEXT, archived_date TEXT,
                    visit_id INTEGER DEFAULT NULL
                )''')
    # Добавляем поле visit_id, если его нет
    try:
        c.execute("ALTER TABLE archived_history ADD COLUMN visit_id INTEGER DEFAULT NULL")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE,
                    total_length REAL,
                    track_type TEXT DEFAULT 'normal',
                    sort_order INTEGER DEFAULT 0
                )''')
    
    try:
        c.execute("ALTER TABLE tracks ADD COLUMN sort_order INTEGER DEFAULT 0")
    except:
        pass
    
    # Старая таблица wagons остаётся для совместимости, но основная работа теперь через wagon_visits
    c.execute('''CREATE TABLE IF NOT EXISTS wagons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    wagon_number TEXT UNIQUE, length REAL, cargo_type TEXT, owner TEXT, 
                    organization TEXT, status TEXT DEFAULT 'assigned', track_id INTEGER, 
                    start_pos REAL, arrival_time TEXT, departure_time TEXT, local_departure_time TEXT,
                    visit_count INTEGER DEFAULT 0, is_archived INTEGER DEFAULT 0
                )''')
    
    for col in ['organization', 'local_departure_time', 'owner', 'visit_count', 'is_archived']:
        try: c.execute(f"ALTER TABLE wagons ADD COLUMN {col} TEXT")
        except: pass

    # Новая таблица визитов
    c.execute('''CREATE TABLE IF NOT EXISTS wagon_visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wagon_number TEXT NOT NULL,
                    arrival_time TEXT,
                    departure_time TEXT,
                    local_departure_time TEXT,
                    is_archived INTEGER DEFAULT 0,
                    track_id INTEGER,
                    start_pos REAL,
                    cargo_type TEXT,
                    owner TEXT,
                    organization TEXT,
                    length REAL DEFAULT 10.0,
                    status TEXT DEFAULT 'assigned',
                    visit_count INTEGER DEFAULT 0
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS action_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    username TEXT,
                    ip_address TEXT,
                    action TEXT,
                    wagon_number TEXT,
                    details TEXT,
                    old_value TEXT,
                    new_value TEXT
                )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS ip_users (
                    ip_address TEXT PRIMARY KEY,
                    username TEXT,
                    note TEXT,
                    is_admin INTEGER DEFAULT 0,
                    role TEXT DEFAULT 'dispatcher',
                    access_allowed INTEGER DEFAULT 0
                )''')
    try:
        c.execute("ALTER TABLE ip_users ADD COLUMN is_admin INTEGER DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE ip_users ADD COLUMN role TEXT DEFAULT 'dispatcher'")
    except: pass
    try:
        c.execute("ALTER TABLE ip_users ADD COLUMN access_allowed INTEGER DEFAULT 0")
    except: pass
    
    # ===== ТАБЛИЦА НАСТРОЕК =====
    c.execute('''CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
    
    c.execute("SELECT COUNT(*) FROM app_settings")
    if c.fetchone()[0] == 0:
        default_settings = [
            ('port', '5000'),
            ('secret_key', 'rail_app_secret_key_change_me'),
            ('backup_hour', '3'),
            ('backup_keep_count', '30'),
            ('remote_enabled', '0'),
            ('remote_path', ''),
            ('remote_user', ''),
            ('remote_password', ''),
            ('log_max_mb', '5'),
            ('log_backup_count', '5'),
            ('refresh_interval', '5'),
            ('theme', 'light'),
            ('default_wagon_length', '10.0'),
            ('wagon_spacing', '50.0')
        ]
        c.executemany("INSERT INTO app_settings (key, value) VALUES (?, ?)", default_settings)

    # Настройки штрафов за перепростой
    overstay_defaults = [
        ('overstay_progressive', '0'),
        ('overstay_rate_base', '0'),
        ('overstay_threshold1', '3'),
        ('overstay_rate1', '1000'),
        ('overstay_threshold2', '7'),
        ('overstay_rate2', '1500'),
        ('overstay_rate3', '2000')
    ]
    for key, val in overstay_defaults:
        c.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (key, val))
    
    c.execute("UPDATE ip_users SET role='admin', access_allowed=1 WHERE is_admin=1 AND (role='dispatcher' OR role='')")
    c.execute("UPDATE ip_users SET access_allowed=1 WHERE is_admin=1")
    c.execute("UPDATE ip_users SET access_allowed=1 WHERE access_allowed=0 AND role='dispatcher'")
    
    c.execute("UPDATE tracks SET name = 'Резерв' WHERE name = 'Очередь (Буфер)'")
    conn.commit()
    
    c.execute("SELECT count(*) FROM tracks")
    if c.fetchone()[0] == 0:
        data = [
            (1, 'Ст. Черкасов Камень', 1000.0, 'normal', 1),
            (2, 'Пост №2', 1000.0, 'normal', 2),
            (3, 'АО "Знамя" (Осмотр)', 1000.0, 'normal', 3),
            (4, 'АО "Знамя" (Ремонт)', 1000.0, 'normal', 4),
            (5, 'АО "Знамя" (База - Погрузка)', 1000.0, 'normal', 5),
            (6, 'АО "Знамя" (Цех ППВВ - Погрузка)', 1000.0, 'normal', 6),
            (7, 'АО "Знамя" (Отстой)', 1000.0, 'normal', 7),
            (8, 'Резерв', 2000.0, 'normal', 8)
        ]
        c.executemany("INSERT INTO tracks (id, name, total_length, track_type, sort_order) VALUES (?, ?, ?, ?, ?)", data)
        print("[OK] База данных создана.")
    else:
        c.execute("UPDATE tracks SET sort_order = id WHERE sort_order IS NULL OR sort_order = 0")
    conn.commit()
    conn.close()

    # Миграция данных в wagon_visits (выполняется один раз)
    migrate_to_visits()


def migrate_to_visits():
    """Переносит данные из wagons в wagon_visits и обновляет archived_history."""
    conn = get_conn()
    c = conn.cursor()
    # Проверяем, не перенесены ли уже данные
    c.execute("SELECT COUNT(*) FROM wagon_visits")
    if c.fetchone()[0] > 0:
        conn.close()
        print("[OK] Данные уже перенесены в wagon_visits.")
        return

    print("[МИГРАЦИЯ] Перенос данных из wagons в wagon_visits...")
    # Копируем все записи из wagons (и активные, и архивные)
    c.execute("""
        INSERT INTO wagon_visits (wagon_number, arrival_time, departure_time, local_departure_time,
                                 is_archived, track_id, start_pos, cargo_type, owner, organization, length, status, visit_count)
        SELECT wagon_number, arrival_time, departure_time, local_departure_time,
               is_archived, track_id, start_pos, cargo_type, owner, organization, length, status, visit_count
        FROM wagons
    """)
    conn.commit()
    print(f"[МИГРАЦИЯ] Перенесено {c.rowcount} записей.")

    # Теперь для каждой записи в archived_history пытаемся найти соответствующий visit_id
    print("[МИГРАЦИЯ] Привязка archived_history к визитам...")
    c.execute("""
        UPDATE archived_history
        SET visit_id = (
            SELECT wv.id FROM wagon_visits wv
            WHERE wv.wagon_number = archived_history.wagon_number
              AND wv.is_archived = 1
              AND wv.arrival_time <= archived_history.timestamp
            ORDER BY wv.arrival_time DESC
            LIMIT 1
        )
        WHERE visit_id IS NULL
    """)
    conn.commit()
    print(f"[МИГРАЦИЯ] Обновлено {c.rowcount} записей в archived_history.")
    conn.close()
    print("[МИГРАЦИЯ] Готово.")


# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С НАСТРОЙКАМИ =====
def get_setting(key, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return default


def set_setting(key, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_all_settings():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT key, value FROM app_settings")
    rows = c.fetchall()
    conn.close()
    return dict(rows)


def clean_action_log():
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM action_log WHERE timestamp < datetime('now', '-6 months')")
    c.execute("SELECT COUNT(*) FROM action_log")
    count = c.fetchone()[0]
    if count > 20000:
        c.execute("DELETE FROM action_log WHERE id NOT IN (SELECT id FROM action_log ORDER BY id DESC LIMIT 20000)")
    conn.commit()
    conn.close()
    print(f"Журнал действий очищен: осталось записей {min(count, 20000)}")


# ==================== РЕЗЕРВНОЕ КОПИРОВАНИЕ ====================
def get_last_auto_backup_time():
    auto_dir = os.path.join(BACKUP_DIR, 'auto')
    if not os.path.exists(auto_dir):
        return None
    backups = glob.glob(os.path.join(auto_dir, 'rail_yard_auto_*.db'))
    if not backups:
        return None
    backups.sort(key=os.path.getmtime, reverse=True)
    last_backup = backups[0]
    return datetime.fromtimestamp(os.path.getmtime(last_backup))


def copy_backup_to_network(backup_filename):
    enabled = get_setting('remote_enabled', '0') == '1'
    if not enabled:
        return False
    remote_path = get_setting('remote_path', '').strip()
    if not remote_path:
        return False
    remote_user = get_setting('remote_user', '').strip()
    remote_password = get_setting('remote_password', '').strip()

    local_path = os.path.join(BACKUP_DIR, 'auto', backup_filename)
    remote_full = os.path.join(remote_path, backup_filename)

    try:
        if remote_user and remote_password:
            net_use_cmd = f'net use "{remote_path}" /user:{remote_user} {remote_password} >nul 2>&1'
            os.system(net_use_cmd)
        shutil.copy2(local_path, remote_full)
        log_action('backup_remote', details=f"Бэкап {backup_filename} скопирован на {remote_path}")
        return True
    except Exception as e:
        log_action('backup_remote_error', details=f"Ошибка копирования на {remote_path}: {e}")
        return False


def create_auto_backup():
    try:
        keep_count = int(get_setting('backup_keep_count', '30'))
        auto_dir = os.path.join(BACKUP_DIR, 'auto')
        if not os.path.exists(auto_dir):
            os.makedirs(auto_dir)
        backup_name = f"rail_yard_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(auto_dir, backup_name)
        shutil.copy2(DB_NAME, backup_path)
        all_backups = sorted(glob.glob(os.path.join(auto_dir, 'rail_yard_auto_*.db')), key=os.path.getmtime)
        while len(all_backups) > keep_count:
            os.remove(all_backups.pop(0))
        log_action('backup_auto', details=f"Автоматическая копия: {backup_path}")
        print(f"📦 Автоматический бэкап создан: {backup_path}")

        copy_backup_to_network(backup_name)
    except Exception as e:
        print(f"⚠️ Ошибка автоматического бэкапа: {e}")


def schedule_daily_backup():
    def backup_loop():
        while True:
            now = datetime.now()
            backup_hour = int(get_setting('backup_hour', '3'))
            next_run = now.replace(hour=backup_hour, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            print(f"⏰ Следующий автоматический бэкап запланирован на {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(wait_seconds)
            create_auto_backup()
    thread = threading.Thread(target=backup_loop, daemon=True)
    thread.start()


# ==================== УПРАВЛЕНИЕ ПУТЯМИ ====================
def get_all_tracks():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, total_length, track_type FROM tracks ORDER BY sort_order ASC")
    rows = c.fetchall()
    conn.close()
    return rows


def add_track(name, total_length, track_type='normal'):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT MAX(sort_order) FROM tracks")
        max_order = c.fetchone()[0] or 0
        c.execute("INSERT INTO tracks (name, total_length, track_type, sort_order) VALUES (?, ?, ?, ?)",
                  (name.strip(), float(total_length), track_type, max_order + 1))
        conn.commit()
        conn.close()
        log_action('track_add', details=f"Добавлен путь: {name}")
        return True, f"Путь '{name}' добавлен"
    except sqlite3.IntegrityError:
        conn.close()
        return False, f"Путь с именем '{name}' уже существует"
    except Exception as e:
        conn.close()
        return False, f"Ошибка: {e}"


def update_track(track_id, name, total_length, track_type):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("UPDATE tracks SET name = ?, total_length = ?, track_type = ? WHERE id = ?",
                  (name.strip(), float(total_length), track_type, track_id))
        conn.commit()
        conn.close()
        log_action('track_edit', details=f"Изменён путь id={track_id}: {name}")
        return True, f"Путь '{name}' обновлён"
    except sqlite3.IntegrityError:
        conn.close()
        return False, f"Путь с именем '{name}' уже существует"
    except Exception as e:
        conn.close()
        return False, f"Ошибка: {e}"


def delete_track(track_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM wagon_visits WHERE track_id = ? AND is_archived = 0", (track_id,))
    count = c.fetchone()[0]
    if count > 0:
        conn.close()
        return False, f"Невозможно удалить путь: на нём находятся {count} активных вагонов"
    try:
        c.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        conn.commit()
        conn.close()
        log_action('track_delete', details=f"Удалён путь id={track_id}")
        return True, "Путь удалён"
    except Exception as e:
        conn.close()
        return False, f"Ошибка: {e}"


def move_track_up(track_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT sort_order FROM tracks WHERE id = ?", (track_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    current_order = row[0]
    c.execute("SELECT id, sort_order FROM tracks WHERE sort_order < ? ORDER BY sort_order DESC LIMIT 1", (current_order,))
    prev = c.fetchone()
    if prev:
        prev_id, prev_order = prev
        c.execute("UPDATE tracks SET sort_order = ? WHERE id = ?", (prev_order, track_id))
        c.execute("UPDATE tracks SET sort_order = ? WHERE id = ?", (current_order, prev_id))
        conn.commit()
        log_action('track_move', details=f"Путь id={track_id} перемещён вверх")
    conn.close()
    return True


def move_track_down(track_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT sort_order FROM tracks WHERE id = ?", (track_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    current_order = row[0]
    c.execute("SELECT id, sort_order FROM tracks WHERE sort_order > ? ORDER BY sort_order ASC LIMIT 1", (current_order,))
    next_row = c.fetchone()
    if next_row:
        next_id, next_order = next_row
        c.execute("UPDATE tracks SET sort_order = ? WHERE id = ?", (next_order, track_id))
        c.execute("UPDATE tracks SET sort_order = ? WHERE id = ?", (current_order, next_id))
        conn.commit()
        log_action('track_move', details=f"Путь id={track_id} перемещён вниз")
    conn.close()
    return True


# ==================== УПРАВЛЕНИЕ ВАГОНАМИ ====================
def get_last_event_datetime(wagon_number):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT timestamp FROM movement_history WHERE wagon_number = ? ORDER BY timestamp DESC LIMIT 1", (wagon_number,))
    row = c.fetchone()
    if row:
        conn.close()
        return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
    c.execute("SELECT arrival_time FROM wagon_visits WHERE wagon_number = ? AND is_archived = 0", (wagon_number,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
    return None


def log_movement(wagon_number, action_type, from_track_name=None, to_track_name=None, note=None, custom_timestamp=None):
    conn = get_conn()
    c = conn.cursor()
    timestamp = custom_timestamp if custom_timestamp else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    clean_note = clean_note_for_db(note)
    c.execute("""INSERT INTO movement_history (wagon_number, action_type, from_track, to_track, note, timestamp) VALUES (?, ?, ?, ?, ?, ?)""",
              (wagon_number, action_type, from_track_name, to_track_name, clean_note, timestamp))
    conn.commit()
    conn.close()


def compact_track(track_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, length FROM wagon_visits WHERE track_id = ? AND status != 'departed' AND is_archived = 0 ORDER BY start_pos ASC", (track_id,))
    wagons = c.fetchall()
    current_pos = 0.0
    spacing = float(get_setting('wagon_spacing', '50.0'))
    for wag_id, wag_len in wagons:
        w_len = float(wag_len) if wag_len is not None else 10.0
        c.execute("UPDATE wagon_visits SET start_pos = ? WHERE id = ?", (current_pos, wag_id))
        current_pos += w_len + spacing
    conn.commit()
    conn.close()


def find_slot_on_track(track_id, wagon_length):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT total_length FROM tracks WHERE id = ?", (track_id,))
    res = c.fetchone()
    if not res: 
        conn.close()
        return None, 0.0
    c.execute("SELECT start_pos, length FROM wagon_visits WHERE track_id = ? AND status != 'departed' AND is_archived = 0 ORDER BY start_pos", (track_id,))
    occupied = c.fetchall()
    spacing = float(get_setting('wagon_spacing', '50.0'))
    if not occupied: 
        conn.close()
        return track_id, 0.0
    last_wagon = occupied[-1]
    last_pos = float(last_wagon[0]) if last_wagon[0] is not None else 0.0
    last_len = float(last_wagon[1]) if last_wagon[1] is not None else 10.0
    next_pos = last_pos + last_len + spacing
    conn.close()
    return track_id, next_pos


def move_wagon(wagon_id, new_track_id, local_days=0, local_hours=0, local_mins=0, manual_start_str=None, new_note=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, owner, organization, departure_time, track_id, cargo_type, visit_count, arrival_time FROM wagon_visits WHERE id = ? AND is_archived = 0", (wagon_id,))
    res = c.fetchone()
    if not res: 
        conn.close()
        return False, "Вагон не найден"
    
    w_num, w_owner, org, global_dep, old_track_id, current_note, current_visits, arrival_time_str = res
    last_event_dt = get_last_event_datetime(w_num)
    
    c.execute("SELECT name FROM tracks WHERE id = ?", (old_track_id,))
    from_track_name = c.fetchone()[0]
    c.execute("SELECT name FROM tracks WHERE id = ?", (new_track_id,))
    to_track_name = c.fetchone()[0]
    
    new_visit_count = int(current_visits) if current_visits is not None else 0
    if not is_return_track(to_track_name): 
        new_visit_count += 1
    
    new_local_dep_time = None
    total_mins = (int(local_days) * 24 * 60) + (int(local_hours) * 60) + int(local_mins)
    
    if manual_start_str and manual_start_str.strip():
        try:
            start_dt = datetime.strptime(manual_start_str.replace('T', ' '), '%Y-%m-%d %H:%M')
            if last_event_dt and start_dt <= last_event_dt:
                conn.close()
                return False, f"Дата начала отсчёта не может быть раньше или равна предыдущему событию"
            if arrival_time_str:
                try:
                    arrival_dt_check = datetime.strptime(arrival_time_str, '%Y-%m-%d %H:%M:%S')
                    if start_dt <= arrival_dt_check:
                        conn.close()
                        return False, f"Дата начала отсчёта не может быть раньше времени прибытия"
                except:
                    pass
            log_timestamp = manual_start_str.replace('T', ' ') + ":00"
        except ValueError:
            log_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    else:
        log_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if total_mins > 0:
        if manual_start_str and manual_start_str.strip():
            try:
                start_dt = datetime.strptime(manual_start_str.replace('T', ' '), '%Y-%m-%d %H:%M')
                new_local_dep_time = (start_dt + timedelta(minutes=total_mins)).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                new_local_dep_time = (datetime.now() + timedelta(minutes=total_mins)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            new_local_dep_time = (datetime.now() + timedelta(minutes=total_mins)).strftime('%Y-%m-%d %H:%M:%S')
    else:
        new_local_dep_time = None
    
    compact_track(new_track_id)
    wagon_len = float(get_setting('default_wagon_length', '10.0'))
    target_track, new_pos = find_slot_on_track(new_track_id, wagon_len)
    if target_track is None: 
        conn.close()
        return False, "Ошибка пути"
    
    update_note = clean_note_for_db(new_note) if (new_note and new_note.strip()) else clean_note_for_db(current_note)
    
    c.execute("""UPDATE wagon_visits SET track_id = ?, start_pos = ?, local_departure_time = ?, cargo_type = ?, visit_count = ? WHERE id = ?""", 
              (target_track, new_pos, new_local_dep_time, update_note, new_visit_count, wagon_id))
    
    conn.commit()
    conn.close()
    log_movement(w_num, 'moved', from_track_name, to_track_name, f"Примечание: {update_note}" if update_note else "", log_timestamp)
    log_action('move', wagon_number=w_num, details=f"с '{from_track_name}' на '{to_track_name}'")
    return True, "Вагон перемещен!"


def depart_wagon(visit_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, track_id FROM wagon_visits WHERE id = ? AND is_archived = 0", (visit_id,))
    res = c.fetchone()
    if res:
        w_num, track_id = res
        c.execute("SELECT name FROM tracks WHERE id = ?", (track_id,))
        track_name_res = c.fetchone()
        track_name = track_name_res[0] if track_name_res else "Неизвестный путь"
        archived_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Переносим историю конкретного визита в архив
        c.execute("""INSERT INTO archived_history (wagon_number, action_type, from_track, to_track, note, timestamp, archived_date, visit_id) 
                     SELECT wagon_number, action_type, from_track, to_track, note, timestamp, ?, ? FROM movement_history WHERE wagon_number = ?""", 
                  (archived_date, visit_id, w_num))
        # Удаляем перемещения этого вагона из активной истории
        c.execute("DELETE FROM movement_history WHERE wagon_number = ?", (w_num,))
        # Помечаем визит как архивный
        c.execute("UPDATE wagon_visits SET status = 'departed', is_archived = 1 WHERE id = ?", (visit_id,))
        
        conn.commit()
        conn.close()
        compact_track(track_id)
        
        conn_arch = get_conn()
        c_arch = conn_arch.cursor()
        c_arch.execute("""INSERT INTO archived_history (wagon_number, action_type, from_track, to_track, note, timestamp, archived_date, visit_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                       (w_num, 'departed', track_name, None, "Убран в архив", archived_date, archived_date, visit_id))
        conn_arch.commit()
        conn_arch.close()
        log_action('depart', wagon_number=w_num, details=f"Убран в архив с пути {track_name}")
        return True
    return False


def edit_wagon(visit_id, new_owner=None, new_org=None, new_note=None,
               new_arrival_time=None, new_global_deadline=None, new_local_deadline=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT wagon_number, owner, organization, cargo_type, arrival_time, 
                 departure_time, local_departure_time, track_id
                 FROM wagon_visits WHERE id = ? AND is_archived = 0""", (visit_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "Вагон не найден или находится в архиве"
    w_num, old_owner, old_org, old_note, old_arrival, old_global, old_local, track_id = row
    
    updates = []
    params = []
    changes = []
    
    if new_owner is not None and new_owner != old_owner:
        updates.append("owner = ?")
        params.append(new_owner)
        changes.append(f"ТК: '{old_owner}' → '{new_owner}'")
    if new_org is not None and new_org != old_org:
        updates.append("organization = ?")
        params.append(new_org)
        changes.append(f"Организация: '{old_org}' → '{new_org}'")
    if new_note is not None and new_note != old_note:
        updates.append("cargo_type = ?")
        params.append(clean_note_for_db(new_note))
        changes.append(f"Примечание: '{old_note}' → '{new_note}'")
    
    last_event_dt = get_last_event_datetime(w_num)
    
    if new_arrival_time is not None and new_arrival_time.strip() != "":
        try:
            from app.utils import parse_flexible_date
            new_arr_dt = parse_flexible_date(new_arrival_time)
            if new_arr_dt is None:
                raise ValueError("Пустая дата")
            new_arrival_time_str = new_arr_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            conn.close()
            return False, f"Ошибка в дате прибытия: {e}"
        if last_event_dt and new_arr_dt > last_event_dt:
            conn.close()
            return False, "Дата прибытия не может быть позже последнего перемещения"
        updates.append("arrival_time = ?")
        params.append(new_arrival_time_str)
        changes.append(f"Время прибытия: '{old_arrival}' → '{new_arrival_time_str}'")
    
    if new_global_deadline is not None and new_global_deadline.strip() != "":
        try:
            from app.utils import parse_flexible_date
            new_glob_dt = parse_flexible_date(new_global_deadline)
            if new_glob_dt is None:
                raise ValueError("Пустая дата")
            new_global_str = new_glob_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            conn.close()
            return False, f"Ошибка в глобальном сроке: {e}"
        arrival_dt = datetime.strptime(old_arrival, '%Y-%m-%d %H:%M:%S') if old_arrival else None
        if arrival_dt and new_glob_dt < arrival_dt:
            conn.close()
            return False, "Глобальный срок не может быть раньше времени прибытия"
        if last_event_dt and new_glob_dt < last_event_dt:
            conn.close()
            return False, "Глобальный срок не может быть раньше последнего перемещения"
        updates.append("departure_time = ?")
        params.append(new_global_str)
        changes.append(f"Глобальный срок: '{old_global}' → '{new_global_str}'")
    
    if new_local_deadline is not None and new_local_deadline.strip() != "":
        try:
            from app.utils import parse_flexible_date
            new_local_dt = parse_flexible_date(new_local_deadline)
            if new_local_dt is None:
                raise ValueError("Пустая дата")
            new_local_str = new_local_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            conn.close()
            return False, f"Ошибка в локальном сроке: {e}"
        arrival_dt = datetime.strptime(old_arrival, '%Y-%m-%d %H:%M:%S') if old_arrival else None
        if arrival_dt and new_local_dt < arrival_dt:
            conn.close()
            return False, "Локальный срок не может быть раньше времени прибытия"
        if last_event_dt and new_local_dt < last_event_dt:
            conn.close()
            return False, "Локальный срок не может быть раньше последнего перемещения"
        updates.append("local_departure_time = ?")
        params.append(new_local_str)
        changes.append(f"Локальный срок: '{old_local}' → '{new_local_str}'")
    
    if not updates:
        conn.close()
        return True, "Нет изменений"
    
    query = "UPDATE wagon_visits SET " + ", ".join(updates) + " WHERE id = ?"
    params.append(visit_id)
    c.execute(query, params)
    conn.commit()
    conn.close()
    
    changes_str = "; ".join(changes)
    log_movement(w_num, 'edit', note=f"Изменения: {changes_str}", custom_timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    log_action('edit', wagon_number=w_num, details=changes_str, old_value=changes_str, new_value=changes_str)
    return True, "Данные вагона обновлены"


# ==================== ПОЛУЧЕНИЕ ДАННЫХ ДЛЯ ИНТЕРФЕЙСА ====================
def get_dashboard_data():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, total_length, track_type FROM tracks ORDER BY sort_order ASC")
    tracks_raw = c.fetchall()
    # Теперь используем wagon_visits вместо wagons
    c.execute("""SELECT wv.id, wv.wagon_number, wv.length, wv.cargo_type, wv.owner, wv.organization, wv.track_id, wv.start_pos, wv.arrival_time, wv.departure_time, wv.local_departure_time, t.name, wv.visit_count 
                 FROM wagon_visits wv 
                 JOIN tracks t ON wv.track_id = t.id 
                 WHERE wv.status != 'departed' AND wv.is_archived = 0 
                 ORDER BY t.sort_order ASC, wv.start_pos ASC""")
    all_wagons_raw = c.fetchall()
    conn.close()
    
    tracks_data = []
    now = datetime.now()
    wagons_by_track = {}
    for w in all_wagons_raw:
        tid = w[6]
        if tid not in wagons_by_track: 
            wagons_by_track[tid] = []
        wagons_by_track[tid].append(w)
    
    for t_id, t_name, t_len, t_type in tracks_raw:
        try: 
            t_len = float(t_len)
        except: 
            t_len = 1000.0
        track_wagons = wagons_by_track.get(t_id, [])
        processed = []
        is_return_track_flag = is_return_track(t_name)
        for w in track_wagons:
            w_id, w_num, w_len, w_note, w_owner, w_org, w_tid, w_pos, w_arr, w_glob, w_loc, tr_name, w_visits = w
            try: 
                w_visits = int(w_visits) if w_visits is not None else 0
            except: 
                w_visits = 0
            try: 
                w_pos = float(w_pos) if w_pos is not None else 0.0
            except: 
                w_pos = 0.0
            try: 
                w_len = float(w_len) if w_len is not None else 10.0
            except: 
                w_len = 10.0
            
            loc_text_parts = {"d": 0, "h": 0, "m": 0, "s": 0, "raw": 999999, "iso": "", "overdue": False}
            if w_loc:
                try: 
                    dt = datetime.strptime(str(w_loc)[:19], '%Y-%m-%d %H:%M:%S')
                    loc_iso = dt.strftime('%Y-%m-%dT%H:%M:%S')
                    diff = (dt - now).total_seconds()
                    if diff > 0:
                        m, s = divmod(int(diff), 60)
                        h, m = divmod(m, 60)
                        d, h = divmod(h, 24)
                        loc_text_parts = {
                            "raw": diff,
                            "d": d,
                            "h": h,
                            "m": m,
                            "s": s,
                            "iso": loc_iso,
                            "overdue": False
                        }
                    else:
                        loc_text_parts = {"overdue": True, "raw": diff, "iso": loc_iso, "d": 0, "h": 0, "m": 0, "s": 0}
                except:
                    loc_text_parts = {"raw": 999999, "overdue": False, "iso": "", "d": 0, "h": 0, "m": 0, "s": 0}
            else:
                loc_text_parts = {"raw": 999999, "overdue": False, "iso": "", "d": 0, "h": 0, "m": 0, "s": 0}
            
            glob_text_parts = {"d": 0, "h": 0, "m": 0, "raw": 0, "iso": "", "overdue": False}
            if w_glob:
                try: 
                    dt = datetime.strptime(str(w_glob)[:19], '%Y-%m-%d %H:%M:%S')
                    glob_iso = dt.strftime('%Y-%m-%dT%H:%M:%S')
                    diff = (dt - now).total_seconds()
                    if diff > 0: 
                        m, s = divmod(int(diff), 60)
                        h, m = divmod(m, 60)
                        d, h = divmod(h, 24)
                        glob_text_parts = {
                            "raw": diff, 
                            "d": d, 
                            "h": h, 
                            "m": m, 
                            "iso": glob_iso,
                            "overdue": False
                        }
                    else: 
                        glob_text_parts = {"raw": diff, "iso": glob_iso, "d": 0, "h": 0, "m": 0, "overdue": True}
                except: 
                    pass
            
            is_global_overdue = glob_text_parts.get('overdue', False)
            processed.append({
                "id": w_id, 
                "num": w_num, 
                "note": w_note or "-", 
                "owner": w_owner or "Не указана", 
                "org": w_org or "Не указано", 
                "pos": w_pos, 
                "arrival": format_date(w_arr), 
                "loc": loc_text_parts, 
                "glob": glob_text_parts, 
                "is_return_track": is_return_track_flag, 
                "is_highlighted_return": is_return_track_flag and (w_visits > 0),
                "is_global_overdue": is_global_overdue
            })
        tracks_data.append({"id": t_id, "name": t_name, "total": t_len, "type": t_type, "wagons": processed})
    
    move_list = [{"id": w[0], "text": f"{w[1]} [{w[4] or ''}] ({w[5] or ''}) | {w[11]}", "current_note": w[3] or ""} for w in all_wagons_raw]
    return tracks_data, move_list


def get_grouped_history():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT m.id, m.wagon_number, m.action_type, m.from_track, m.to_track, m.note, m.timestamp, wv.owner, wv.organization, wv.cargo_type 
                 FROM movement_history m 
                 LEFT JOIN wagon_visits wv ON m.wagon_number = wv.wagon_number AND wv.is_archived = 0
                 ORDER BY m.wagon_number, m.timestamp ASC""")
    rows = c.fetchall()
    conn.close()
    grouped = defaultdict(list)
    for row in rows:
        hist_id, w_num, action, from_t, to_t, note, ts_str, owner, org, cargo_type = row
        if action == 'added':
            action_label = "<span style='color:#27ae60'>Добавлен</span>"
        elif action == 'moved':
            action_label = "<span style='color:#f39c12'>Перемещен</span>"
        elif action == 'edit':
            action_label = "<span style='color:#8e44ad'>Изменён</span>"
        else:
            action_label = "<span style='color:#e74c3c'>Убыл</span>"
        grouped[w_num].append({
            "id": hist_id,
            "action": action_label,
            "from": from_t or "-",
            "to": to_t or "-",
            "owner": owner or "-",
            "org": org or "-",
            "cargo": cargo_type or "-",
            "note": note or "-",
            "time": ts_str
        })
    def sort_key(k):
        try:
            return (0, int(k))
        except:
            return (1, k)
    sorted_wagons = sorted(grouped.keys(), key=sort_key)
    result = []
    for w_num in sorted_wagons:
        events = grouped[w_num]
        for idx, ev in enumerate(events):
            ev['is_last'] = (idx == len(events) - 1)
        result.append({
            "num": w_num,
            "last_status": events[-1]['action'],
            "last_time": events[-1]['time'],
            "events": events,
            "count": len(events)
        })
    return result


def get_grouped_archive_history():
    conn = get_conn()
    c = conn.cursor()
    # Группируем по номеру вагона, но внутри каждой группы могут быть разные visit_id
    # Для отображения в архиве нам нужны все записи, отсортированные по времени
    c.execute("""SELECT a.wagon_number, a.action_type, a.from_track, a.to_track, a.note, a.timestamp, wv.owner, wv.organization, wv.cargo_type 
                 FROM archived_history a 
                 LEFT JOIN wagon_visits wv ON a.visit_id = wv.id
                 ORDER BY a.wagon_number, a.timestamp ASC""")
    rows = c.fetchall()
    conn.close()
    grouped = defaultdict(list)
    for row in rows:
        w_num, action, from_t, to_t, note, ts_str, owner, org, cargo_type = row
        if action == 'added':
            action_label = "<span style='color:#27ae60'>Добавлен</span>"
        elif action == 'moved':
            action_label = "<span style='color:#f39c12'>Перемещен</span>"
        elif action == 'edit':
            action_label = "<span style='color:#8e44ad'>Изменён</span>"
        else:
            action_label = "<span style='color:#e74c3c'>Убыл</span>"
        grouped[w_num].append({
            "action": action_label, 
            "from": from_t or "-", 
            "to": to_t or "-", 
            "owner": owner or "-", 
            "org": org or "-", 
            "cargo": cargo_type or "-",
            "note": note or "-",
            "time": ts_str
        })
    def sort_key(k):
        try:
            return (0, int(k))
        except:
            return (1, k)
    sorted_wagons = sorted(grouped.keys(), key=sort_key)
    result = []
    for w_num in sorted_wagons:
        events = grouped[w_num]
        result.append({
            "num": w_num, 
            "last_status": events[-1]['action'], 
            "last_time": events[-1]['time'], 
            "events": events, 
            "count": len(events)
        })
    return result


# ==================== РАСЧЁТ ПЕРЕПРОСТОЯ (ПО ВИЗИТУ) ====================
def calculate_overstay(visit_id):
    """
    Возвращает кортеж (перепростой_сутки, сумма_руб) для конкретного визита.
    Если перепростоя нет, возвращает (0, 0.0).
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT arrival_time, departure_time,
                 (SELECT MAX(timestamp) FROM archived_history WHERE visit_id = ?) as last_ts
                 FROM wagon_visits WHERE id = ? AND is_archived = 1""",
              (visit_id, visit_id))
    row = c.fetchone()
    if not row:
        conn.close()
        return 0, 0.0

    arrival_str, global_deadline_str, last_ts_str = row
    if not arrival_str or not last_ts_str:
        conn.close()
        return 0, 0.0

    try:
        arrival_dt = datetime.strptime(arrival_str[:10], '%Y-%m-%d')
        last_dt = datetime.strptime(last_ts_str[:10], '%Y-%m-%d')
    except:
        conn.close()
        return 0, 0.0

    calendar_days = (last_dt - arrival_dt).days + 1
    if calendar_days <= 0:
        conn.close()
        return 0, 0.0

    allowed_days = 0
    if global_deadline_str:
        try:
            global_dt = datetime.strptime(global_deadline_str[:10], '%Y-%m-%d')
            allowed_days = (global_dt - arrival_dt).days
        except:
            pass
    if allowed_days < 0:
        allowed_days = 0

    overstay = calendar_days - allowed_days
    if overstay <= 0:
        conn.close()
        return 0, 0.0

    progressive = get_setting('overstay_progressive', '0') == '1'
    if progressive:
        threshold1 = int(get_setting('overstay_threshold1', '3'))
        threshold2 = int(get_setting('overstay_threshold2', '7'))
        rate1 = float(get_setting('overstay_rate1', '1000'))
        rate2 = float(get_setting('overstay_rate2', '1500'))
        rate3 = float(get_setting('overstay_rate3', '2000'))

        days1 = min(overstay, threshold1)
        amount = days1 * rate1
        remaining = overstay - days1
        if remaining > 0:
            days2 = min(remaining, threshold2 - threshold1)
            amount += days2 * rate2
            remaining -= days2
            if remaining > 0:
                amount += remaining * rate3
    else:
        base_rate = float(get_setting('overstay_rate_base', '0'))
        amount = overstay * base_rate

    conn.close()
    return overstay, amount