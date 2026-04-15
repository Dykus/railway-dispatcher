# -*- coding: utf-8 -*-
"""
Конфигурация приложения «ЖД Диспетчерская».
Все пути, версия и настройки хранятся здесь.
"""

import os
import sys

# ==================== ПУТИ (ВАЖНО ДЛЯ EXE) ====================
def get_base_dir():
    """Определяет базовую директорию (работает и в .py, и в .exe).
       Используется для изменяемых файлов: БД, бэкапы, логи."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    """Возвращает путь к неизменяемому ресурсу внутри EXE или рядом с .py."""
    if getattr(sys, 'frozen', False):
        # В EXE ресурсы распакованы во временную папку _MEIPASS
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

BASE_DIR = get_base_dir()
DB_NAME = os.path.join(BASE_DIR, 'rail_yard.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
# CHANGELOG теперь внутри EXE (или рядом с .py)
CHANGELOG_PATH = get_resource_path('CHANGELOG.txt')

# Убедимся, что папка для бэкапов существует
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# ==================== НАСТРОЙКИ РЕЗЕРВНОГО КОПИРОВАНИЯ ====================
BACKUP_HOUR = 3
BACKUP_KEEP_COUNT = 30

# ==================== ПРОЧИЕ КОНСТАНТЫ ====================
APP_VERSION = "3.0.2"
RETURN_TRACK_NAMES = ["Пост №2", "Ст. Черкасов Камень"]

# Секретный ключ Flask
SECRET_KEY = 'rail_app_secret_key_change_me'

# IP сервера (будет определён при запуске)
SERVER_IP = None