# -*- coding: utf-8 -*-
"""
Вспомогательные функции: очистка строк, работа с IP и ролями, логирование, парсинг дат.
"""

import re
import sqlite3
from datetime import datetime
from flask import request

# Импортируем конфигурацию
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_NAME, RETURN_TRACK_NAMES


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


def log_action(action, wagon_number=None, details=None, old_value=None, new_value=None):
    """Записывает действие в журнал action_log."""
    try:
        # Если функция вызвана не из контекста запроса (например, при автоматическом бэкапе),
        # используем системные значения.
        if request:
            ip = request.remote_addr
            username = get_username_by_ip(ip)
        else:
            ip = '127.0.0.1'
            username = 'system'
    except RuntimeError:
        ip = '127.0.0.1'
        username = 'system'

    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute('''INSERT INTO action_log 
            (timestamp, username, ip_address, action, wagon_number, details, old_value, new_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             username, ip, action, wagon_number, details, old_value, new_value))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


def parse_flexible_date(date_str):
    """Парсит дату из строки, поддерживая разные форматы."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    # Популярные форматы
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
                '%d-%m-%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%d-%m-%Y',
                '%d.%m.%Y %H:%M:%S', '%d.%m.%Y %H:%M', '%d.%m.%Y'):
        try:
            return datetime.strptime(date_str, fmt)
        except:
            pass
    # Если не получилось, пробуем по цифрам (ДДММГГГГ и т.п.)
    digits = re.sub(r'\D', '', date_str)
    if len(digits) == 12:  # ДДММГГГГЧЧММ
        try:
            day = int(digits[0:2]); month = int(digits[2:4]); year = int(digits[4:8])
            hour = int(digits[8:10]); minute = int(digits[10:12])
            return datetime(year, month, day, hour, minute)
        except:
            pass
    if len(digits) == 8:  # ДДММГГГГ
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