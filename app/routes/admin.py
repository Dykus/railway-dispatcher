# app/routes/admin.py
# -*- coding: utf-8 -*-
"""
Административные маршруты: бэкапы, журнал действий, управление IP, список изменений, настройки, пути.
"""
from flask import Blueprint, request, send_file, flash, redirect, url_for, render_template, jsonify, g
import os
import sys
import glob
import shutil
import io
import pandas as pd
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import BACKUP_DIR, DB_NAME, CHANGELOG_PATH
from app.models import (
    get_conn, get_all_settings, set_setting,
    get_all_tracks, add_track, update_track, delete_track,
    move_track_up, move_track_down
)
from app.utils import log_action, parse_flexible_date, get_moscow_now

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def apply_excel_styling(writer, sheet_name, has_notes=False):
    from openpyxl.styles import Font, Alignment
    worksheet = writer.sheets[sheet_name]
    for column in worksheet.columns:
        max_length = 0
        col_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        worksheet.column_dimensions[col_letter].width = adjusted_width
    worksheet.auto_filter.ref = worksheet.dimensions
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center', vertical='center')
    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            if has_notes and cell.column_letter in ('F', 'G', 'H', 'D', 'E'):
                cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal='center', vertical='center')

# ==================== БЭКАПЫ ====================
@admin_bp.route('/backup', methods=['POST'])
def create_backup():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    try:
        date_str = get_moscow_now().strftime('%Y%m%d')
        daily_dir = os.path.join(BACKUP_DIR, date_str)
        if not os.path.exists(daily_dir):
            os.makedirs(daily_dir)
        time_str = get_moscow_now().strftime('%H%M%S')
        backup_name = f"rail_yard_backup_{date_str}_{time_str}.db"
        backup_path = os.path.join(daily_dir, backup_name)
        shutil.copy2(DB_NAME, backup_path)
        log_action('backup_create', details=f"Создана копия: {backup_path}")
        return f"✅ Резервная копия создана: {backup_path}", 200
    except Exception as e:
        return f"❌ Ошибка создания бэкапа: {str(e)}", 500

@admin_bp.route('/backups')
def list_backups():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    all_backups = glob.glob(os.path.join(BACKUP_DIR, '**', '*.db'), recursive=True)
    backups_info = []
    for path in all_backups:
        stat = os.stat(path)
        rel_path = os.path.relpath(path, BACKUP_DIR).replace('\\', '/')
        backups_info.append({
            'name': os.path.basename(path),
            'rel_path': rel_path,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        })
    backups_info.sort(key=lambda x: x['modified'], reverse=True)
    return render_template('admin_backups.html', backups_info=backups_info)

@admin_bp.route('/download_backup')
def download_backup():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    rel_path = request.args.get('rel_path')
    if not rel_path:
        return "Не указан путь", 400
    full_path = os.path.abspath(os.path.join(BACKUP_DIR, rel_path))
    if not full_path.startswith(os.path.abspath(BACKUP_DIR)):
        return "Неверный путь", 403
    if not os.path.exists(full_path):
        return "Файл не найден", 404
    return send_file(full_path, as_attachment=True, download_name=os.path.basename(full_path))

@admin_bp.route('/restore', methods=['POST'])
def restore_backup():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    rel_path = request.form.get('rel_path')
    if not rel_path:
        return "Не указан путь", 400
    full_path = os.path.abspath(os.path.join(BACKUP_DIR, rel_path))
    if not full_path.startswith(os.path.abspath(BACKUP_DIR)):
        return "Неверный путь", 403
    if not os.path.exists(full_path):
        return f"Файл не найден: {full_path}", 404
    try:
        temp_backup = os.path.join(BACKUP_DIR, f"pre_restore_{get_moscow_now().strftime('%Y%m%d_%H%M%S')}.db")
        shutil.copy2(DB_NAME, temp_backup)
        shutil.copy2(full_path, DB_NAME)
        log_action('backup_restore', details=f"Восстановлена БД из {rel_path}")
        return f"✅ База данных восстановлена из {rel_path}. Рекомендуется перезапустить программу."
    except Exception as e:
        return f"❌ Ошибка восстановления: {str(e)}", 500

# ==================== ЖУРНАЛ ДЕЙСТВИЙ ====================
@admin_bp.route('/logs')
def view_logs():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    station_id = g.get('station_id', 1)
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM action_log WHERE station_id = ? ORDER BY timestamp DESC LIMIT 500", (station_id,))
    logs = c.fetchall()
    conn.close()
    action_translation = {
        'add': 'Добавление вагона', 'move': 'Перемещение', 'depart': 'Архивация',
        'backup_create': 'Создание бэкапа', 'backup_restore': 'Восстановление из бэкапа',
        'ip_user_edit': 'Изменение привязки IP', 'ip_user_delete': 'Удаление привязки IP',
        'edit': 'Редактирование вагона', 'backup_auto': 'Автоматический бэкап',
        'edit_history': 'Редактирование истории', 'track_add': 'Добавление пути',
        'track_edit': 'Редактирование пути', 'track_delete': 'Удаление пути',
        'track_move': 'Изменение порядка путей', 'track_reorder': 'Сохранение порядка путей',
        'backup_remote': 'Удалённый бэкап', 'backup_remote_error': 'Ошибка удалённого бэкапа'
    }
    return render_template('admin_logs.html', logs=logs, action_translation=action_translation)

@admin_bp.route('/export_logs_excel')
def export_logs_excel():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    station_id = g.get('station_id', 1)
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT timestamp as "Время", username as "Пользователь", ip_address as "IP-адрес",
               action as "Действие", wagon_number as "Номер вагона", details as "Детали",
               old_value as "Старое значение", new_value as "Новое значение"
        FROM action_log WHERE station_id = ? ORDER BY timestamp DESC
    """, conn, params=(station_id,))
    conn.close()
    action_map = {
        'add': 'Добавление вагона', 'move': 'Перемещение', 'depart': 'Архивация',
        'backup_create': 'Создание бэкапа', 'backup_restore': 'Восстановление из бэкапа',
        'ip_user_edit': 'Изменение привязки IP', 'ip_user_delete': 'Удаление привязки IP',
        'edit': 'Редактирование вагона', 'backup_auto': 'Автоматический бэкап',
        'edit_history': 'Редактирование истории', 'track_add': 'Добавление пути',
        'track_edit': 'Редактирование пути', 'track_delete': 'Удаление пути',
        'track_move': 'Изменение порядка путей', 'track_reorder': 'Сохранение порядка путей',
        'backup_remote': 'Удалённый бэкап', 'backup_remote_error': 'Ошибка удалённого бэкапа'
    }
    df['Действие'] = df['Действие'].map(action_map).fillna(df['Действие'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Журнал действий', index=False)
        apply_excel_styling(writer, 'Журнал действий', has_notes=True)
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"ActionLog_{get_moscow_now().strftime('%Y%m%d_%H%M%S')}.xlsx")

# ==================== УПРАВЛЕНИЕ IP ====================
@admin_bp.route('/ip_users', methods=['GET', 'POST'])
def manage_ip_users():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    conn = get_conn()
    c = conn.cursor()
    if request.method == 'POST':
        if request.form.get('delete_ip'):
            del_ip = request.form.get('delete_ip')
            c.execute("DELETE FROM ip_users WHERE ip_address = ?", (del_ip,))
            conn.commit()
            flash(f"Привязка для IP {del_ip} удалена", 'success')
            log_action('ip_user_delete', details=f"Удалена привязка IP {del_ip}")
            conn.close()
            return redirect(url_for('admin.manage_ip_users'))
        
        ip = request.form.get('ip_address', '').strip()
        username = request.form.get('username', '').strip()
        note = request.form.get('note', '').strip()
        access_allowed = 1 if request.form.get('access_allowed') else 0
        role = request.form.get('role', 'viewer')
        
        if ip and username:
            c.execute("INSERT OR REPLACE INTO ip_users (ip_address, username, note, access_allowed, role) VALUES (?, ?, ?, ?, ?)",
                      (ip, username, note, access_allowed, role))
            conn.commit()
            flash(f"Привязка для IP {ip} сохранена", 'success')
            log_action('ip_user_edit', details=f"Добавлен/изменён IP {ip} → {username}, доступ={access_allowed}, роль={role}")
            conn.close()
            return redirect(url_for('admin.manage_ip_users'))
    
    c.execute("SELECT ip_address, username, note, access_allowed, role FROM ip_users ORDER BY ip_address")
    rows = c.fetchall()
    conn.close()
    return render_template('admin_ip_users.html', rows=rows)

# ==================== РЕДАКТИРОВАНИЕ ====================
@admin_bp.route('/edit_wagon/<int:wagon_id>', methods=['POST'])
def edit_wagon_route(wagon_id):
    if request.user_role not in ('supervisor', 'admin'):
        return jsonify({"error": "Недостаточно прав"}), 403
    station_id = g.get('station_id', 1)
    new_owner = request.form.get('owner') or None
    new_org = request.form.get('organization') or None
    new_note = request.form.get('note') or None
    new_arrival = request.form.get('arrival_time') or None
    new_global = request.form.get('departure_time') or None
    new_local = request.form.get('local_departure_time') or None
    from app.models import edit_wagon
    success, msg = edit_wagon(wagon_id, new_owner, new_org, new_note, new_arrival, new_global, new_local, station_id)
    if success:
        return jsonify({"success": True, "message": msg})
    else:
        return jsonify({"success": False, "message": msg}), 400

@admin_bp.route('/edit_history/<int:history_id>', methods=['POST'])
def edit_history(history_id):
    if request.user_role not in ('supervisor', 'admin'):
        return jsonify({"error": "Недостаточно прав"}), 403
    new_timestamp_str = request.form.get('timestamp', '').strip()
    if not new_timestamp_str:
        return jsonify({"error": "Дата не указана"}), 400
    try:
        new_dt = parse_flexible_date(new_timestamp_str)
        if new_dt is None: raise ValueError
        new_timestamp = new_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return jsonify({"error": f"Неверный формат даты: {e}"}), 400
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT wagon_number, timestamp, action_type FROM movement_history WHERE id = ?", (history_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Запись не найдена"}), 404
    wagon_num, old_timestamp, action_type = row
    c.execute("""SELECT id, timestamp FROM movement_history
                 WHERE wagon_number = ? AND id != ? ORDER BY timestamp ASC""", (wagon_num, history_id))
    all_events = c.fetchall()
    prev_ts = next_ts = None
    found = False
    for ev_id, ev_ts in all_events:
        if ev_ts == old_timestamp and not found:
            found = True
            continue
        if not found: prev_ts = ev_ts
        else: 
            next_ts = ev_ts
            break
    if prev_ts and new_timestamp <= prev_ts:
        conn.close()
        return jsonify({"error": f"Новая дата не может быть раньше предыдущего события ({prev_ts[:16]})"}), 400
    if next_ts and new_timestamp >= next_ts:
        conn.close()
        return jsonify({"error": f"Новая дата не может быть позже следующего события ({next_ts[:16]})"}), 400
    c.execute("UPDATE movement_history SET timestamp = ? WHERE id = ?", (new_timestamp, history_id))
    c.execute("SELECT MAX(timestamp) FROM movement_history WHERE wagon_number = ?", (wagon_num,))
    last_ts = c.fetchone()[0]
    if last_ts == new_timestamp:
        if action_type == 'added':
            c.execute("UPDATE wagon_visits SET arrival_time = ? WHERE wagon_number = ? AND is_archived = 0", (new_timestamp, wagon_num))
        elif action_type == 'moved':
            c.execute("SELECT local_departure_time FROM wagon_visits WHERE wagon_number = ? AND is_archived = 0", (wagon_num,))
            loc = c.fetchone()
            if loc and loc[0]:
                try:
                    old_loc_dt = datetime.strptime(loc[0], '%Y-%m-%d %H:%M:%S')
                    old_event_dt = datetime.strptime(old_timestamp, '%Y-%m-%d %H:%M:%S')
                    new_event_dt = datetime.strptime(new_timestamp, '%Y-%m-%d %H:%M:%S')
                    delta = old_loc_dt - old_event_dt
                    new_loc_dt = new_event_dt + delta
                    c.execute("UPDATE wagon_visits SET local_departure_time = ? WHERE wagon_number = ? AND is_archived = 0",
                              (new_loc_dt.strftime('%Y-%m-%d %H:%M:%S'), wagon_num))
                except: pass
    conn.commit()
    log_action('edit_history', wagon_number=wagon_num,
               details=f"Изменена дата события #{history_id} с {old_timestamp} на {new_timestamp}",
               old_value=old_timestamp, new_value=new_timestamp)
    conn.close()
    return jsonify({"success": True, "message": "Дата успешно обновлена"})

# ==================== CHANGELOG ====================
@admin_bp.route('/changelog')
def changelog():
    if request.user_role != 'admin':
        return "Доступ запрещён. Список изменений доступен только администраторам.", 403
    if not os.path.exists(CHANGELOG_PATH):
        return f"Файл CHANGELOG.txt не найден. Ожидаемый путь: {CHANGELOG_PATH}", 404
    with open(CHANGELOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_template('changelog.html', content=content)

# ==================== НАСТРОЙКИ (ИСПРАВЛЕНА ОШИБКА UNIQUE) ====================
@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    station_id = g.get('station_id', 1)

    if request.method == 'POST':
        # --- ОТЛАДКА: печатаем полученные данные ---
        import logging
        logging.warning("=== POST данные для station_id=%s ===", station_id)
        for key, value in request.form.items():
            logging.warning("  %s = %s", key, value)
        logging.warning("=================================")

        action = request.form.get('action')
        
        # Управление путями
        if action == 'add_track':
            name = request.form.get('track_name', '').strip()
            length = request.form.get('track_length', '')
            track_type = request.form.get('track_type', 'normal')
            if name and length:
                success, msg = add_track(name, length, track_type, station_id)
                flash(msg, 'success' if success else 'error')
            else:
                flash("Название и длина обязательны", 'error')
            return redirect(url_for('admin.settings', station_id=station_id))
            
        elif action == 'edit_track':
            track_id = request.form.get('track_id')
            name = request.form.get('track_name', '').strip()
            length = request.form.get('track_length', '')
            track_type = request.form.get('track_type', 'normal')
            if track_id and name and length:
                success, msg = update_track(track_id, name, length, track_type)
                flash(msg, 'success' if success else 'error')
            else:
                flash("Название и длина обязательны", 'error')
            return redirect(url_for('admin.settings', station_id=station_id))
            
        elif action == 'delete_track':
            track_id = request.form.get('track_id')
            if track_id:
                success, msg = delete_track(track_id)
                flash(msg, 'success' if success else 'error')
            return redirect(url_for('admin.settings', station_id=station_id))

        # ---------- СОХРАНЕНИЕ ОСНОВНЫХ НАСТРОЕК ----------
        else:
            # Глобальные настройки (station_id=0)
            global_keys = [
                'port', 'secret_key', 'backup_hour', 'backup_keep_count',
                'remote_enabled', 'remote_path', 'remote_user', 'remote_password',
                'log_max_mb', 'log_backup_count'
            ]
            for key in global_keys:
                if key == 'remote_enabled':
                    value = '1' if request.form.get(key) else '0'
                elif key == 'remote_password':
                    value = request.form.get(key, '')
                else:
                    value = request.form.get(key, '')
                set_setting(key, value, station_id=0)

            # Локальные настройки (интерфейс и вагоны)
            local_keys = ['refresh_interval', 'default_wagon_length', 'wagon_spacing']
            for key in local_keys:
                value = request.form.get(key, '')
                set_setting(key, value, station_id=station_id)

            # ========== НАСТРОЙКИ ШТРАФОВ – БЕЗ ОШИБКИ UNIQUE ==========
            conn = get_conn()
            c = conn.cursor()
            # Список ключей и значений
            fine_data = {
                'overstay_progressive': request.form.get('overstay_progressive', '0'),
                'overstay_fixed_rate': request.form.get('overstay_fixed_rate', '2000'),
                'overstay_range1_limit': request.form.get('overstay_range1_limit', '4'),
                'overstay_range1_rate': request.form.get('overstay_range1_rate', '2000'),
                'overstay_range2_limit': request.form.get('overstay_range2_limit', '7'),
                'overstay_range2_rate': request.form.get('overstay_range2_rate', '2400'),
                'overstay_range3_rate': request.form.get('overstay_range3_rate', '3000')
            }
            for key, value in fine_data.items():
                # INSERT OR REPLACE автоматически заменяет существующую запись
                c.execute("INSERT OR REPLACE INTO app_settings (key, value, station_id) VALUES (?, ?, ?)",
                          (key, str(value), station_id))
            conn.commit()
            conn.close()

            # --- ОТЛАДКА: проверяем, что записалось ---
            conn2 = get_conn()
            c2 = conn2.cursor()
            c2.execute("SELECT key, value FROM app_settings WHERE station_id = ? AND key LIKE 'overstay_%'", (station_id,))
            rows = c2.fetchall()
            conn2.close()
            logging.warning("=== СОХРАНЁННЫЕ НАСТРОЙКИ ДЛЯ station_id=%s ===", station_id)
            for key, value in rows:
                logging.warning("  %s = %s", key, value)
            logging.warning("============================================")

            flash('Настройки сохранены', 'success')
            return redirect(url_for('admin.settings', station_id=station_id))

    # GET – отображаем страницу
    settings_dict = get_all_settings(station_id)
    tracks = get_all_tracks(station_id)
    return render_template('admin_settings.html', settings=settings_dict, tracks=tracks)

# ==================== ПЕРЕМЕЩЕНИЕ ПУТЕЙ ====================
@admin_bp.route('/tracks/up', methods=['POST'])
def move_track_up_route():
    if request.user_role != 'admin':
        return jsonify({"error": "Доступ запрещён"}), 403
    track_id = request.args.get('track_id')
    if not track_id:
        return jsonify({"error": "Не указан путь"}), 400
    success = move_track_up(int(track_id))
    return jsonify({"success": success})

@admin_bp.route('/tracks/down', methods=['POST'])
def move_track_down_route():
    if request.user_role != 'admin':
        return jsonify({"error": "Доступ запрещён"}), 403
    track_id = request.args.get('track_id')
    if not track_id:
        return jsonify({"error": "Не указан путь"}), 400
    success = move_track_down(int(track_id))
    return jsonify({"success": success})

# ==================== СОХРАНЕНИЕ ПОРЯДКА ПУТЕЙ ====================
@admin_bp.route('/tracks/save_order', methods=['POST'])
def save_tracks_order():
    if request.user_role != 'admin':
        return jsonify({"error": "Доступ запрещён"}), 403
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({"error": "Неверные данные"}), 400
    order = data['order']
    conn = get_conn()
    c = conn.cursor()
    try:
        for idx, track_id in enumerate(order, start=1):
            c.execute("UPDATE tracks SET sort_order = ? WHERE id = ?", (idx, track_id))
        conn.commit()
        log_action('track_reorder', details="Обновлён порядок путей")
        return jsonify({"success": True, "message": "Порядок сохранён"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# ==================== ПЕРЕИМЕНОВАНИЕ ПЛОЩАДОК ====================
@admin_bp.route('/rename_station', methods=['POST'])
def rename_station():
    if request.user_role != 'admin':
        return jsonify({"error": "Доступ запрещён"}), 403
    station_id = request.form.get('station_id')
    new_name = request.form.get('name', '').strip()
    if not station_id or not new_name:
        return jsonify({"error": "Неверные данные"}), 400
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE stations SET name = ? WHERE id = ?", (new_name, station_id))
    conn.commit()
    conn.close()
    log_action('station_rename', details=f"Площадка id={station_id} переименована в '{new_name}'")
    return jsonify({"success": True, "message": "Название обновлено"})