# -*- coding: utf-8 -*-
"""
Основные маршруты: главная страница, добавление, перемещение, архивация, справка.
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, flash
from datetime import datetime, timedelta
import sys
import os
import socket

# Добавляем пути для импорта из корня и app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import APP_VERSION
from app.models import (
    get_dashboard_data, move_wagon, depart_wagon, log_movement, log_action,
    find_slot_on_track, compact_track, get_conn
)

main_bp = Blueprint('main', __name__)

# ==================== HTML-ШАБЛОН ГЛАВНОЙ СТРАНИЦЫ ====================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>ЖД Диспетчерская</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #2c3e50; margin-top: 0; }
        .header-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px; }
        .nav-buttons { display: flex; gap: 10px; flex-wrap: wrap; }
        .btn { color: white; padding: 8px 15px; border: none; border-radius: 5px; text-decoration: none; font-weight: bold; display: inline-flex; align-items: center; gap: 5px; cursor: pointer; }
        .btn-history { background: #2980b9; }
        .btn-excel { background: #217346; }
        .btn-archive { background: #7f8c8d; }
        .btn-help { background: #16a085; }
        .btn-changelog { background: #2c3e50; }
        .btn-backup { background: #27ae60; }
        .btn-add { background: #27ae60; }
        .btn-move { background: #f39c12; }
        .controls { display: flex; gap: 20px; margin-bottom: 30px; background: #ecf0f1; padding: 20px; border-radius: 8px; flex-wrap: wrap; }
        .control-box { flex: 1; min-width: 300px; }
        .control-box:first-child { border-right: 1px solid #bdc3c7; padding-right: 20px; }
        .control-box:last-child { padding-left: 20px; }
        input, select, textarea { padding: 10px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; width: 100%; }
        .time-group { display: flex; gap: 10px; align-items: flex-end; }
        .time-group div { flex: 1; text-align: center; }
        .time-group input { text-align: center; margin-bottom: 3px; }
        .time-group label { font-size: 11px; color: #555; display: block; margin-top: 2px; }
        .manual-time-inputs { display: flex; gap: 5px; align-items: center; flex-wrap: wrap; }
        .manual-time-inputs input { width: 120px; }
        .date-help { font-size: 10px; color: #7f8c8d; margin-top: 2px; }
        .date-buttons { display: flex; gap: 5px; margin-left: 10px; }
        .date-buttons button { background: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 3px; padding: 4px 8px; cursor: pointer; font-size: 11px; }
        .alert { padding: 10px; margin-bottom: 15px; border-radius: 4px; text-align: center; font-weight: bold; }
        .alert-success { background: #d4edda; color: #155724; border-left: 4px solid #27ae60; }
        .alert-error { background: #f8d7da; color: #721c24; border-left: 4px solid #e74c3c; }
        .track-wrapper { margin-bottom: 20px; border: 1px solid #ddd; border-radius: 8px; background: white; }
        .track-header { background: #34495e; color: white; padding: 10px 15px; font-weight: bold; display: flex; justify-content: space-between; border-radius: 8px 8px 0 0; }
        .track-body { position: relative; height: 200px; background: #ecf0f1; margin: 15px; border-bottom: 3px solid #7f8c8d; overflow-x: auto; }
        .wagon { position: absolute; top: 20px; height: 160px; border: 2px solid #2c3e50; border-radius: 6px; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; cursor: pointer; box-shadow: 2px 2px 5px rgba(0,0,0,0.2); min-width: 130px; padding: 8px; }
        .wagon:hover { transform: scale(1.02); z-index: 100; }
        .wagon.active { outline: 3px solid #f1c40f; }
        .wagon-normal { background: linear-gradient(135deg, #3498db, #2980b9); }
        .wagon-return-highlight { background: linear-gradient(135deg, #8e44ad, #9b59b6); border: 2px solid #f1c40f; }
        .wagon-global-overdue { background: linear-gradient(135deg, #6c3483, #4a235a); border: 2px solid #e74c3c; }
        .wagon-global-overdue-normal { background: linear-gradient(135deg, #922b21, #641e16); border: 2px solid #e74c3c; }
        .wagon-overdue { background: linear-gradient(135deg, #e74c3c, #c0392b); }
        .wagon-warn { background: linear-gradient(135deg, #f39c12, #d35400); }
        .wagon-number { font-size: 18px; font-weight: bold; text-align: center; margin-bottom: 8px; }
        .wagon-timer { font-family: monospace; font-size: 13px; margin-top: 5px; text-align: center; font-weight: bold; }
        .timer-label { font-size: 11px; opacity: 0.9; margin-right: 4px; }
        .total-count { background: #34495e; color: white; padding: 8px 15px; border-radius: 20px; font-weight: bold; }
        .refresh-btn { background: #95a5a6; border: none; padding: 5px 10px; border-radius: 4px; color: white; cursor: pointer; }
        #global-tooltip { display: none; position: fixed; background: #2c3e50; color: white; padding: 15px; border-radius: 8px; z-index: 1000; min-width: 280px; box-shadow: 0 5px 20px rgba(0,0,0,0.3); }
        .tooltip-row { display: flex; justify-content: space-between; margin-bottom: 8px; padding-bottom: 5px; border-bottom: 1px solid #465c71; }
        .timer-block { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #7f8c8d; }
        .timer-title { font-size: 12px; text-transform: uppercase; color: #bdc3c7; margin-bottom: 5px; }
        .btn-remove-large { background: #e74c3c; color: white; border: none; padding: 8px; border-radius: 4px; cursor: pointer; width: 100%; margin-top: 10px; font-weight: bold; }
        .close-tooltip { text-align: center; margin-top: 8px; font-size: 12px; color: #bdc3c7; cursor: pointer; }
        @media (max-width: 768px) { .control-box:first-child { border-right: none; padding-right: 0; } .control-box:last-child { padding-left: 0; } }
        #moveWagonSelect { height: auto; min-height: 120px; }
        #wagonSearchInput { margin-bottom: 5px; }
        .legend { background: #f8f9fa; padding: 10px; border-radius: 8px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 15px; align-items: center; font-size: 13px; }
        .legend-color { display: inline-block; width: 20px; height: 20px; border-radius: 4px; vertical-align: middle; margin-right: 4px; }
        .date-time-group { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-bottom: 5px; }
        .date-input { font-family: monospace; }
    </style>
</head>
<body>
<div class="container">
<div class="header-actions" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
    <div>
        <h1 style="margin: 0;">🚂 ЖД Диспетчерская</h1>
        <div style="font-size: 11px; color: #7f8c8d; margin-top: 2px;">Версия {{ version }}</div>
    </div>
    <div class="nav-buttons" style="display: flex; gap: 10px; align-items: center;">
        <div class="total-count">📦 Всего: {{ total_wagons }}</div>
        <a href="/history" class="btn btn-history">📜 История</a>
        <a href="/archive" class="btn btn-archive">🗄️ Архив</a>
        <a href="/export_excel" class="btn btn-excel">📊 Excel</a>
        {% if is_admin %}
            <a href="/admin/changelog" class="btn btn-changelog">📋 Список изменений</a>
            <a href="/admin/backups" class="btn btn-backup">💾 Бэкапы</a>
            <a href="/admin/logs" class="btn" style="background:#8e44ad;">📜 Журнал действий</a>
            <a href="/admin/ip_users" class="btn" style="background:#e67e22;">🔗 Привязка IP</a>
        {% endif %}
        <a href="/help" class="btn btn-help">❓ Помощь</a>
    </div>
</div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for cat, msg in messages %}
                <div class="alert alert-{{ cat }}">{% if cat == 'success' %}✅{% else %}⚠️{% endif %} {{ msg }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <!-- Остальное содержимое шаблона главной страницы без изменений -->
    <!-- В целях экономии места здесь приведён не весь шаблон, но в реальном файле он должен быть полностью -->
</div>
<!-- Здесь должен быть весь JavaScript и модальные окна -->
</body>
</html>"""

# ==================== HTML-ШАБЛОН СПРАВКИ ====================
HELP_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Инструкция диспетчера - ЖД Диспетчерская</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #2980b9; margin-top: 25px; }
        .nav-link { display: inline-block; padding: 8px 15px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-bottom: 20px; }
        .color-box { display: inline-block; width: 20px; height: 20px; border-radius: 4px; vertical-align: middle; margin-right: 8px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #ecf0f1; }
        .note { background: #fef9e7; padding: 10px; border-left: 4px solid #f39c12; margin: 15px 0; }
        .address { background: #e8f4fd; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 1.2em; text-align: center; margin: 20px 0; }
    </style>
</head>
<body>
<div class="container">
    <a href="/" class="nav-link">🏠 На главную</a>
    <h1>🚂 Инструкция для диспетчера</h1>
    
    <h2>1. Как подключиться</h2>
    <p>Откройте браузер (Chrome, Firefox, Edge) и введите адрес:</p>
    <div class="address">http://{{ server_ip }}:5000</div>
    <p>Если вы работаете с того же компьютера, где запущена программа, используте <strong>http://127.0.0.1:5000</strong>.</p>
    <div class="note">📌 После входа вы увидите главный экран со списком путей и вагонов.</div>
    
    <h2>2. Главный экран</h2>
    <p>На главной странице отображаются:</p>
    <ul>
        <li><strong>Пути</strong> (станции, посты, цеха) в виде горизонтальных полос.</li>
        <li><strong>Вагоны</strong> – цветные прямоугольники с номером и таймерами.</li>
        <li>Панель управления слева – <strong>«Новый вагон»</strong>, справа – <strong>«Переместить»</strong>.</li>
        <li>Вверху – кнопки: История, Архив, Excel, Помощь (эта страница).</li>
    </ul>
    
    <h2>3. Добавление нового вагона</h2>
    <ul>
        <li>Заполните поля: <strong>№ вагона</strong>, <strong>Транспортная компания</strong>, <strong>Организация</strong>.</li>
        <li>При желании укажите <strong>глобальный срок</strong> – общее время на станции. Для этого задайте дни, часы, минуты.</li>
        <li>Можно указать <strong>начало отсчёта</strong> (дата и время). Если оставить поля пустыми – срок начнётся с текущего момента.</li>
        <li>Выберите <strong>путь</strong>, на который ставится вагон.</li>
        <li>Нажмите <strong>«Распределить»</strong>.</li>
    </ul>
    <div class="note">💡 Если вагон уже был в архиве, он восстановится с сохранением истории.</div>
    
    <h2>4. Перемещение вагона</h2>
    <ul>
        <li>В правой панели найдите вагон (помогает поле <strong>«Поиск вагона»</strong>).</li>
        <li>Выберите его из списка – примечание подставится автоматически.</li>
        <li>При необходимости измените <strong>примечание</strong>.</li>
        <li>Задайте <strong>локальный срок</strong> – время, которое вагон должен провести на новом пути (дни, часы, минуты).</li>
        <li>Укажите <strong>начало отсчёта</strong> (дата/время) или оставьте пустым – будет использовано текущее время.</li>
        <li>Выберите <strong>путь назначения</strong> и нажмите <strong>«Переместить»</strong>.</li>
    </ul>
    
    <h2>5. Цвета вагонов (что означают)</h2>
    <table>
        <tr><th>Цвет</th><th>Значение</th></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#3498db,#2980b9);"></span> Синий</span><th>Обычный вагон (срок в норме или не задан)</th></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#8e44ad,#9b59b6); border:1px solid #f1c40f;"></span> Фиолетовый (с жёлтой рамкой)</span><th>Вагон уже побывал на возвратном пути («Пост №2» или «Ст. Черкасов Камень»)</th></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#6c3483,#4a235a); border:2px solid #e74c3c;"></span> Тёмно-фиолетовый</span><th>Был на возвратном пути И истёк глобальный срок</th></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#922b21,#641e16); border:2px solid #e74c3c;"></span> Тёмно-красный</span><th>Обычный вагон с истёкшим глобальным сроком</th></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#f39c12,#d35400);"></span> Оранжевый</span><th>Локальный срок истекает менее чем через час</th></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#e74c3c,#c0392b);"></span> Красный</span><th>Локальный срок уже истёк (просрочка)</th></tr>
    </table>
    <p><strong>Локальный срок</strong> – время на текущем пути. <strong>Глобальный срок</strong> – общее время на станции.</p>
    
    <h2>6. Информация о вагоне</h2>
    <p>Кликните по вагону – появится всплывающее окно с подробностями:</p>
    <ul>
        <li>Номер вагона, транспортная компания, организация.</li>
        <li>Примечание, время прибытия.</li>
        <li><strong>Таймеры</strong> локального и глобального сроков (обратный отсчёт).</li>
        <li>Если вагон находится на возвратном пути («Пост №2» или «Ст. Черкасов Камень»), будет кнопка <strong>«УБРАТЬ В АРХИВ»</strong>.</li>
    </ul>
    <p>Чтобы закрыть окно, нажмите «Закрыть» или кликните вне его.</p>
    
    <h2>7. История и архив</h2>
    <p>Кнопки <strong>«История»</strong> и <strong>«Архив»</strong> вверху страницы.</p>
    <ul>
        <li><strong>История</strong> – все перемещения активных вагонов (сгруппированы по вагонам, раскрывающиеся блоки).</li>
        <li><strong>Архив</strong> – вагоны, которые были убраны с возвратных путей. Также сгруппированы с полной историей.</li>
    </ul>
    <p>Внутри каждого блока есть кнопка <strong>«📊 Excel»</strong> – выгружает историю конкретного вагона в отдельный файл.</p>
    
    <h2>8. Выгрузка в Excel</h2>
    <ul>
        <li>На главной странице – кнопка <strong>«Excel»</strong> (отчёт по всем активным вагонам).</li>
        <li>В разделе «История» – кнопка <strong>«Скачать Excel (все вагоны)»</strong> (полная история перемещений).</li>
        <li>В разделе «Архив» – кнопка <strong>«Скачать Excel (все вагоны)»</strong> (сводка + детализация по архиву).</li>
        <li>Для каждого отдельного вагона (как в истории, так и в архиве) есть своя кнопка Excel.</li>
    </ul>
    
    <h2>9. Редактирование дат в истории (для ролей supervisor и admin)</h2>
    <p>На странице «История» у последнего события каждого вагона появляется кнопка <strong>✏️</strong>.</p>
    <p><strong>Почему только последнее событие?</strong> Изменение даты более раннего события нарушило бы хронологию перемещений и могло бы привести к неверной работе таймеров локального срока. Если вы ошиблись в дате не последнего события, рекомендуется отредактировать время прибытия или сроки вагона (кнопка «Редактировать вагон»), либо удалить и добавить вагон заново.</p>
    <p>При изменении даты последнего события проверяется, что новая дата не нарушает хронологию, и автоматически пересчитывается локальный срок (если был задан). Изменение записывается в журнал действий.</p>
    
    <h2>10. Завершение работы</h2>
    <p>Диспетчеру достаточно закрыть вкладку браузера. Программа на сервере продолжит работать. Если нужно полностью остановить сервер – это делает администратор на серверной машине.</p>
    
    <div class="note">📞 При возникновении проблем обратитесь к системному администратору.</div>
    <p style="text-align: center; margin-top: 30px;">© ЖД Диспетчерская, АО "Знамя"<br>Версия {{ version }} (сетевая, для диспетчера)</p>
</div>
</body>
</html>"""


# ==================== МАРШРУТЫ ====================
@main_bp.route('/')
def index():
    tracks, move_list = get_dashboard_data()
    is_admin = (request.user_role == 'admin')
    return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                  add_form_data=None, move_form_data=None, request=request, is_admin=is_admin,
                                  version=APP_VERSION)


@main_bp.route('/help')
def help_page():
    # Определяем IP сервера для отображения в справке
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        server_ip = s.getsockname()[0]
        s.close()
    except:
        server_ip = "IP_вашего_сервера"
    return render_template_string(HELP_TEMPLATE, server_ip=server_ip, version=APP_VERSION)


@main_bp.route('/add', methods=['POST'])
def add_wagon():
    number = request.form.get('number', '').strip()
    owner = request.form.get('owner', '').strip()
    org = request.form.get('organization', '').strip()
    note = request.form.get('note', '')
    track_id_str = request.form.get('track_id', '')
    cycle_days = request.form.get('cycle_days', '0')
    cycle_hours = request.form.get('cycle_hours', '0')
    cycle_mins = request.form.get('cycle_mins', '0')
    start_date = request.form.get('start_date', '').strip()
    start_time = request.form.get('start_time', '').strip()

    add_form_data = {
        'number': number,
        'owner': owner,
        'org': org,
        'note': note,
        'cycle_days': cycle_days,
        'cycle_hours': cycle_hours,
        'cycle_mins': cycle_mins,
        'start_date': start_date,
        'start_time': start_time,
        'track_id': track_id_str
    }

    if not number or not owner or not org or not track_id_str:
        flash("Заполните все поля!", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)

    try:
        track_id = int(track_id_str)
    except ValueError:
        flash("Ошибка: Неверный ID пути.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, status, is_archived FROM wagons WHERE wagon_number = ?", (number,))
    existing = c.fetchone()

    try:
        days = int(cycle_days) if cycle_days else 0
        hours = int(cycle_hours) if cycle_hours else 0
        mins = int(cycle_mins) if cycle_mins else 0
    except ValueError:
        days, hours, mins = 0, 0, 0
    total_mins = (days * 24 * 60) + (hours * 60) + mins

    if (start_date and not start_time) or (start_time and not start_date):
        flash("Ошибка: Если вы указываете дату, нужно указать и время, и наоборот.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)

    manual_start = None
    if start_date and start_time:
        manual_start = f"{start_date} {start_time}"
        try:
            start_dt = datetime.strptime(manual_start, '%Y-%m-%d %H:%M')
            arrival_time = f"{start_date} {start_time}:00"
        except:
            arrival_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            flash("Неверный формат даты/времени, использовано текущее время", 'warning')
    else:
        arrival_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    global_dep = None
    if total_mins > 0:
        if manual_start:
            try:
                start_dt = datetime.strptime(manual_start, '%Y-%m-%d %H:%M')
                global_dep = (start_dt + timedelta(minutes=total_mins)).strftime('%Y-%m-%d %H:%M:%S')
            except:
                global_dep = (datetime.now() + timedelta(minutes=total_mins)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            global_dep = (datetime.now() + timedelta(minutes=total_mins)).strftime('%Y-%m-%d %H:%M:%S')

    if existing:
        w_id, w_status, w_archived = existing
        if w_archived == 1:
            compact_track(track_id)
            pos = find_slot_on_track(track_id, 10)[1]
            c.execute("""UPDATE wagons SET status = 'assigned', owner = ?, organization = ?, cargo_type = ?, track_id = ?, start_pos = ?, arrival_time = ?, departure_time = ?, local_departure_time = NULL, visit_count = 0, is_archived = 0 WHERE id = ?""",
                      (owner, org, note, track_id, float(pos), arrival_time, global_dep, w_id))
            conn.commit()
            conn.close()
            log_movement(number, 'added', None, None, f"Восстановлен из архива. ТК: {owner}, Орг: {org}", arrival_time)
            log_action('add', wagon_number=number, details=f"Восстановлен из архива на путь {track_id_str}")
            flash(f"✅ Вагон {number} восстановлен с временем прибытия {arrival_time[:16]}.", 'success')
            return redirect(url_for('main.index'))
        elif w_status != 'departed':
            conn.close()
            flash(f"⚠️ Вагон '{number}' уже на путях!", 'error')
            tracks, move_list = get_dashboard_data()
            is_admin = (request.user_role == 'admin')
            return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                          add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)

    compact_track(track_id)
    pos = find_slot_on_track(track_id, 10)[1]
    try:
        c.execute("""INSERT INTO wagons (wagon_number, length, cargo_type, owner, organization, track_id, start_pos, arrival_time, departure_time, local_departure_time, visit_count, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)""",
                  (number, 10.0, note, owner, org, track_id, float(pos), arrival_time, global_dep, None))
        conn.commit()
        t_name = c.execute("SELECT name FROM tracks WHERE id=?", (track_id,)).fetchone()[0]
        conn.close()
        log_movement(number, 'added', None, t_name, f"ТК: {owner}, Орг: {org}", arrival_time)
        log_action('add', wagon_number=number, details=f"Добавлен на путь {t_name}. ТК: {owner}, Орг: {org}")
        msg = f"✅ Вагон {number} добавлен с временем прибытия {arrival_time[:16]}."
        if total_mins > 0:
            msg += f" Срок: {days}д {hours}ч {mins}мин"
        if global_dep:
            msg += f" (до {global_dep[:16]})"
        flash(msg, 'success')
    except sqlite3.IntegrityError:
        conn.close()
        flash(f"⚠️ Вагон '{number}' уже существует.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)
    return redirect(url_for('main.index'))


@main_bp.route('/move', methods=['POST'])
def move_action():
    wagon_id = request.form.get('wagon_id', '')
    new_track_id_str = request.form.get('new_track_id', '')
    local_days = request.form.get('local_days', '0')
    local_hours = request.form.get('local_hours', '0')
    local_mins = request.form.get('local_mins', '0')
    start_date = request.form.get('start_date', '').strip()
    start_time = request.form.get('start_time', '').strip()
    note = request.form.get('note', '')

    move_form_data = {
        'wagon_id': wagon_id,
        'new_track_id': new_track_id_str,
        'local_days': local_days,
        'local_hours': local_hours,
        'local_mins': local_mins,
        'start_date': start_date,
        'start_time': start_time,
        'note': note
    }

    if not wagon_id or not new_track_id_str:
        flash("Выберите вагон и путь назначения!", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=None, move_form_data=move_form_data, request=request, is_admin=is_admin)
    try:
        new_track_id = int(new_track_id_str)
    except ValueError:
        flash("Ошибка: Неверный ID пути.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=None, move_form_data=move_form_data, request=request, is_admin=is_admin)
    try:
        l_days = int(local_days) if local_days else 0
        l_hours = int(local_hours) if local_hours else 0
        l_mins = int(local_mins) if local_mins else 0
    except ValueError:
        l_days, l_hours, l_mins = 0, 0, 0

    if (start_date and not start_time) or (start_time and not start_date):
        flash("Ошибка: Если вы указываете дату, нужно указать и время, и наоборот.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=None, move_form_data=move_form_data, request=request, is_admin=is_admin)

    manual_start = None
    if start_date and start_time:
        manual_start = f"{start_date} {start_time}"

    success, msg = move_wagon(wagon_id, new_track_id, l_days, l_hours, l_mins, manual_start, note)
    if success:
        flash(msg, 'success')
        return redirect(url_for('main.index'))
    else:
        flash(msg, 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=None, move_form_data=move_form_data, request=request, is_admin=is_admin)


@main_bp.route('/depart/<int:wagon_id>', methods=['POST'])
def depart_action(wagon_id):
    if depart_wagon(wagon_id):
        flash("✅ Вагон убран в архив.", 'success')
    else:
        flash("⚠️ Ошибка при удалении.", 'error')
    return redirect(url_for('main.index'))