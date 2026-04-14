# -*- coding: utf-8 -*-
"""
Маршруты для истории перемещений и архива.
"""

from flask import Blueprint, render_template_string, request
import sys
import os

# Добавляем пути для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.models import get_grouped_history, get_grouped_archive_history, get_conn
from config import APP_VERSION

history_bp = Blueprint('history', __name__)

# ==================== HTML-ШАБЛОН ИСТОРИИ ====================
HISTORY_SPOILER_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f4f6f9; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        .nav-links { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .nav-link { display: inline-block; padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; }
        .nav-link-archive { background: #7f8c8d; }
        .nav-link-excel { background: #217346; }
        .nav-link-help { background: #16a085; }
        .search-box { margin-bottom: 20px; display: flex; gap: 10px; align-items: center; }
        .search-box input { flex: 1; padding: 10px; font-size: 16px; border: 1px solid #bdc3c7; border-radius: 5px; }
        .search-box button { padding: 10px 15px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; }
        .search-box button:hover { background: #2980b9; }
        .no-results { text-align: center; padding: 20px; color: #e74c3c; font-weight: bold; display: none; }
        details { border: 1px solid #ddd; border-radius: 6px; margin-bottom: 10px; background: white; }
        summary {
            padding: 12px;
            cursor: pointer;
            background: #ecf0f1;
            font-weight: bold;
            display: grid;
            grid-template-columns: 150px 120px 1fr 100px;
            align-items: center;
            gap: 10px;
            list-style: none;
        }
        summary::-webkit-details-marker { display: none; }
        summary::marker { display: none; }
        .wagon-num { font-size: 1.2em; color: #2980b9; }
        .status-added { background: #27ae60; color: white; padding: 2px 8px; border-radius: 12px; display: inline-block; text-align: center; }
        .status-moved { background: #f39c12; color: white; padding: 2px 8px; border-radius: 12px; display: inline-block; text-align: center; }
        .status-departed { background: #e74c3c; color: white; padding: 2px 8px; border-radius: 12px; display: inline-block; text-align: center; }
        .status-edit { background: #8e44ad; color: white; padding: 2px 8px; border-radius: 12px; display: inline-block; text-align: center; }
        .excel-wagon-btn {
            background: #217346;
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 12px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            justify-self: end;
            white-space: nowrap;
        }
        .excel-wagon-btn:hover { background: #1e5c3a; }
        .wagon-info { justify-self: start; }
        .details-content { padding: 15px; border-top: 1px solid #ddd; overflow-x: auto; }
        .history-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            margin-top: 5px;
        }
        .history-table th, .history-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }
        .history-table th {
            background-color: #34495e;
            color: white;
            font-weight: bold;
        }
        .history-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .history-table tr:hover {
            background-color: #f1f1f1;
        }
        .history-table th:nth-child(1), .history-table td:nth-child(1) { width: 100px; }
        .history-table th:nth-child(2), .history-table td:nth-child(2) { width: 120px; }
        .history-table th:nth-child(3), .history-table td:nth-child(3) { width: 120px; }
        .history-table th:nth-child(4), .history-table td:nth-child(4) { width: 150px; }
        .history-table th:nth-child(5), .history-table td:nth-child(5) { width: 150px; }
        .history-table th:nth-child(6), .history-table td:nth-child(6) { width: 250px; word-break: break-word; white-space: normal; }
        .history-table th:nth-child(7), .history-table td:nth-child(7) { width: 160px; }
        .edit-history-btn { background: none; border: none; cursor: pointer; color: #2980b9; font-size: 14px; margin-left: 8px; }
        .edit-history-btn:hover { color: #e67e22; }
        .edit-history-locked { color: #95a5a6; font-size: 12px; margin-left: 8px; cursor: help; }
        .wagon-details { display: block; }
    </style>
</head>
<body>
<div class="container">
    <div class="nav-links">
        <a href="/" class="nav-link">🏠 На главную</a>
        <a href="/archive" class="nav-link nav-link-archive">🗄️ Архив</a>
        <a href="/export_history_excel" class="nav-link nav-link-excel">📊 Скачать Excel (все вагоны)</a>
        <a href="/help" class="nav-link nav-link-help">❓ Помощь</a>
    </div>
    <h1>{{ title }}</h1>

    <div class="search-box">
        <input type="text" id="searchInput" placeholder="🔍 Поиск по номеру вагона..." autocomplete="off">
        <button id="clearSearch">Очистить</button>
    </div>
    <div id="noResultsMsg" class="no-results">❌ Ничего не найдено</div>

    <div id="historyContainer">
    {% if not history_groups %}
        <p>История пуста.</p>
    {% else %}
        {% for item in history_groups %}
            <details class="wagon-details" data-wagon-num="{{ item.num|lower }}">
                <summary>
                    <span class="wagon-num">{{ item.num }}</span>
                    <span class="status-{% if 'Добавлен' in item.last_status %}added{% elif 'Перемещен' in item.last_status %}moved{% elif 'Изменён' in item.last_status %}edit{% else %}departed{% endif %}">{{ item.last_status|safe }}</span>
                    <span class="wagon-info">📅 {{ item.last_time[:16] }} | Событий: {{ item.count }}</span>
                    <a href="/export_wagon_history/{{ item.num }}" class="excel-wagon-btn" title="Выгрузить историю только этого вагона">📊 Excel</a>
                </summary>
                <div class="details-content">
                    <table class="history-table">
                        <thead>
                            <tr><th>Действие</th><th>Откуда</th><th>Куда</th><th>ТК</th><th>Орг</th><th>Примечание</th><th>Время</th></tr>
                        </thead>
                        <tbody>
                            {% for ev in item.events %}
                                <tr>
                                    <td>{{ ev.action|safe }}</td>
                                    <td>{{ ev.from }}</td>
                                    <td>{{ ev.to }}</td>
                                    <td>{{ ev.owner }}</td>
                                    <td>{{ ev.org }}</td>
                                    <td>{{ ev.note }}</td>
                                    <td>
                                        {{ ev.time }}
                                        {% if session_role in ('supervisor', 'admin') %}
                                            {% if ev.is_last %}
                                                <button class="edit-history-btn" data-id="{{ ev.id }}" data-time="{{ ev.time }}" title="Редактировать дату последнего события">✏️</button>
                                            {% else %}
                                                <span class="edit-history-locked" title="Редактирование доступно только для последнего события, чтобы не нарушать хронологию">🔒</span>
                                            {% endif %}
                                        {% endif %}
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </details>
        {% endfor %}
    {% endif %}
    </div>
</div>
<script>
function filterWagons() {
    const searchTerm = document.getElementById('searchInput').value.trim().toLowerCase();
    const containers = document.querySelectorAll('.wagon-details');
    let visibleCount = 0;
    containers.forEach(container => {
        const wagonNum = container.getAttribute('data-wagon-num');
        if (wagonNum && wagonNum.includes(searchTerm)) {
            container.style.display = '';
            visibleCount++;
        } else {
            container.style.display = 'none';
        }
    });
    const noResultsDiv = document.getElementById('noResultsMsg');
    if (visibleCount === 0 && searchTerm !== '') {
        noResultsDiv.style.display = 'block';
    } else {
        noResultsDiv.style.display = 'none';
    }
}
document.getElementById('searchInput').addEventListener('input', filterWagons);
document.getElementById('clearSearch').addEventListener('click', function() {
    document.getElementById('searchInput').value = '';
    filterWagons();
});
document.querySelectorAll('.edit-history-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
        e.stopPropagation();
        const historyId = this.dataset.id;
        const oldTime = this.dataset.time;
        const newTime = prompt('Введите новую дату и время (поддерживается ГГГГ-ММ-ДД ЧЧ:ММ, ДД.ММ.ГГГГ ЧЧ:ММ, ДДММГГГГ и т.д.):', oldTime);
        if (newTime && newTime !== oldTime) {
            fetch(`/admin/edit_history/${historyId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'timestamp=' + encodeURIComponent(newTime)
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert(data.message);
                    location.reload();
                } else {
                    alert('Ошибка: ' + data.error);
                }
            })
            .catch(err => alert('Ошибка запроса: ' + err));
        }
    });
});
</script>
</body>
</html>"""

# ==================== HTML-ШАБЛОН АРХИВА ====================
ARCHIVE_SPOILER_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Архив</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #f4f6f9; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        h1 { color: #2c3e50; border-bottom: 2px solid #7f8c8d; padding-bottom: 10px; }
        .nav-links { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .nav-link { display: inline-block; padding: 10px 20px; background: #7f8c8d; color: white; text-decoration: none; border-radius: 5px; }
        .nav-link-history { background: #3498db; }
        .nav-link-excel { background: #217346; }
        .nav-link-help { background: #16a085; }
        .search-box { margin-bottom: 20px; display: flex; gap: 10px; align-items: center; }
        .search-box input { flex: 1; padding: 10px; font-size: 16px; border: 1px solid #bdc3c7; border-radius: 5px; }
        .search-box button { padding: 10px 15px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; }
        .search-box button:hover { background: #2980b9; }
        .no-results { text-align: center; padding: 20px; color: #e74c3c; font-weight: bold; display: none; }
        details { border: 1px solid #ddd; border-radius: 6px; margin-bottom: 10px; background: white; }
        summary {
            padding: 12px;
            cursor: pointer;
            background: #ecf0f1;
            font-weight: bold;
            display: grid;
            grid-template-columns: 150px 80px 200px 1fr 100px;
            align-items: center;
            gap: 10px;
            list-style: none;
        }
        summary::-webkit-details-marker { display: none; }
        summary::marker { display: none; }
        .wagon-num { font-size: 1.2em; color: #2980b9; }
        .wagon-status { background: #e74c3c; color: white; padding: 2px 8px; border-radius: 12px; display: inline-block; text-align: center; }
        .excel-wagon-btn {
            background: #217346;
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 12px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            justify-self: end;
            white-space: nowrap;
        }
        .excel-wagon-btn:hover { background: #1e5c3a; }
        .details-content { padding: 15px; border-top: 1px solid #ddd; overflow-x: auto; }
        .history-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            margin-top: 5px;
        }
        .history-table th, .history-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }
        .history-table th {
            background-color: #34495e;
            color: white;
            font-weight: bold;
        }
        .history-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .history-table tr:hover {
            background-color: #f1f1f1;
        }
        .history-table th:nth-child(1), .history-table td:nth-child(1) { width: 100px; }
        .history-table th:nth-child(2), .history-table td:nth-child(2) { width: 120px; }
        .history-table th:nth-child(3), .history-table td:nth-child(3) { width: 120px; }
        .history-table th:nth-child(4), .history-table td:nth-child(4) { width: 250px; word-break: break-word; white-space: normal; }
        .history-table th:nth-child(5), .history-table td:nth-child(5) { width: 160px; }
        .wagon-details { display: block; }
    </style>
</head>
<body>
<div class="container">
    <div class="nav-links">
        <a href="/" class="nav-link">🏠 На главную</a>
        <a href="/history" class="nav-link nav-link-history">📜 История</a>
        <a href="/export_archive_excel" class="nav-link nav-link-excel">📊 Скачать Excel (все вагоны)</a>
        <a href="/help" class="nav-link nav-link-help">❓ Помощь</a>
    </div>
    <h1>🗄️ Архив</h1>

    <div class="search-box">
        <input type="text" id="searchInput" placeholder="🔍 Поиск по номеру вагона..." autocomplete="off">
        <button id="clearSearch">Очистить</button>
    </div>
    <div id="noResultsMsg" class="no-results">❌ Ничего не найдено</div>

    <div id="archiveContainer">
    {% if not archive_groups %}
        <p>Архив пуст.</p>
    {% else %}
        {% for item in archive_groups %}
            <details class="wagon-details" data-wagon-num="{{ item.num|lower }}">
                <summary>
                    <span class="wagon-num">{{ item.num }}</span>
                    <span class="wagon-status">Убыл</span>
                    <span>{{ item.owner }}</span>
                    <span>{{ item.org }}</span>
                    <span>📅 {{ item.dep[:16] }}</span>
                    <span>Событий: {{ item.count }}</span>
                    <a href="/export_wagon_archive/{{ item.num }}" class="excel-wagon-btn" title="Выгрузить историю только этого вагона">📊 Excel</a>
                </summary>
                <div class="details-content">
                    <table class="history-table">
                        <thead>
                            <tr><th>Действие</th><th>Откуда</th><th>Куда</th><th>Примечание</th><th>Время</th></tr>
                        </thead>
                        <tbody>
                            {% for ev in item.events %}
                            <tr>
                                <td>{{ ev.action|safe }}</td>
                                <td>{{ ev.from }}</td>
                                <td>{{ ev.to }}</td>
                                <td>{{ ev.note }}</td>
                                <td>{{ ev.time }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </details>
        {% endfor %}
    {% endif %}
    </div>
</div>
<script>
function filterWagons() {
    const searchTerm = document.getElementById('searchInput').value.trim().toLowerCase();
    const containers = document.querySelectorAll('.wagon-details');
    let visibleCount = 0;
    containers.forEach(container => {
        const wagonNum = container.getAttribute('data-wagon-num');
        if (wagonNum && wagonNum.includes(searchTerm)) {
            container.style.display = '';
            visibleCount++;
        } else {
            container.style.display = 'none';
        }
    });
    const noResultsDiv = document.getElementById('noResultsMsg');
    if (visibleCount === 0 && searchTerm !== '') {
        noResultsDiv.style.display = 'block';
    } else {
        noResultsDiv.style.display = 'none';
    }
}
document.getElementById('searchInput').addEventListener('input', filterWagons);
document.getElementById('clearSearch').addEventListener('click', function() {
    document.getElementById('searchInput').value = '';
    filterWagons();
});
</script>
</body>
</html>"""


# ==================== МАРШРУТЫ ====================
@history_bp.route('/history')
def history_page():
    return render_template_string(HISTORY_SPOILER_TEMPLATE,
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
    return render_template_string(ARCHIVE_SPOILER_TEMPLATE, archive_groups=full_archive_data)