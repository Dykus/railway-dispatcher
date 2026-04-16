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
from config import DB_NAME, BACKUP_DIR, BACKUP_HOUR, BACKUP_KEEP_COUNT, CHANGELOG_PATH
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
                    wagon_number TEXT, action_type TEXT, from_track TEXT, to_track TEXT, note TEXT, timestamp TEXT, archived_date TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS tracks (id INTEGER PRIMARY KEY, name TEXT UNIQUE, total_length REAL, track_type TEXT DEFAULT 'normal')''')
    
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
    
    # ===== НОВАЯ ТАБЛИЦА НАСТРОЕК =====
    c.execute('''CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
    
    # Установка значений по умолчанию, если таблица пуста
    c.execute("SELECT COUNT(*) FROM app_settings")
    if c.fetchone()[0] == 0:
        default_settings = [
            ('port', '5000'),
            ('secret_key', 'rail_app_secret_key_change_me'),
            ('backup_hour', str(BACKUP_HOUR)),
            ('backup_keep_count', str(BACKUP_KEEP_COUNT)),
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
    # ===== КОНЕЦ НОВОГО БЛОКА =====
    
    c.execute("UPDATE ip_users SET role='admin', access_allowed=1 WHERE is_admin=1 AND (role='dispatcher' OR role='')")
    c.execute("UPDATE ip_users SET access_allowed=1 WHERE is_admin=1")
    c.execute("UPDATE ip_users SET access_allowed=1 WHERE access_allowed=0 AND role='dispatcher'")
    
    c.execute("UPDATE tracks SET name = 'Резерв' WHERE name = 'Очередь (Буфер)'")
    conn.commit()
    
    c.execute("SELECT count(*) FROM tracks")
    if c.fetchone()[0] == 0:
        data = [
            (1, 'Ст. Черкасов Камень', 1000.0, 'normal'),
            (2, 'Пост №2', 1000.0, 'normal'),
            (3, 'АО "Знамя" (Осмотр)', 1000.0, 'normal'),
            (4, 'АО "Знамя" (Ремонт)', 1000.0, 'normal'),
            (5, 'АО "Знамя" (База - Погрузка)', 1000.0, 'normal'),
            (6, 'АО "Знамя" (Цех ППВВ - Погрузка)', 1000.0, 'normal'),
            (7, 'АО "Знамя" (Отстой)', 1000.0, 'normal'),
            (8, 'Резерв', 2000.0, 'normal')
        ]
        c.executemany("INSERT INTO tracks VALUES (?, ?, ?, ?)", data)
        print("[OK] База данных создана.")
    conn.commit()
    conn.close()


# ===== НОВЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С НАСТРОЙКАМИ =====
def get_setting(key, default=None):
    """Получает значение настройки из БД."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return default


def set_setting(key, value):
    """Сохраняет настройку в БД."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_all_settings():
    """Возвращает словарь всех настроек."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT key, value FROM app_settings")
    rows = c.fetchall()
    conn.close()
    return dict(rows)
# ===== КОНЕЦ НОВЫХ ФУНКЦИЙ =====


def clean_action_log():
    """Удаляет старые записи из журнала действий."""
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
    """Возвращает время последнего автоматического бэкапа."""
    auto_dir = os.path.join(BACKUP_DIR, 'auto')
    if not os.path.exists(auto_dir):
        return None
    backups = glob.glob(os.path.join(auto_dir, 'rail_yard_auto_*.db'))
    if not backups:
        return None
    backups.sort(key=os.path.getmtime, reverse=True)
    last_backup = backups[0]
    return datetime.fromtimestamp(os.path.getmtime(last_backup))


def create_auto_backup():
    """Создаёт автоматическую резервную копию БД."""
    try:
        auto_dir = os.path.join(BACKUP_DIR, 'auto')
        if not os.path.exists(auto_dir):
            os.makedirs(auto_dir)
        backup_name = f"rail_yard_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(auto_dir, backup_name)
        shutil.copy2(DB_NAME, backup_path)
        all_backups = sorted(glob.glob(os.path.join(auto_dir, 'rail_yard_auto_*.db')), key=os.path.getmtime)
        while len(all_backups) > BACKUP_KEEP_COUNT:
            os.remove(all_backups.pop(0))
        # Логирование (без контекста запроса, используем log_action из utils, но передаём system)
        from app.utils import log_action
        log_action('backup_auto', details=f"Автоматическая копия: {backup_path}")
        print(f"📦 Автоматический бэкап создан: {backup_path}")
    except Exception as e:
        print(f"⚠️ Ошибка автоматического бэкапа: {e}")


def schedule_daily_backup():
    """Запускает фоновый поток для ежедневного бэкапа."""
    def backup_loop():
        while True:
            now = datetime.now()
            next_run = now.replace(hour=BACKUP_HOUR, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            print(f"⏰ Следующий автоматический бэкап запланирован на {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(wait_seconds)
            create_auto_backup()
    thread = threading.Thread(target=backup_loop, daemon=True)
    thread.start()


# ==================== УПРАВЛЕНИЕ ВАГОНАМИ ====================
def get_last_event_datetime(wagon_number):
    """Возвращает дату и время последнего события вагона."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT timestamp FROM movement_history WHERE wagon_number = ? ORDER BY timestamp DESC LIMIT 1", (wagon_number,))
    row = c.fetchone()
    if row:
        conn.close()
        return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
    c.execute("SELECT arrival_time FROM wagons WHERE wagon_number = ? AND is_archived = 0", (wagon_number,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
    return None


def log_movement(wagon_number, action_type, from_track_name=None, to_track_name=None, note=None, custom_timestamp=None):
    """Записывает событие в историю перемещений."""
    conn = get_conn()
    c = conn.cursor()
    timestamp = custom_timestamp if custom_timestamp else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    clean_note = clean_note_for_db(note)
    c.execute("""INSERT INTO movement_history (wagon_number, action_type, from_track, to_track, note, timestamp) VALUES (?, ?, ?, ?, ?, ?)""",
              (wagon_number, action_type, from_track_name, to_track_name, clean_note, timestamp))
    conn.commit()
    conn.close()


def compact_track(track_id):
    """Уплотняет вагоны на пути (пересчитывает start_pos)."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, length FROM wagons WHERE track_id = ? AND status != 'departed' AND is_archived = 0 ORDER BY start_pos ASC", (track_id,))
    wagons = c.fetchall()
    current_pos = 0.0
    for wag_id, wag_len in wagons:
        w_len = float(wag_len) if wag_len is not None else 10.0
        c.execute("UPDATE wagons SET start_pos = ? WHERE id = ?", (current_pos, wag_id))
        current_pos += w_len + 50.0
    conn.commit()
    conn.close()


def find_slot_on_track(track_id, wagon_length):
    """Находит свободную позицию на пути."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT total_length FROM tracks WHERE id = ?", (track_id,))
    res = c.fetchone()
    if not res: 
        conn.close()
        return None, 0.0
    c.execute("SELECT start_pos, length FROM wagons WHERE track_id = ? AND status != 'departed' AND is_archived = 0 ORDER BY start_pos", (track_id,))
    occupied = c.fetchall()
    if not occupied: 
        conn.close()
        return track_id, 0.0
    last_wagon = occupied[-1]
    last_pos = float(last_wagon[0]) if last_wagon[0] is not None else 0.0
    last_len = float(last_wagon[1]) if last_wagon[1] is not None else 10.0
    next_pos = last_pos + last_len + 50 
    conn.close()
    return track_id, next_pos


def move_wagon(wagon_id, new_track_id, local_days=0, local_hours=0, local_mins=0, manual_start_str=None, new_note=None):
    """Перемещает вагон на другой путь, устанавливает локальный срок."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, owner, organization, departure_time, track_id, cargo_type, visit_count, arrival_time FROM wagons WHERE id = ? AND is_archived = 0", (wagon_id,))
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
    
    # Определяем время события
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
    target_track, new_pos = find_slot_on_track(new_track_id, 10)
    if target_track is None: 
        conn.close()
        return False, "Ошибка пути"
    
    update_note = clean_note_for_db(new_note) if (new_note and new_note.strip()) else clean_note_for_db(current_note)
    
    c.execute("""UPDATE wagons SET track_id = ?, start_pos = ?, local_departure_time = ?, cargo_type = ?, visit_count = ? WHERE id = ?""", 
              (target_track, new_pos, new_local_dep_time, update_note, new_visit_count, wagon_id))
    
    conn.commit()
    conn.close()
    log_movement(w_num, 'moved', from_track_name, to_track_name, f"Примечание: {update_note}" if update_note else "", log_timestamp)
    log_action('move', wagon_number=w_num, details=f"с '{from_track_name}' на '{to_track_name}'")
    return True, "Вагон перемещен!"


def depart_wagon(wagon_id):
    """Архивирует вагон (убытие)."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, track_id FROM wagons WHERE id = ? AND is_archived = 0", (wagon_id,))
    res = c.fetchone()
    if res:
        w_num, track_id = res
        c.execute("SELECT name FROM tracks WHERE id = ?", (track_id,))
        track_name_res = c.fetchone()
        track_name = track_name_res[0] if track_name_res else "Неизвестный путь"
        archived_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        c.execute("""INSERT INTO archived_history (wagon_number, action_type, from_track, to_track, note, timestamp, archived_date) 
                     SELECT wagon_number, action_type, from_track, to_track, note, timestamp, ? FROM movement_history WHERE wagon_number = ?""", 
                  (archived_date, w_num))
        
        c.execute("DELETE FROM movement_history WHERE wagon_number = ?", (w_num,))
        c.execute("UPDATE wagons SET status = 'departed', is_archived = 1 WHERE id = ?", (wagon_id,))
        
        conn.commit()
        conn.close()
        compact_track(track_id)
        
        conn_arch = get_conn()
        c_arch = conn_arch.cursor()
        c_arch.execute("""INSERT INTO archived_history (wagon_number, action_type, from_track, to_track, note, timestamp, archived_date) VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                       (w_num, 'departed', track_name, None, "Убран в архив", archived_date, archived_date))
        conn_arch.commit()
        conn_arch.close()
        log_action('depart', wagon_number=w_num, details=f"Убран в архив с пути {track_name}")
        return True
    return False


def edit_wagon(wagon_id, new_owner=None, new_org=None, new_note=None,
               new_arrival_time=None, new_global_deadline=None, new_local_deadline=None):
    """Редактирует данные вагона (кроме номера)."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, owner, organization, cargo_type, arrival_time, departure_time, local_departure_time, track_id FROM wagons WHERE id = ? AND is_archived = 0", (wagon_id,))
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
    
    query = "UPDATE wagons SET " + ", ".join(updates) + " WHERE id = ?"
    params.append(wagon_id)
    c.execute(query, params)
    conn.commit()
    conn.close()
    
    changes_str = "; ".join(changes)
    log_movement(w_num, 'edit', note=f"Изменения: {changes_str}", custom_timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    log_action('edit', wagon_number=w_num, details=changes_str, old_value=changes_str, new_value=changes_str)
    return True, "Данные вагона обновлены"


# ==================== ПОЛУЧЕНИЕ ДАННЫХ ДЛЯ ИНТЕРФЕЙСА ====================
def get_dashboard_data():
    """Возвращает данные о путях и вагонах для главной страницы и API."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, total_length, track_type FROM tracks ORDER BY id")
    tracks_raw = c.fetchall()
    c.execute("""SELECT w.id, w.wagon_number, w.length, w.cargo_type, w.owner, w.organization, w.track_id, w.start_pos, w.arrival_time, w.departure_time, w.local_departure_time, t.name, w.visit_count 
                 FROM wagons w 
                 JOIN tracks t ON w.track_id = t.id 
                 WHERE w.status != 'departed' AND w.is_archived = 0 
                 ORDER BY t.id, w.start_pos""")
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
    """Возвращает сгруппированную историю активных вагонов."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT m.id, m.wagon_number, m.action_type, m.from_track, m.to_track, m.note, m.timestamp, w.owner, w.organization, w.cargo_type 
                 FROM movement_history m 
                 LEFT JOIN wagons w ON m.wagon_number = w.wagon_number 
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
    """Возвращает сгруппированную историю архивированных вагонов."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT a.wagon_number, a.action_type, a.from_track, a.to_track, a.note, a.timestamp, w.owner, w.organization, w.cargo_type 
                 FROM archived_history a 
                 LEFT JOIN wagons w ON a.wagon_number = w.wagon_number 
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