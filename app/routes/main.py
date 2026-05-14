# -*- coding: utf-8 -*-
"""
Основные маршруты: главная страница, добавление, перемещение, архивация, справка, о программе.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import sys
import os
import socket
import sqlite3

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import APP_VERSION
from app.models import (
    get_dashboard_data, move_wagon, depart_wagon, log_movement, log_action,
    find_slot_on_track, compact_track, get_conn, get_setting
)

main_bp = Blueprint('main', __name__)


# ==================== ОПРЕДЕЛЕНИЕ ЛОКАЛЬНОГО IP (БЕЗ ВНЕШНЕГО СОЕДИНЕНИЯ) ====================
def get_local_ip():
    """Возвращает локальный IP-адрес в сети (без доступа в интернет)."""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip.startswith('127.'):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.1)
                try:
                    s.connect(('1.1.1.1', 1))
                    ip = s.getsockname()[0]
                except Exception:
                    pass
            if ip.startswith('127.'):
                return '127.0.0.1'
        return ip
    except Exception:
        return '127.0.0.1'


@main_bp.route('/')
def index():
    tracks, move_list = get_dashboard_data()
    is_admin = (request.user_role == 'admin')
    refresh_interval = int(get_setting('refresh_interval', '5'))
    return render_template('index.html',
                           tracks=tracks,
                           move_list=move_list,
                           total_wagons=len(move_list),
                           add_form_data=None,
                           move_form_data=None,
                           request=request,
                           is_admin=is_admin,
                           version=APP_VERSION,
                           refresh_interval=refresh_interval)


@main_bp.route('/help')
def help_page():
    server_ip = get_local_ip()
    return render_template('help.html', server_ip=server_ip, version=APP_VERSION)


@main_bp.route('/about')
def about_page():
    return render_template('about.html')


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
        refresh_interval = int(get_setting('refresh_interval', '5'))
        return render_template('index.html',
                               tracks=tracks,
                               move_list=move_list,
                               total_wagons=len(move_list),
                               add_form_data=add_form_data,
                               move_form_data=None,
                               request=request,
                               is_admin=is_admin,
                               version=APP_VERSION,
                               refresh_interval=refresh_interval)

    try:
        track_id = int(track_id_str)
    except ValueError:
        flash("Ошибка: Неверный ID пути.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        refresh_interval = int(get_setting('refresh_interval', '5'))
        return render_template('index.html',
                               tracks=tracks,
                               move_list=move_list,
                               total_wagons=len(move_list),
                               add_form_data=add_form_data,
                               move_form_data=None,
                               request=request,
                               is_admin=is_admin,
                               version=APP_VERSION,
                               refresh_interval=refresh_interval)

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
        refresh_interval = int(get_setting('refresh_interval', '5'))
        return render_template('index.html',
                               tracks=tracks,
                               move_list=move_list,
                               total_wagons=len(move_list),
                               add_form_data=add_form_data,
                               move_form_data=None,
                               request=request,
                               is_admin=is_admin,
                               version=APP_VERSION,
                               refresh_interval=refresh_interval)

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
            wagon_len = float(get_setting('default_wagon_length', '10.0'))
            pos = find_slot_on_track(track_id, wagon_len)[1]
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
            refresh_interval = int(get_setting('refresh_interval', '5'))
            return render_template('index.html',
                                   tracks=tracks,
                                   move_list=move_list,
                                   total_wagons=len(move_list),
                                   add_form_data=add_form_data,
                                   move_form_data=None,
                                   request=request,
                                   is_admin=is_admin,
                                   version=APP_VERSION,
                                   refresh_interval=refresh_interval)

    compact_track(track_id)
    wagon_len = float(get_setting('default_wagon_length', '10.0'))
    pos = find_slot_on_track(track_id, wagon_len)[1]
    try:
        c.execute("""INSERT INTO wagons (wagon_number, length, cargo_type, owner, organization, track_id, start_pos, arrival_time, departure_time, local_departure_time, visit_count, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)""",
                  (number, wagon_len, note, owner, org, track_id, float(pos), arrival_time, global_dep, None))
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
        refresh_interval = int(get_setting('refresh_interval', '5'))
        return render_template('index.html',
                               tracks=tracks,
                               move_list=move_list,
                               total_wagons=len(move_list),
                               add_form_data=add_form_data,
                               move_form_data=None,
                               request=request,
                               is_admin=is_admin,
                               version=APP_VERSION,
                               refresh_interval=refresh_interval)
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
        refresh_interval = int(get_setting('refresh_interval', '5'))
        return render_template('index.html',
                               tracks=tracks,
                               move_list=move_list,
                               total_wagons=len(move_list),
                               add_form_data=None,
                               move_form_data=move_form_data,
                               request=request,
                               is_admin=is_admin,
                               version=APP_VERSION,
                               refresh_interval=refresh_interval)

    try:
        new_track_id = int(new_track_id_str)
    except ValueError:
        flash("Ошибка: Неверный ID пути.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        refresh_interval = int(get_setting('refresh_interval', '5'))
        return render_template('index.html',
                               tracks=tracks,
                               move_list=move_list,
                               total_wagons=len(move_list),
                               add_form_data=None,
                               move_form_data=move_form_data,
                               request=request,
                               is_admin=is_admin,
                               version=APP_VERSION,
                               refresh_interval=refresh_interval)

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
        refresh_interval = int(get_setting('refresh_interval', '5'))
        return render_template('index.html',
                               tracks=tracks,
                               move_list=move_list,
                               total_wagons=len(move_list),
                               add_form_data=None,
                               move_form_data=move_form_data,
                               request=request,
                               is_admin=is_admin,
                               version=APP_VERSION,
                               refresh_interval=refresh_interval)

    # --- Сохраняем старый путь ДО перемещения ---
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT track_id FROM wagons WHERE id = ?", (wagon_id,))
    old_track = c.fetchone()
    old_track_id = old_track[0] if old_track else None
    conn.close()

    manual_start = None
    if start_date and start_time:
        manual_start = f"{start_date} {start_time}"

    success, msg = move_wagon(wagon_id, new_track_id, l_days, l_hours, l_mins, manual_start, note)
    if success:
        # --- Уплотняем СТАРЫЙ путь после перемещения ---
        if old_track_id is not None:
            compact_track(old_track_id)
        flash(msg, 'success')
        return redirect(url_for('main.index'))
    else:
        flash(msg, 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        refresh_interval = int(get_setting('refresh_interval', '5'))
        return render_template('index.html',
                               tracks=tracks,
                               move_list=move_list,
                               total_wagons=len(move_list),
                               add_form_data=None,
                               move_form_data=move_form_data,
                               request=request,
                               is_admin=is_admin,
                               version=APP_VERSION,
                               refresh_interval=refresh_interval)


@main_bp.route('/depart/<int:wagon_id>', methods=['POST'])
def depart_action(wagon_id):
    conn = get_conn()
    c = conn.cursor()
    
    # 1. Узнаем, на каком пути был вагон, чтобы уплотнить именно этот путь
    c.execute("SELECT track_id, wagon_number FROM wagons WHERE id = ?", (wagon_id,))
    row = c.fetchone()
    
    if row:
        track_id, wagon_number = row
        
        # 2. Выполняем удаление (архивацию)
        if depart_wagon(wagon_id):
            # 3. ВАЖНО: Уплотняем путь после удаления вагона
            compact_track(track_id)
            
            conn.commit()
            conn.close()
            
            log_movement(wagon_number, 'departed', None, None, "Убыл со станции", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            log_action('depart', wagon_number=wagon_number, details=f"Убыл со станции")
            
            flash("✅ Вагон убран в архив.", 'success')
        else:
            conn.close()
            flash("⚠️ Ошибка при удалении.", 'error')
    else:
        conn.close()
        flash("⚠️ Вагон не найден.", 'error')
        
    return redirect(url_for('main.index'))