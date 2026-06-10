# app/routes/history.py
# -*- coding: utf-8 -*-
"""
Маршруты для истории перемещений и архива.
"""

from flask import Blueprint, render_template, request, redirect, url_for, g
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.models import get_grouped_history, get_grouped_archive_history, get_conn, calculate_overstay, calculate_current_overstay, get_setting
from config import APP_VERSION

history_bp = Blueprint('history', __name__)


@history_bp.route('/history')
def history_page():
    station_id = g.get('station_id', 1)
    
    history_groups = get_grouped_history(station_id)
    
    conn = get_conn()
    c = conn.cursor()
    for group in history_groups:
        wagon_num = group['num']
        c.execute("SELECT id FROM wagon_visits WHERE wagon_number = ? AND is_archived = 0 AND station_id = ?", (wagon_num, station_id))
        row = c.fetchone()
        if row:
            visit_id = row[0]
            overstay = calculate_current_overstay(visit_id)
            if overstay > 0:
                progressive = get_setting('overstay_progressive', '0', station_id) == '1'
                if progressive:
                    range1_limit = int(get_setting('overstay_range1_limit', '4', station_id))
                    range1_rate = float(get_setting('overstay_range1_rate', '2000', station_id))
                    range2_limit = int(get_setting('overstay_range2_limit', '7', station_id))
                    range2_rate = float(get_setting('overstay_range2_rate', '2400', station_id))
                    range3_rate = float(get_setting('overstay_range3_rate', '3000', station_id))
                    amount = 0.0
                    days1 = min(overstay, range1_limit)
                    amount += days1 * range1_rate
                    remaining = overstay - days1
                    if remaining > 0:
                        days2 = min(remaining, range2_limit - range1_limit)
                        amount += days2 * range2_rate
                        remaining -= days2
                        if remaining > 0:
                            amount += remaining * range3_rate
                else:
                    fixed_rate = float(get_setting('overstay_fixed_rate', '2000', station_id))
                    amount = overstay * fixed_rate
                group['current_overstay'] = overstay
                group['current_amount'] = amount
            else:
                group['current_overstay'] = 0
                group['current_amount'] = 0
        else:
            group['current_overstay'] = 0
            group['current_amount'] = 0
    conn.close()
    
    return render_template('history.html',
                           history_groups=history_groups,
                           title="История перемещений",
                           session_role=request.user_role,
                           version=APP_VERSION)


@history_bp.route('/archive')
def archive_page():
    station_id = g.get('station_id', 1)
    conn = get_conn()
    c = conn.cursor()
    
    c.execute("""
        SELECT wv.wagon_number, wv.owner, wv.organization, wv.id as visit_id
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
    
    meta_dict = {}
    for row in meta_rows:
        num, owner, org, visit_id = row
        c.execute("SELECT MAX(timestamp) FROM archived_history WHERE visit_id = ? AND station_id = ?", (visit_id, station_id))
        dep_row = c.fetchone()
        departure_date = dep_row[0] if dep_row and dep_row[0] else "-"
        # ФОРМАТИРУЕМ ДАТУ ПРЯМО ЗДЕСЬ
        if departure_date != "-":
            try:
                dt = datetime.strptime(departure_date[:19], '%Y-%m-%d %H:%M:%S')
                departure_date = dt.strftime('%d-%m-%Y %H:%M')
            except:
                pass
        
        overstay, amount = calculate_overstay(visit_id)
        meta_dict[num] = {
            "owner": owner or "-",
            "org": org or "-",
            "dep": departure_date,
            "visit_id": visit_id,
            "overstay": overstay if overstay > 0 else 0,
            "amount": amount if amount > 0 else 0
        }

    history_data = get_grouped_archive_history(station_id)
    full_archive_data = []
    for item in history_data:
        num = item['num']
        meta = meta_dict.get(num, {"owner": "-", "org": "-", "dep": "-", "visit_id": None, "overstay": 0, "amount": 0})
        full_archive_data.append({
            "num": num,
            "owner": meta['owner'],
            "org": meta['org'],
            "dep": meta['dep'],
            "visit_id": meta['visit_id'],
            "overstay": meta['overstay'],
            "amount": meta['amount'],
            "last_status": item['last_status'],
            "last_time": item['last_time'],
            "events": item['events'],
            "count": item['count']
        })
    conn.close()
    return render_template('archive.html', archive_groups=full_archive_data, version=APP_VERSION)


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

    return render_template('archive_export_filter.html', years=years, version=APP_VERSION)