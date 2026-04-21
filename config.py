# -*- coding: utf-8 -*-
"""
Конфигурация приложения «ЖД Диспетчерская».
Все пути, версия и настройки хранятся здесь.
"""

import os
import sys

# ==================== ПУТИ (ВАЖНО ДЛЯ EXE) ====================
def get_base_dir():
    """Определяет базовую директорию (работает и в .py, и в .exe)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    """Возвращает путь к неизменяемому ресурсу внутри EXE или рядом с .py."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

BASE_DIR = get_base_dir()
DB_NAME = os.path.join(BASE_DIR, 'rail_yard_v4.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
CHANGELOG_PATH = get_resource_path('CHANGELOG.txt')

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# ==================== НАСТРОЙКИ РЕЗЕРВНОГО КОПИРОВАНИЯ ====================
BACKUP_HOUR = 3
BACKUP_KEEP_COUNT = 30

# ==================== ПРОЧИЕ КОНСТАНТЫ ====================
APP_VERSION = "4.1.0"
RETURN_TRACK_NAMES = ["Пост №2", "Ст. Черкасов Камень"]

SECRET_KEY = 'rail_app_secret_key_change_me'

SERVER_IP = None