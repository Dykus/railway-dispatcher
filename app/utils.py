# app/utils.py
# -*- coding: utf-8 -*-
"""
Вспомогательные функции: очистка строк, работа с IP и ролями, логирование, парсинг дат,
а также функции для работы с московским временем и миграцией.
"""

import re
import sqlite3
from datetime import datetime, timedelta
from flask import request, g

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_NAME, RETURN_TRACK_NAMES


# ==================== КОНСТАНТЫ ДЛЯ ВРЕМЕНИ ====================
# Московское время – UTC+3 (фиксировано)
MOSCOW_OFFSET = 3
# Для миграции: старые данные хранились в новокузнецком времени (UTC+7)
# значит, их нужно перевести в московское, вычтя 4 часа.
OLD_LOCAL_OFFSET = 7  # Новокузнецк UTC+7
NEW_MSK_OFFSET = 3    # Москва UTC+3
MIGRATION_SUBTRACT_HOURS = OLD_LOCAL_OFFSET - NEW_MSK_OFFSET  # = 4


def get_moscow_now():
    """
    Возвращает текущее московское время (UTC+3).
    Не зависит от системного часового пояса сервера.
    """
    # Получаем текущее UTC время и прибавляем 3 часа
    utc_now = datetime.utcnow()
    msk_now = utc_now + timedelta(hours=MOSCOW_OFFSET)
    # Обрезаем микросекунды для согласованности с БД
    return msk_now.replace(microsecond=0)


def local_to_moscow(dt_str, from_offset=MIGRATION_SUBTRACT_HOURS):
    """
    Преобразует строку даты/времени из местного (новокузнецкого) времени
    в московское, вычитая указанное количество часов.
    Используется для одноразовой миграции старых записей в БД.
    """
    if not dt_str:
        return None
    try:
        # Парсим строку формата 'YYYY-MM-DD HH:MM:SS'
        dt = datetime.strptime(dt_str[:19], '%Y-%m-%d %H:%M:%S')
        new_dt = dt - timedelta(hours=from_offset)
        return new_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return dt_str  # если не распарсилось, возвращаем как есть


def moscow_to_local(dt_str, to_offset=MIGRATION_SUBTRACT_HOURS):
    """
    Преобразует строку даты из московского времени в местное (прибавляя часы).
    Может пригодиться в будущем, если понадобится обратная миграция.
    """
    if not dt_str:
        return None
    try:
        dt = datetime.strptime(dt_str[:19], '%Y-%m-%d %H:%M:%S')
        new_dt = dt + timedelta(hours=to_offset)
        return new_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return dt_str


# ==================== ОСТАЛЬНЫЕ СУЩЕСТВУЮЩИЕ ФУНКЦИИ ====================
# (они остаются без изменений, только добавлены импорты выше)

def get_conn():
    """Возвращает соединение с базой данных."""
    return sqlite3.connect(DB_NAME, timeout=10, check_same_thread=False)


def is_return_track(track_name):
    """Проверяет, является ли путь возвратным."""
    return any(rt in track_name for rt in RETURN_TRACK_NAMES)


def clean_note_for_db(note):
    """Очищает примечание от HTML-тегов и лишних пробелов."""
    if not note:
        return ""
    clean = re.sub('<[^<]+?>', '', str(note))
    clean = clean.replace('\n', ' ').replace('\r', ' ')
    return ' '.join(clean.split()).strip()


def get_user_by_ip(ip):
    """Возвращает (username, role, access_allowed) по IP."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username, role, access_allowed FROM ip_users WHERE ip_address = ?", (ip,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], row[1], bool(row[2])
    return None, None, False


def is_ip_allowed(ip):
    """Проверяет, разрешён ли доступ для IP."""
    if ip in ('127.0.0.1', '::1'):
        return True
    _, _, allowed = get_user_by_ip(ip)
    return allowed


def get_role_by_ip(ip):
    """Возвращает роль пользователя по IP."""
    if ip in ('127.0.0.1', '::1'):
        return 'admin'
    _, role, _ = get_user_by_ip(ip)
    return role if role else 'viewer'


def get_username_by_ip(ip):
    """Возвращает имя пользователя по IP (для логирования)."""
    if ip in ('127.0.0.1', '::1'):
        return "admin"
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username FROM ip_users WHERE ip_address = ?", (ip,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return ip


def log_action(action, wagon_number=None, details=None, old_value=None, new_value=None, station_id=None):
    """Записывает действие в журнал action_log."""
    try:
        if request:
            ip = request.remote_addr
            username = get_username_by_ip(ip)
        else:
            ip = '127.0.0.1'
            username = 'system'
    except RuntimeError:
        ip = '127.0.0.1'
        username = 'system'

    # Если station_id не передан, берём из контекста g
    if station_id is None:
        try:
            station_id = g.get('station_id', 1)
        except RuntimeError:
            station_id = 1

    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute('''INSERT INTO action_log 
            (timestamp, username, ip_address, action, wagon_number, details, old_value, new_value, station_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             username, ip, action, wagon_number, details, old_value, new_value, station_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


def parse_flexible_date(date_str):
    """Парсит дату из строки, поддерживая разные форматы."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
                '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%d-%m-%Y',
                '%d.%m.%Y %H:%M:%S', '%d.%m.%Y %H:%M', '%d.%m.%Y'):
        try:
            return datetime.strptime(date_str, fmt)
        except:
            pass
    digits = re.sub(r'\D', '', date_str)
    if len(digits) == 12:
        try:
            day = int(digits[0:2]); month = int(digits[2:4]); year = int(digits[4:8])
            hour = int(digits[8:10]); minute = int(digits[10:12])
            return datetime(year, month, day, hour, minute)
        except:
            pass
    if len(digits) == 8:
        try:
            day = int(digits[0:2]); month = int(digits[2:4]); year = int(digits[4:8])
            return datetime(year, month, day)
        except:
            pass
    raise ValueError(f"Не удалось распознать дату: {date_str}")


def format_date(dt_str):
    """Форматирует дату для отображения (ДД.ММ.ГГГГ ЧЧ:ММ)."""
    if not dt_str:
        return "-"
    try:
        return datetime.strptime(str(dt_str)[:16], '%Y-%m-%d %H:%M').strftime('%d.%m.%Y %H:%M')
    except:
        return str(dt_str)[:19]