# -*- coding: utf-8 -*-
"""
Маршруты для истории перемещений и архива.
"""

from flask import Blueprint, render_template, request
import sys
import os

# Добавляем пути для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.models import get_grouped_history, get_grouped_archive_history, get_conn

history_bp = Blueprint('history', __name__)


@history_bp.route('/history')
def history_page():
    return render_template('history.html',
                           history_groups=get_grouped_history(),
                           title="История перемещений",
                           session_role=request.user_role)


@history_bp.route('/archive')
def archive_page():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT wagon_number, owner, organization, departure_time FROM wagons WHERE is_archived = 1 ORDER BY wagon_number ASC""")
    meta_rows = c.fetchall()
    meta_dict = {row[0]: {"owner": row[1] or "-", "org": row[2] or "-", "dep": row[3] or "-"} for row in meta_rows}
    history_data = get_grouped_archive_history()
    full_archive_data = []
    for item in history_data:
        meta = meta_dict.get(item['num'], {"owner": "-", "org": "-", "dep": "-"})
        full_archive_data.append({
            "num": item['num'],
            "owner": meta['owner'],
            "org": meta['org'],
            "dep": meta['dep'],
            "last_status": item['last_status'],
            "last_time": item['last_time'],
            "events": item['events'],
            "count": item['count']
        })
    conn.close()
    return render_template('archive.html', archive_groups=full_archive_data)