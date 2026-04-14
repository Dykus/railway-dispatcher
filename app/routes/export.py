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

# Добавляем пути для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.models import get_conn

export_bp = Blueprint('export', __name__)


def apply_excel_styling(writer, sheet_name, has_notes=False):
    """Применяет стандартное оформление к листу Excel."""
    worksheet = writer.sheets[sheet_name]
    
    # Автоширина столбцов
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
    
    from openpyxl.styles import Font, Alignment
    # Заголовки жирным и по центру
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Данные: примечания — слева с переносом, остальное по центру
    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            if has_notes and cell.column_letter in ('F', 'G', 'H', 'D', 'E'):  # Примерные колонки с примечаниями
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
    """Сводка и детализация по архиву."""
    conn = get_conn()
    df_summary = pd.read_sql_query("""
        SELECT 
            w.wagon_number as "Номер вагона", 
            w.owner as "Транспортная компания", 
            w.organization as "Организация", 
            w.departure_time as "Время убытия"
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
    
    action_map = {'added': 'Добавлен', 'moved': 'Перемещен', 'departed': 'Убыл'}
    df_details['Тип действия'] = df_details['Тип действия'].map(action_map).fillna(df_details['Тип действия'])
    
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


@export_bp.route('/export_wagon_history/<wagon_number>')
def export_wagon_history(wagon_number):
    """История конкретного вагона."""
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT 
            action_type as "Тип действия", 
            from_track as "Откуда", 
            to_track as "Куда", 
            note as "Примечание", 
            timestamp as "Время" 
        FROM movement_history 
        WHERE wagon_number = ?
        ORDER BY timestamp ASC
    """, conn, params=(wagon_number,))
    conn.close()
    
    if df.empty:
        flash(f"Нет данных по вагону {wagon_number}", 'error')
        return redirect(url_for('history.history_page'))
    
    action_map = {'added': 'Добавлен', 'moved': 'Перемещен', 'departed': 'Убыл', 'edit': 'Изменён'}
    df['Тип действия'] = df['Тип действия'].map(action_map).fillna(df['Тип действия'])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=f'История {wagon_number}', index=False)
        apply_excel_styling(writer, f'История {wagon_number}', has_notes=True)
    
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"History_{wagon_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )


@export_bp.route('/export_wagon_archive/<wagon_number>')
def export_wagon_archive(wagon_number):
    """Архивная история конкретного вагона."""
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
    
    action_map = {'added': 'Добавлен', 'moved': 'Перемещен', 'departed': 'Убыл'}
    df['Тип действия'] = df['Тип действия'].map(action_map).fillna(df['Тип действия'])
    
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