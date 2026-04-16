# -*- coding: utf-8 -*-
"""
Точка входа в приложение «ЖД Диспетчерская».
Запускает Flask-сервер и иконку в системном трее.
"""

import os
import sys
import threading
import webbrowser
import logging
from logging.handlers import RotatingFileHandler

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from config import BASE_DIR, APP_VERSION

# Глобальная переменная для IP сервера
SERVER_IP = None

# Попытка импорта pystray для иконки в трее
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    print("Для работы иконки в трее установите: pip install pystray pillow")


def create_tray_icon():
    """Создаёт и запускает иконку в системном трее."""
    if not HAS_TRAY:
        return

    # Определяем, где искать иконку
    if getattr(sys, 'frozen', False):
        # Запущено как EXE – ищем внутри _MEIPASS
        base_path = sys._MEIPASS
    else:
        base_path = BASE_DIR

    # Пытаемся загрузить иконку из файла
    img = None
    icon_path = None
    for ext in ['.ico', '.png']:
        test_path = os.path.join(base_path, f'icon{ext}')
        if os.path.exists(test_path):
            icon_path = test_path
            break

    if icon_path:
        try:
            img = Image.open(icon_path)
            # Приводим к размеру 64x64
            img = img.resize((64, 64), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
        except Exception as e:
            logging.warning(f"Не удалось загрузить иконку из {icon_path}: {e}")
            img = None

    # Если иконку не удалось загрузить, рисуем стандартную
    if img is None:
        logging.info("Иконка не найдена, используется стандартная (рисованная)")
        img = Image.new('RGB', (64, 64), color='#2c3e50')
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 50), (64, 58)], fill='#7f8c8d')
        draw.rectangle([(0, 55), (64, 60)], fill='#95a5a6')
        draw.rectangle([(10, 30), (54, 48)], fill='#e74c3c', outline='white', width=1)
        draw.ellipse([(16, 45), (24, 53)], fill='#2c3e50', outline='white', width=1)
        draw.ellipse([(40, 45), (48, 53)], fill='#2c3e50', outline='white', width=1)
        draw.rectangle([(14, 34), (22, 42)], fill='#3498db')
        draw.rectangle([(26, 34), (34, 42)], fill='#3498db')
        draw.rectangle([(38, 34), (46, 42)], fill='#3498db')
        draw.rectangle([(12, 28), (52, 32)], fill='#c0392b')
        draw.ellipse([(48, 20), (56, 28)], fill='#bdc3c7')
        draw.ellipse([(52, 14), (60, 22)], fill='#bdc3c7')

    def on_open(icon, item):
        webbrowser.open('http://127.0.0.1:5000')

    def on_quit(icon, item):
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("🚂 Открыть", on_open),
        pystray.MenuItem("❌ Выход", on_quit)
    )
    icon = pystray.Icon("railway_dispatcher", img, "ЖД Диспетчерская", menu)
    icon.run()


def setup_logging():
    """Настраивает подробное логирование в файл с ротацией."""
    log_file = os.path.join(BASE_DIR, 'railway_dispatcher.log')

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    if not getattr(sys, 'frozen', False):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('flask').setLevel(logging.INFO)


def print_startup_info():
    """Выводит информацию о запуске (через логгер)."""
    logging.info("=" * 50)
    logging.info(f"🚂 ЖД Диспетчерская запущена (версия {APP_VERSION})")
    logging.info("=" * 50)
    logging.info(f"📁 База данных: {os.path.join(BASE_DIR, 'rail_yard.db')}")
    logging.info(f"🌐 Локальный адрес: http://127.0.0.1:5000")
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        logging.info(f"🌐 Сетевой адрес: http://{local_ip}:5000")
        global SERVER_IP
        SERVER_IP = local_ip
    except:
        logging.info("🌐 Сетевой адрес: не удалось определить")
    logging.info("=" * 50)
    logging.info("Для остановки нажмите Ctrl+C или используйте иконку в трее")
    logging.info("=" * 50)


if __name__ == '__main__':
    # --- Проверка единственного экземпляра приложения ---
    try:
        import win32event
        import win32api
        import winerror

        mutex_name = "RailwayDispatcher_App_Mutex"
        mutex = win32event.CreateMutex(None, False, mutex_name)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            # Приложение уже запущено
            print("Программа уже запущена. Второй экземпляр не может быть запущен.")
            sys.exit(1)
    except ImportError:
        # Если pywin32 не установлен, пропускаем проверку (только для разработки)
        logging.warning("pywin32 не установлен, проверка единственного экземпляра отключена.")
    # ------------------------------------------------------

    # Настройка логирования
    setup_logging()

    # Создаём приложение
    app = create_app()

    # Выводим стартовую информацию (попадёт в лог)
    print_startup_info()

    # Запускаем сервер в отдельном потоке
    server_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False),
        daemon=True
    )
    server_thread.start()

    # Запускаем иконку в трее или просто ждём
    if HAS_TRAY:
        create_tray_icon()
    else:
        logging.warning("Иконка в трее не доступна. Для выхода нажмите Ctrl+C")
        server_thread.join()