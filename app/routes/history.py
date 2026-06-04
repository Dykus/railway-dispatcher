# -*- coding: utf-8 -*-
"""
Маршруты для истории перемещений и архива.
"""

from flask import Blueprint, render_template, request, redirect, url_for
import sys
import os

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


@history_bp.route('/archive/export', methods=['GET', 'POST'])
def archive_export_filter():
    """Форма фильтрации архива по датам перед экспортом."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT substr(arrival_time, 1, 4) as year,
               substr(arrival_time, 6, 2) as month
        FROM wagons 
        WHERE is_archived = 1 AND arrival_time IS NOT NULL
        ORDER BY year DESC, month DESC
    """)
    date_rows = c.fetchall()
    conn.close()

    # Группируем месяцы по годам
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

        params = {'filter_type': filter_type}
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