# app/routes/export.py
# -*- coding: utf-8 -*-
"""
Маршруты для экспорта данных в Excel.
"""

from flask import Blueprint, send_file, flash, redirect, url_for
import io
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.models import get_conn, calculate_overstay

export_bp = Blueprint('export', __name__)


def apply_excel_styling(writer, sheet_name, has_notes=False):
    """Применяет стандартное оформление к листу Excel."""
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


@export_bp.route('/export_excel')
def export_excel():
    """Отчёт по активным вагонам."""
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT 
            w.wagon_number as "Номер вагона", 
            w.owner as "Транспортная компания", 
            w.organization as "Организация", 
            t.name as "Путь", 
            w.arrival_time as "Время прибытия", 
            w.departure_time as "Глобальный срок" 
        FROM wagons w 
        JOIN tracks t ON w.track_id = t.id 
        WHERE w.status != 'departed' AND w.is_archived = 0
        ORDER BY w.wagon_number
    """, conn)
    conn.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Отчет', index=False)
        apply_excel_styling(writer, 'Отчет')

    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )


@export_bp.route('/export_history_excel')
def export_history_excel():
    """Полная история перемещений (активные вагоны)."""
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT 
            m.wagon_number as "Номер вагона", 
            m.action_type as "Тип действия", 
            m.from_track as "Откуда", 
            m.to_track as "Куда", 
            w.owner as "Транспортная компания",
            w.organization as "Организация",
            m.note as "Примечание", 
            m.timestamp as "Время" 
        FROM movement_history m
        LEFT JOIN wagons w ON m.wagon_number = w.wagon_number
        ORDER BY m.timestamp DESC
    """, conn)
    conn.close()

    action_map = {'added': 'Добавлен', 'moved': 'Перемещен', 'departed': 'Убыл', 'edit': 'Изменён'}
    df['Тип действия'] = df['Тип действия'].map(action_map).fillna(df['Тип действия'])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='История', index=False)
        apply_excel_styling(writer, 'История', has_notes=True)

    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"History_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )


@export_bp.route('/export_archive_excel')
def export_archive_excel():
    """Сводка и детализация по архиву с перепростоем и суммой."""
    conn = get_conn()
    # Три колонки времени: прибытие, глобальный срок, фактическое убытие
    df_summary = pd.read_sql_query("""
        SELECT 
            w.wagon_number as "Номер вагона", 
            w.owner as "Транспортная компания", 
            w.organization as "Организация", 
            w.arrival_time as "Время прибытия",
            w.departure_time as "Глобальный срок",
            (SELECT MAX(timestamp) FROM archived_history WHERE wagon_number = w.wagon_number) as "Фактическое убытие"
        FROM wagons w 
        WHERE w.is_archived = 1
        ORDER BY w.wagon_number
    """, conn)

    df_details = pd.read_sql_query("""
        SELECT 
            wagon_number as "Номер вагона", 
            action_type as "Тип действия", 
            from_track as "Откуда", 
            to_track as "Куда", 
            note as "Примечание", 
            timestamp as "Время"
        FROM archived_history
        ORDER BY wagon_number, timestamp ASC
    """, conn)
    conn.close()

    action_map = {'added': 'Добавлен', 'moved': 'Перемещен', 'departed': 'Убыл', 'edit': 'Изменён'}
    df_details['Тип действия'] = df_details['Тип действия'].map(action_map).fillna(df_details['Тип действия'])

    # Формат даты ДД-ММ-ГГГГ ЧЧ:ММ:СС
    try:
        df_summary['Время прибытия'] = pd.to_datetime(df_summary['Время прибытия']).dt.strftime('%d-%m-%Y %H:%M:%S')
        df_summary['Глобальный срок'] = pd.to_datetime(df_summary['Глобальный срок']).dt.strftime('%d-%m-%Y %H:%M:%S')
        df_summary['Фактическое убытие'] = pd.to_datetime(df_summary['Фактическое убытие']).dt.strftime('%d-%m-%Y %H:%M:%S')
    except:
        pass
    try:
        df_details['Время'] = pd.to_datetime(df_details['Время']).dt.strftime('%d-%m-%Y %H:%M:%S')
    except:
        pass

    # Добавляем перепростой и сумму
    overstays = []
    amounts = []
    for _, row in df_summary.iterrows():
        num = row['Номер вагона']
        over, amt = calculate_overstay(num)
        overstays.append(over if over > 0 else '')
        amounts.append(f"{amt:.2f}" if amt > 0 else '')
    df_summary['Перепростой, сут'] = overstays
    df_summary['Сумма, руб'] = amounts

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_summary.to_excel(writer, sheet_name='Сводка', index=False)
        apply_excel_styling(writer, 'Сводка')
        df_details.to_excel(writer, sheet_name='Детализация', index=False)
        apply_excel_styling(writer, 'Детализация', has_notes=True)

    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )


@export_bp.route('/export_wagon_archive/<wagon_number>')
def export_wagon_archive(wagon_number):
    """Архивная история конкретного вагона с перепростоем."""
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT 
            action_type as "Тип действия", 
            from_track as "Откуда", 
            to_track as "Куда", 
            note as "Примечание", 
            timestamp as "Время" 
        FROM archived_history 
        WHERE wagon_number = ?
        ORDER BY timestamp ASC
    """, conn, params=(wagon_number,))
    conn.close()

    if df.empty:
        flash(f"Нет данных по вагону {wagon_number} в архиве", 'error')
        return redirect(url_for('history.archive_page'))

    action_map = {'added': 'Добавлен', 'moved': 'Перемещен', 'departed': 'Убыл', 'edit': 'Изменён'}
    df['Тип действия'] = df['Тип действия'].map(action_map).fillna(df['Тип действия'])

    # Формат даты
    try:
        df['Время'] = pd.to_datetime(df['Время']).dt.strftime('%d-%m-%Y %H:%M:%S')
    except:
        pass

    overstay, amount = calculate_overstay(wagon_number)

    # Добавляем две строки с итогами
    extra_rows = pd.DataFrame([
        {'Тип действия': '', 'Откуда': '', 'Куда': '', 'Примечание': 'Перепростой, сут:' if overstay > 0 else '', 'Время': str(overstay) if overstay > 0 else ''},
        {'Тип действия': '', 'Откуда': '', 'Куда': '', 'Примечание': 'Сумма, руб:' if amount > 0 else '', 'Время': f"{amount:.2f}" if amount > 0 else ''}
    ])
    df = pd.concat([df, extra_rows], ignore_index=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=f'Архив {wagon_number}', index=False)
        apply_excel_styling(writer, f'Архив {wagon_number}', has_notes=True)

    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Archive_{wagon_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )