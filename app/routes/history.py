# app/routes/history.py
# -*- coding: utf-8 -*-
"""
Маршруты для истории перемещений и архива.
"""

from flask import Blueprint, render_template, request, redirect, url_for, g
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.models import get_grouped_history, get_grouped_archive_history, get_conn

history_bp = Blueprint('history', __name__)


@history_bp.route('/history')
def history_page():
    station_id = g.get('station_id', 1)
    return render_template('history.html',
                           history_groups=get_grouped_history(station_id),
                           title="История перемещений",
                           session_role=request.user_role)


@history_bp.route('/archive')
def archive_page():
    station_id = g.get('station_id', 1)
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT wv.wagon_number, wv.owner, wv.organization, wv.departure_time, wv.id as visit_id
        FROM wagon_visits wv
        JOIN (
            SELECT wagon_number, MAX(id) as max_id
            FROM wagon_visits
            WHERE is_archived = 1 AND station_id = ?
            GROUP BY wagon_number
        ) latest ON wv.wagon_number = latest.wagon_number AND wv.id = latest.max_id
        ORDER BY wv.wagon_number ASC
    """, (station_id,))
    meta_rows = c.fetchall()
    meta_dict = {row[0]: {"owner": row[1] or "-", "org": row[2] or "-", "dep": row[3] or "-", "visit_id": row[4]} for row in meta_rows}

    history_data = get_grouped_archive_history(station_id)
    full_archive_data = []
    for item in history_data:
        num = item['num']
        meta = meta_dict.get(num, {"owner": "-", "org": "-", "dep": "-", "visit_id": None})
        full_archive_data.append({
            "num": num,
            "owner": meta['owner'],
            "org": meta['org'],
            "dep": meta['dep'],
            "visit_id": meta['visit_id'],
            "last_status": item['last_status'],
            "last_time": item['last_time'],
            "events": item['events'],
            "count": item['count']
        })
    conn.close()
    return render_template('archive.html', archive_groups=full_archive_data)


@history_bp.route('/archive/export', methods=['GET', 'POST'])
def archive_export_filter():
    station_id = g.get('station_id', 1)
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT substr(arrival_time, 1, 4) as year,
               substr(arrival_time, 6, 2) as month
        FROM wagon_visits
        WHERE is_archived = 1 AND station_id = ? AND arrival_time IS NOT NULL
        ORDER BY year DESC, month DESC
    """, (station_id,))
    date_rows = c.fetchall()
    conn.close()

    years = {}
    for year, month in date_rows:
        if year not in years:
            years[year] = []
        if month not in years[year]:
            years[year].append(month)

    if request.method == 'POST':
        filter_type = request.form.get('filter_type', 'all')
        year = request.form.get('year', '')
        month = request.form.get('month', '')
        date_from = request.form.get('date_from', '')
        date_to = request.form.get('date_to', '')

        params = {'filter_type': filter_type, 'station_id': station_id}
        if filter_type == 'year' and year:
            params['year'] = year
        elif filter_type == 'month' and year and month:
            params['year'] = year
            params['month'] = month
        elif filter_type == 'period':
            params['date_from'] = date_from
            params['date_to'] = date_to

        return redirect(url_for('export.export_archive_excel', **params))

    return render_template('archive_export_filter.html', years=years)