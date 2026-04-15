# -*- coding: utf-8 -*-
"""
Конфигурация приложения «ЖД Диспетчерская».
Все пути, версия и настройки хранятся здесь.
"""

import os
import sys

# ==================== ПУТИ (ВАЖНО ДЛЯ EXE) ====================
def get_base_dir():
    """Определяет базовую директорию (работает и в .py, и в .exe)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
DB_NAME = os.path.join(BASE_DIR, 'rail_yard.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
CHANGELOG_PATH = os.path.join(BASE_DIR, 'CHANGELOG.txt')

# Убедимся, что папка для бэкапов существует
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# ==================== НАСТРОЙКИ РЕЗЕРВНОГО КОПИРОВАНИЯ ====================
BACKUP_HOUR = 3
BACKUP_KEEP_COUNT = 30

# ==================== ПРОЧИЕ КОНСТАНТЫ ====================
APP_VERSION = "3.0.1"
RETURN_TRACK_NAMES = ["Пост №2", "Ст. Черкасов Камень"]

# Секретный ключ Flask (в реальном проекте лучше брать из переменных окружения)
SECRET_KEY = 'rail_app_secret_key_change_me'

# IP сервера (будет определён при запуске)
SERVER_IP = None