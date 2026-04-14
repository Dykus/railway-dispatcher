# -*- coding: utf-8 -*-
"""
API-маршруты для получения данных в формате JSON.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import sys
import os

# Добавляем пути для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.models import get_dashboard_data, get_conn

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/status')
def api_status():
    """Возвращает статус таймеров для всех активных вагонов."""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now()
    c.execute("""SELECT w.id, w.local_departure_time, w.departure_time 
                 FROM wagons w 
                 WHERE w.status != 'departed' AND w.is_archived = 0""")
    rows = c.fetchall()
    conn.close()
    result = []
    for w_id, local_dep_str, global_dep_str in rows:
        timer_text = ""
        if local_dep_str:
            try:
                local_dt = datetime.strptime(local_dep_str, '%Y-%m-%d %H:%M:%S')
                diff = (local_dt - now).total_seconds()
                if diff <= 0:
                    timer_text = "ПРОСРОЧЕНО!"
                else:
                    m, s = divmod(int(diff), 60)
                    h, m = divmod(m, 60)
                    d, h = divmod(h, 24)
                    timer_text = f"{d}д {h:02d}:{m:02d}:{s:02d}" if d > 0 else f"{h:02d}:{m:02d}:{s:02d}"
            except:
                pass
        result.append({"id": w_id, "text": timer_text})
    return jsonify({"timers": result})


@api_bp.route('/wagon_info')
def get_wagon_info():
    """Возвращает информацию о вагоне (ТК и организация) по номеру."""
    num = request.args.get('num', '').strip()
    if not num:
        return jsonify({})
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT owner, organization FROM wagons WHERE wagon_number = ? LIMIT 1", (num,))
    row = c.fetchone()
    if not row:
        c.execute("SELECT owner, organization FROM wagons WHERE wagon_number = ? AND is_archived = 1 ORDER BY id DESC LIMIT 1", (num,))
        row = c.fetchone()
    conn.close()
    if row:
        return jsonify({"owner": row[0] or "", "org": row[1] or ""})
    return jsonify({})


@api_bp.route('/dashboard_data')
def api_dashboard_data():
    """Возвращает полные данные о путях и вагонах для AJAX-обновления."""
    tracks, move_list = get_dashboard_data()
    result = []
    for track in tracks:
        wagons_data = []
        for w in track['wagons']:
            wagons_data.append({
                'id': w['id'],
                'num': w['num'],
                'owner': w['owner'],
                'org': w['org'],
                'note': w['note'],
                'pos': w['pos'],
                'arrival': w['arrival'],
                'loc_iso': w['loc']['iso'],
                'loc_raw': w['loc']['raw'],
                'loc_overdue': w['loc']['overdue'],
                'glob_iso': w['glob']['iso'],
                'glob_raw': w['glob']['raw'],
                'glob_overdue': w['glob']['overdue'],
                'is_return_track': w['is_return_track'],
                'is_highlighted_return': w['is_highlighted_return'],
                'is_global_overdue': w['is_global_overdue']
            })
        result.append({
            'id': track['id'],
            'name': track['name'],
            'total': track['total'],
            'wagons': wagons_data
        })
    return jsonify({'tracks': result, 'total_wagons': len(move_list)})