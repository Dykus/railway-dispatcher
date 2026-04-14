# -*- coding: utf-8 -*-
"""
Точка входа в приложение «ЖД Диспетчерская».
Запускает Flask-сервер и (опционально) иконку в системном трее.
"""

import os
import sys
import threading
import webbrowser
from datetime import datetime, timedelta

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from config import BASE_DIR, APP_VERSION

# Глобальная переменная для IP сервера (будет определена позже)
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

    icon_path = None
    for ext in ['.png', '.ico']:
        test_path = os.path.join(BASE_DIR, f'icon{ext}')
        if os.path.exists(test_path):
            icon_path = test_path
            break

    if icon_path:
        try:
            img = Image.open(icon_path)
            img = img.resize((64, 64), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
        except:
            img = None

    if not icon_path or img is None:
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

def print_startup_info():
    """Выводит информацию о запуске в консоль."""
    print("=" * 50)
    print(f"🚂 ЖД Диспетчерская запущена (версия {APP_VERSION})")
    print("=" * 50)
    print(f"📁 База данных: {os.path.join(BASE_DIR, 'rail_yard.db')}")
    print(f"🌐 Локальный адрес: http://127.0.0.1:5000")
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"🌐 Сетевой адрес: http://{local_ip}:5000")
        global SERVER_IP
        SERVER_IP = local_ip
    except:
        print("🌐 Сетевой адрес: не удалось определить")
    print("=" * 50)
    print("Для остановки нажмите Ctrl+C или используйте иконку в трее")
    print("=" * 50)

if __name__ == '__main__':
    # Создаём приложение
    app = create_app()

    # Выводим стартовую информацию
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
        print("Иконка в трее не доступна. Для выхода нажмите Ctrl+C")
        server_thread.join()