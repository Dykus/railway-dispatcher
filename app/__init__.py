# -*- coding: utf-8 -*-
"""
Инициализация Flask-приложения «ЖД Диспетчерская».
"""

from flask import Flask, request, jsonify
import os
import sys
from datetime import datetime, timedelta

# Добавляем корневую директорию в путь для импорта config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SECRET_KEY, APP_VERSION, DB_NAME, BACKUP_DIR
from app.models import init_db, clean_action_log, get_last_auto_backup_time, create_auto_backup, schedule_daily_backup
from app.utils import is_ip_allowed, get_role_by_ip

def create_app():
    """Создаёт и настраивает Flask-приложение."""
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    # Инициализация БД и фоновых задач
    init_db()
    clean_action_log()

    last_auto = get_last_auto_backup_time()
    if last_auto is None or (datetime.now() - last_auto) > timedelta(days=1):
        print("📦 Создание автоматического бэкапа при запуске (прошло более суток)...")
        create_auto_backup()
    schedule_daily_backup()

    # Глобальная проверка доступа (before_request)
    @app.before_request
    def before_request_check():
        if request.endpoint in ('static',):
            return
        ip = request.remote_addr

        # Определяем роль и проверяем доступ
        allowed, role, msg = check_access_for_route(ip, request.endpoint)
        if not allowed:
            if request.path.startswith('/api/'):
                return jsonify({"error": msg}), 403
            else:
                return f"<html><body><h1>403 Доступ запрещён</h1><p>{msg}</p><p>Ваш IP: {ip}</p><p><a href='/'>На главную</a></p></body></html>", 403
        request.user_role = role

    def check_access_for_route(ip, endpoint):
        """Внутренняя функция проверки прав доступа."""
        # Локальный хост всегда админ
        if ip in ('127.0.0.1', '::1'):
            role = 'admin'
        else:
            if not is_ip_allowed(ip):
                return False, None, "Доступ запрещён: ваш IP не внесён в белый список."
            role = get_role_by_ip(ip)
            if not role:
                role = 'viewer'

        # Списки эндпоинтов (учитываем Blueprints)
        public_endpoints = [
            'main.index', 'history.history_page', 'history.archive_page', 'help_page',
            'api.api_status', 'api.get_wagon_info', 'api.api_dashboard_data', 'static',
            'export.export_excel', 'export.export_history_excel', 'export.export_archive_excel',
            'export.export_wagon_history', 'export.export_wagon_archive'
        ]
        dispatcher_endpoints = ['main.add_wagon', 'main.move_action', 'main.depart_action']
        supervisor_endpoints = ['admin.edit_wagon_route', 'admin.edit_history']
        admin_endpoints = [
            'admin.create_backup', 'admin.list_backups', 'admin.download_backup', 'admin.restore_backup',
            'admin.view_logs', 'admin.export_logs_excel', 'admin.manage_ip_users', 'admin.changelog'
        ]

        if endpoint in public_endpoints:
            return True, role, None
        elif endpoint in dispatcher_endpoints:
            if role in ('dispatcher', 'admin', 'supervisor'):
                return True, role, None
            else:
                return False, role, "Недостаточно прав. Требуется роль диспетчера или выше."
        elif endpoint in supervisor_endpoints:
            if role in ('supervisor', 'admin'):
                return True, role, None
            else:
                return False, role, "Недостаточно прав. Требуется роль супервизора или администратора."
        elif endpoint in admin_endpoints:
            if role == 'admin':
                return True, role, None
            else:
                return False, role, "Доступ только для администратора."
        else:
            # Если эндпоинт не найден в списках, разрешаем только админу (для безопасности)
            if role == 'admin':
                return True, role, None
            else:
                return False, role, "Маршрут не доступен."

    # Импортируем и регистрируем Blueprints
    from app.routes.main import main_bp
    from app.routes.history import history_bp
    from app.routes.api import api_bp
    from app.routes.export import export_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(api_bp)          # префикс /api задан в Blueprint
    app.register_blueprint(export_bp)
    app.register_blueprint(admin_bp)        # префикс /admin задан в Blueprint

    return app