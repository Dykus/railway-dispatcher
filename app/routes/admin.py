# -*- coding: utf-8 -*-
"""
Административные маршруты: бэкапы, журнал действий, управление IP, список изменений.
"""

from flask import Blueprint, request, send_file, flash, redirect, url_for, render_template_string, jsonify
import os
import sys
import glob
import shutil
import io
import pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import BACKUP_DIR, DB_NAME, CHANGELOG_PATH, APP_VERSION
from app.models import get_conn
from app.utils import log_action, parse_flexible_date

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
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
            if has_notes and cell.column_letter in ('F', 'G', 'H'):
                cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal='center', vertical='center')

# ==================== БЭКАПЫ ====================
@admin_bp.route('/backup', methods=['POST'])
def create_backup():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    try:
        date_str = datetime.now().strftime('%Y%m%d')
        daily_dir = os.path.join(BACKUP_DIR, date_str)
        if not os.path.exists(daily_dir):
            os.makedirs(daily_dir)
        time_str = datetime.now().strftime('%H%M%S')
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
    html = """
    <html>
    <head><title>Резервные копии</title>
    <style>
        body { font-family: monospace; padding: 20px; background: #f0f2f5; }
        table { border-collapse: collapse; width: 100%; background: white; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #34495e; color: white; }
        .btn { display: inline-block; padding: 5px 10px; background: #3498db; color: white; text-decoration: none; border-radius: 4px; margin-right: 5px; }
        .btn-danger { background: #e74c3c; }
        .nav-bar { margin-bottom: 15px; }
    </style>
    </head>
    <body>
    <h1>📦 Резервные копии базы данных</h1>
    <div class="nav-bar">
        <a href="/" class="btn">🏠 На главную</a>
        <a href="/admin/logs" class="btn">📜 Журнал действий</a>
        <a href="/admin/ip_users" class="btn">🔗 Привязка IP</a>
        <a href="/admin/changelog" class="btn">📋 Список изменений</a>
    </div>
    <p><a href="#" onclick="event.preventDefault(); fetch('/admin/backup', {method:'POST'}).then(r=>r.text()).then(alert);" class="btn">➕ Создать новую копию</a></p>
    <table>
        <tr><th>Имя файла</th><th>Размер (КБ)</th><th>Дата изменения</th><th>Действия</th></tr>
    """
    for b in backups_info:
        size_kb = b['size'] / 1024
        html += f"""
        <tr>
            <td>{b['name']}</td>
            <td>{size_kb:.1f}</td>
            <td>{b['modified']}</td>
            <td>
                <a href="/admin/download_backup?rel_path={b['rel_path']}" class="btn">📥 Скачать</a>
                <a href="#" onclick="restore('{b['rel_path']}')" class="btn btn-danger">🔄 Восстановить</a>
            </td>
        </tr>
        """
    html += """
    </table>
    <script>
    function restore(relPath) {
        if (confirm('Восстановление заменит текущую базу данных! Сделайте резервную копию перед восстановлением. Продолжить?')) {
            fetch('/admin/restore', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'rel_path=' + encodeURIComponent(relPath)
            }).then(r => r.text()).then(alert).then(() => location.reload());
        }
    }
    </script>
    </body>
    </html>
    """
    return html

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
        temp_backup = os.path.join(BACKUP_DIR, f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
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
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM action_log ORDER BY timestamp DESC LIMIT 500")
    logs = c.fetchall()
    conn.close()
    action_translation = {
        'add': 'Добавление вагона',
        'move': 'Перемещение',
        'depart': 'Архивация',
        'backup_create': 'Создание бэкапа',
        'backup_restore': 'Восстановление из бэкапа',
        'ip_user_edit': 'Изменение привязки IP',
        'ip_user_delete': 'Удаление привязки IP',
        'edit': 'Редактирование вагона',
        'backup_auto': 'Автоматический бэкап',
        'edit_history': 'Редактирование истории'
    }
    html = """
    <html>
    <head>
        <title>Журнал действий</title>
        <style>
            body { font-family: monospace; padding: 20px; background: #f0f2f5; }
            table { border-collapse: collapse; width: 100%; background: white; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background: #34495e; color: white; }
            .btn { display: inline-block; padding: 5px 10px; background: #3498db; color: white; text-decoration: none; border-radius: 4px; }
            .btn-excel { background: #27ae60; }
        </style>
    </head>
    <body>
        <h1>📋 Журнал действий</h1>
        <p>
            <a href="/" class="btn">🏠 На главную</a>
            <a href="/admin/export_logs_excel" class="btn btn-excel">📊 Выгрузить в Excel</a>
        </p>
        <table>
            <thead>
                <tr>
                    <th>Время</th>
                    <th>Пользователь</th>
                    <th>IP</th>
                    <th>Действие</th>
                    <th>Вагон</th>
                    <th>Детали</th>
                    <th>Старое</th>
                    <th>Новое</th>
                </tr>
            </thead>
            <tbody>
    """
    for log in logs:
        action_rus = action_translation.get(log[4], log[4])
        html += f"""
                <tr>
                    <td>{log[1]}</td>
                    <td>{log[2]}</td>
                    <td>{log[3]}</td>
                    <td>{action_rus}</td>
                    <td>{log[5] if log[5] else ''}</td>
                    <td>{log[6] if log[6] else ''}</td>
                    <td>{log[7] if log[7] else ''}</td>
                    <td>{log[8] if log[8] else ''}</td>
                </tr>
        """
    html += """
            </tbody>
        </table>
    </body>
    </html>
    """
    return html

@admin_bp.route('/export_logs_excel')
def export_logs_excel():
    if request.user_role != 'admin':
        return "Доступ запрещён", 403
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT 
            timestamp as "Время",
            username as "Пользователь",
            ip_address as "IP-адрес",
            action as "Действие",
            wagon_number as "Номер вагона",
            details as "Детали",
            old_value as "Старое значение",
            new_value as "Новое значение"
        FROM action_log
        ORDER BY timestamp DESC
    """, conn)
    conn.close()
    action_map = {
        'add': 'Добавление вагона',
        'move': 'Перемещение',
        'depart': 'Архивация',
        'backup_create': 'Создание бэкапа',
        'backup_restore': 'Восстановление из бэкапа',
        'ip_user_edit': 'Изменение привязки IP',
        'ip_user_delete': 'Удаление привязки IP',
        'edit': 'Редактирование вагона',
        'backup_auto': 'Автоматический бэкап',
        'edit_history': 'Редактирование истории'
    }
    df['Действие'] = df['Действие'].map(action_map).fillna(df['Действие'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Журнал действий', index=False)
        apply_excel_styling(writer, 'Журнал действий', has_notes=True)
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=f"ActionLog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

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
    
    html = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Привязка IP к пользователям</title>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; background: #f0f2f5; margin: 0; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; margin-top: 0; }
            .btn { display: inline-block; padding: 8px 15px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-right: 5px; font-size: 14px; }
            .btn-excel { background: #27ae60; }
            form { background: #ecf0f1; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
            input, select { padding: 8px; margin: 5px 5px 5px 0; border: 1px solid #bdc3c7; border-radius: 4px; }
            label { margin-right: 10px; }
            table { width: 100%; border-collapse: collapse; background: white; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: top; }
            th { background: #34495e; color: white; font-weight: bold; }
            tr:nth-child(even) { background: #f9f9f9; }
            .delete-btn { background: #e74c3c; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; }
            .nav-bar { margin-bottom: 20px; }
        </style>
    </head>
    <body>
    <div class="container">
        <h1>🔗 Привязка IP к именам пользователей</h1>
        <div class="nav-bar">
            <a href="/" class="btn">🏠 На главную</a>
            <a href="/admin/logs" class="btn">📜 Журнал действий</a>
            <a href="/admin/backups" class="btn">💾 Бэкапы</a>
            <a href="/admin/changelog" class="btn">📋 Список изменений</a>
        </div>
        
        <form method="POST">
            <h3>Добавить / изменить привязку</h3>
            <input type="text" name="ip_address" placeholder="IP-адрес (например, 192.168.1.100)" required>
            <input type="text" name="username" placeholder="Имя пользователя" required>
            <input type="text" name="note" placeholder="Примечание (необязательно)">
            <label><input type="checkbox" name="access_allowed" value="1"> Доступ разрешён</label>
            <select name="role">
                <option value="viewer">Наблюдатель (только просмотр)</option>
                <option value="dispatcher">Диспетчер</option>
                <option value="supervisor">Супервизор (может редактировать данные)</option>
                <option value="admin">Администратор</option>
            </select>
            <button type="submit" class="btn" style="background:#27ae60;">Сохранить</button>
        </form>
        
        <h3>Текущие привязки</h3>
        <table>
            <thead>
                <tr>
                    <th>IP-адрес</th>
                    <th>Имя пользователя</th>
                    <th>Примечание</th>
                    <th>Доступ</th>
                    <th>Роль</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
    """
    for ip, username, note, access_allowed, role in rows:
        access_flag = "Да" if access_allowed else "Нет"
        html += f"""
                <tr>
                    <td>{ip}</td>
                    <td>{username}</td>
                    <td>{note or ''}</td>
                    <td>{access_flag}</td>
                    <td>{role}</td>
                    <td>
                        <form method="POST" style="margin:0; padding:0; display:inline;" onsubmit="return confirm('Удалить привязку для {ip}?')">
                            <input type="hidden" name="delete_ip" value="{ip}">
                            <button type="submit" class="delete-btn">❌ Удалить</button>
                        </form>
                    </td>
                </tr>
        """
    html += """
            </tbody>
        </table>
    </div>
    </body>
    </html>
    """
    return html

# ==================== РЕДАКТИРОВАНИЕ ВАГОНА И ИСТОРИИ ====================
@admin_bp.route('/edit_wagon/<int:wagon_id>', methods=['POST'])
def edit_wagon_route(wagon_id):
    if request.user_role not in ('supervisor', 'admin'):
        return jsonify({"error": "Недостаточно прав"}), 403
    new_owner = request.form.get('owner') or None
    new_org = request.form.get('organization') or None
    new_note = request.form.get('note') or None
    new_arrival = request.form.get('arrival_time') or None
    new_global = request.form.get('departure_time') or None
    new_local = request.form.get('local_departure_time') or None
    from app.models import edit_wagon
    success, msg = edit_wagon(wagon_id, new_owner, new_org, new_note, new_arrival, new_global, new_local)
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
        if new_dt is None:
            raise ValueError
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
                 WHERE wagon_number = ? AND id != ? 
                 ORDER BY timestamp ASC""", (wagon_num, history_id))
    all_events = c.fetchall()
    prev_ts = None
    next_ts = None
    found = False
    for ev_id, ev_ts in all_events:
        if ev_ts == old_timestamp and not found:
            found = True
            continue
        if not found:
            prev_ts = ev_ts
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
            c.execute("UPDATE wagons SET arrival_time = ? WHERE wagon_number = ? AND is_archived = 0", (new_timestamp, wagon_num))
        elif action_type == 'moved':
            c.execute("SELECT local_departure_time FROM wagons WHERE wagon_number = ? AND is_archived = 0", (wagon_num,))
            loc = c.fetchone()
            if loc and loc[0]:
                try:
                    old_loc_dt = datetime.strptime(loc[0], '%Y-%m-%d %H:%M:%S')
                    old_event_dt = datetime.strptime(old_timestamp, '%Y-%m-%d %H:%M:%S')
                    new_event_dt = datetime.strptime(new_timestamp, '%Y-%m-%d %H:%M:%S')
                    delta = old_loc_dt - old_event_dt
                    new_loc_dt = new_event_dt + delta
                    c.execute("UPDATE wagons SET local_departure_time = ? WHERE wagon_number = ? AND is_archived = 0",
                              (new_loc_dt.strftime('%Y-%m-%d %H:%M:%S'), wagon_num))
                except:
                    pass
    conn.commit()
    log_action('edit_history', wagon_number=wagon_num,
               details=f"Изменена дата события #{history_id} с {old_timestamp} на {new_timestamp}",
               old_value=old_timestamp, new_value=new_timestamp)
    conn.close()
    return jsonify({"success": True, "message": "Дата успешно обновлена"})

# ==================== CHANGELOG ====================
@admin_bp.route('/admin/changelog')
def changelog():
    if request.user_role != 'admin':
        return "Доступ запрещён. Список изменений доступен только администраторам.", 403
    if not os.path.exists(CHANGELOG_PATH):
        return f"Файл CHANGELOG.txt не найден. Ожидаемый путь: {CHANGELOG_PATH}", 404
    with open(CHANGELOG_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    html = f"""
    <html>
    <head>
        <title>Список изменений</title>
        <style>
            body {{ font-family: monospace; padding: 20px; background: #f0f2f5; }}
            pre {{ background: white; padding: 20px; border-radius: 10px; overflow-x: auto; }}
            .btn {{ display: inline-block; padding: 5px 10px; background: #3498db; color: white; text-decoration: none; border-radius: 4px; margin-right: 5px; }}
            .nav-bar {{ margin-bottom: 15px; }}
        </style>
    </head>
    <body>
        <div class="nav-bar">
            <a href="/" class="btn">🏠 На главную</a>
            <a href="/admin/logs" class="btn">📜 Журнал действий</a>
            <a href="/admin/ip_users" class="btn">🔗 Привязка IP</a>
            <a href="/admin/backups" class="btn">📦 Резервные копии</a>
        </div>
        <h1>📋 Список изменений</h1>
        <pre>{content}</pre>
    </body>
    </html>
    """
    return html