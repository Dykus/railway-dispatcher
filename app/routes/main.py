# -*- coding: utf-8 -*-
"""
Основные маршруты: главная страница, добавление, перемещение, архивация, справка.
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, flash
from datetime import datetime, timedelta
import sys
import os
import socket

# Добавляем пути для импорта из корня и app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import APP_VERSION
from app.models import (
    get_dashboard_data, move_wagon, depart_wagon, log_movement, log_action,
    find_slot_on_track, compact_track, get_conn
)

main_bp = Blueprint('main', __name__)

# ==================== HTML-ШАБЛОН ГЛАВНОЙ СТРАНИЦЫ (ПОЛНЫЙ) ====================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>ЖД Диспетчерская</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #2c3e50; margin-top: 0; }
        .header-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px; }
        .nav-buttons { display: flex; gap: 10px; flex-wrap: wrap; }
        .btn { color: white; padding: 8px 15px; border: none; border-radius: 5px; text-decoration: none; font-weight: bold; display: inline-flex; align-items: center; gap: 5px; cursor: pointer; }
        .btn-history { background: #2980b9; }
        .btn-excel { background: #217346; }
        .btn-archive { background: #7f8c8d; }
        .btn-help { background: #16a085; }
        .btn-changelog { background: #2c3e50; }
        .btn-backup { background: #27ae60; }
        .btn-add { background: #27ae60; }
        .btn-move { background: #f39c12; }
        .controls { display: flex; gap: 20px; margin-bottom: 30px; background: #ecf0f1; padding: 20px; border-radius: 8px; flex-wrap: wrap; }
        .control-box { flex: 1; min-width: 300px; }
        .control-box:first-child { border-right: 1px solid #bdc3c7; padding-right: 20px; }
        .control-box:last-child { padding-left: 20px; }
        input, select, textarea { padding: 10px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; width: 100%; }
        .time-group { display: flex; gap: 10px; align-items: flex-end; }
        .time-group div { flex: 1; text-align: center; }
        .time-group input { text-align: center; margin-bottom: 3px; }
        .time-group label { font-size: 11px; color: #555; display: block; margin-top: 2px; }
        .manual-time-inputs { display: flex; gap: 5px; align-items: center; flex-wrap: wrap; }
        .manual-time-inputs input { width: 120px; }
        .date-help { font-size: 10px; color: #7f8c8d; margin-top: 2px; }
        .date-buttons { display: flex; gap: 5px; margin-left: 10px; }
        .date-buttons button { background: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 3px; padding: 4px 8px; cursor: pointer; font-size: 11px; }
        .alert { padding: 10px; margin-bottom: 15px; border-radius: 4px; text-align: center; font-weight: bold; }
        .alert-success { background: #d4edda; color: #155724; border-left: 4px solid #27ae60; }
        .alert-error { background: #f8d7da; color: #721c24; border-left: 4px solid #e74c3c; }
        .track-wrapper { margin-bottom: 20px; border: 1px solid #ddd; border-radius: 8px; background: white; }
        .track-header { background: #34495e; color: white; padding: 10px 15px; font-weight: bold; display: flex; justify-content: space-between; border-radius: 8px 8px 0 0; }
        .track-body { position: relative; height: 200px; background: #ecf0f1; margin: 15px; border-bottom: 3px solid #7f8c8d; overflow-x: auto; }
        .wagon { position: absolute; top: 20px; height: 160px; border: 2px solid #2c3e50; border-radius: 6px; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; cursor: pointer; box-shadow: 2px 2px 5px rgba(0,0,0,0.2); min-width: 130px; padding: 8px; }
        .wagon:hover { transform: scale(1.02); z-index: 100; }
        .wagon.active { outline: 3px solid #f1c40f; }
        .wagon-normal { background: linear-gradient(135deg, #3498db, #2980b9); }
        .wagon-return-highlight { background: linear-gradient(135deg, #8e44ad, #9b59b6); border: 2px solid #f1c40f; }
        .wagon-global-overdue { background: linear-gradient(135deg, #6c3483, #4a235a); border: 2px solid #e74c3c; }
        .wagon-global-overdue-normal { background: linear-gradient(135deg, #922b21, #641e16); border: 2px solid #e74c3c; }
        .wagon-overdue { background: linear-gradient(135deg, #e74c3c, #c0392b); }
        .wagon-warn { background: linear-gradient(135deg, #f39c12, #d35400); }
        .wagon-number { font-size: 18px; font-weight: bold; text-align: center; margin-bottom: 8px; }
        .wagon-timer { font-family: monospace; font-size: 13px; margin-top: 5px; text-align: center; font-weight: bold; }
        .timer-label { font-size: 11px; opacity: 0.9; margin-right: 4px; }
        .total-count { background: #34495e; color: white; padding: 8px 15px; border-radius: 20px; font-weight: bold; }
        .refresh-btn { background: #95a5a6; border: none; padding: 5px 10px; border-radius: 4px; color: white; cursor: pointer; }
        #global-tooltip { display: none; position: fixed; background: #2c3e50; color: white; padding: 15px; border-radius: 8px; z-index: 1000; min-width: 280px; box-shadow: 0 5px 20px rgba(0,0,0,0.3); }
        .tooltip-row { display: flex; justify-content: space-between; margin-bottom: 8px; padding-bottom: 5px; border-bottom: 1px solid #465c71; }
        .timer-block { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #7f8c8d; }
        .timer-title { font-size: 12px; text-transform: uppercase; color: #bdc3c7; margin-bottom: 5px; }
        .btn-remove-large { background: #e74c3c; color: white; border: none; padding: 8px; border-radius: 4px; cursor: pointer; width: 100%; margin-top: 10px; font-weight: bold; }
        .close-tooltip { text-align: center; margin-top: 8px; font-size: 12px; color: #bdc3c7; cursor: pointer; }
        @media (max-width: 768px) { .control-box:first-child { border-right: none; padding-right: 0; } .control-box:last-child { padding-left: 0; } }
        #moveWagonSelect { height: auto; min-height: 120px; }
        #wagonSearchInput { margin-bottom: 5px; }
        .legend { background: #f8f9fa; padding: 10px; border-radius: 8px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 15px; align-items: center; font-size: 13px; }
        .legend-color { display: inline-block; width: 20px; height: 20px; border-radius: 4px; vertical-align: middle; margin-right: 4px; }
        .date-time-group { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-bottom: 5px; }
        .date-input { font-family: monospace; }
    </style>
</head>
<body>
<div class="container">
<div class="header-actions" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
    <div>
        <h1 style="margin: 0;">🚂 ЖД Диспетчерская</h1>
        <div style="font-size: 11px; color: #7f8c8d; margin-top: 2px;">Версия {{ version }}</div>
    </div>
    <div class="nav-buttons" style="display: flex; gap: 10px; align-items: center;">
        <div class="total-count">📦 Всего: {{ total_wagons }}</div>
        <a href="/history" class="btn btn-history">📜 История</a>
        <a href="/archive" class="btn btn-archive">🗄️ Архив</a>
        <a href="/export_excel" class="btn btn-excel">📊 Excel</a>
        {% if is_admin %}
            <a href="/admin/changelog" class="btn btn-changelog">📋 Список изменений</a>
            <a href="/admin/backups" class="btn btn-backup">💾 Бэкапы</a>
            <a href="/admin/logs" class="btn" style="background:#8e44ad;">📜 Журнал действий</a>
            <a href="/admin/ip_users" class="btn" style="background:#e67e22;">🔗 Привязка IP</a>
        {% endif %}
        <a href="/help" class="btn btn-help">❓ Помощь</a>
    </div>
</div>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for cat, msg in messages %}
                <div class="alert alert-{{ cat }}">{% if cat == 'success' %}✅{% else %}⚠️{% endif %} {{ msg }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <div class="legend">
        <div><span class="legend-color" style="background: linear-gradient(135deg,#3498db,#2980b9);"></span> Синий – обычный вагон (срок в норме или не задан)</div>
        <div><span class="legend-color" style="background: linear-gradient(135deg,#8e44ad,#9b59b6); border:1px solid #f1c40f;"></span> Фиолетовый – был на возвратном пути</div>
        <div><span class="legend-color" style="background: linear-gradient(135deg,#6c3483,#4a235a); border:2px solid #e74c3c;"></span> Тёмно-фиолетовый – был на возвратном пути И истёк глобальный срок</div>
        <div><span class="legend-color" style="background: linear-gradient(135deg,#922b21,#641e16); border:2px solid #e74c3c;"></span> Тёмно-красный – обычный вагон с истёкшим глобальным сроком</div>
        <div><span class="legend-color" style="background: linear-gradient(135deg,#f39c12,#d35400);"></span> Оранжевый – локальный срок &lt; 1 часа</div>
        <div><span class="legend-color" style="background: linear-gradient(135deg,#e74c3c,#c0392b);"></span> Красный – локальный срок истёк (просрочка)</div>
    </div>
    <div class="controls">
        <div class="control-box">
            <h3>➕ Новый вагон</h3>
            <form action="/add" method="POST" onsubmit="return validateDateTime('add')">
                <input type="text" id="new-wagon-number" name="number" placeholder="№ Вагона" required onblur="fetchWagonInfo(this.value)" value="{{ add_form_data.number if add_form_data else '' }}">
                <input type="text" id="new-wagon-owner" name="owner" placeholder="Транспортная компания" required value="{{ add_form_data.owner if add_form_data else '' }}">
                <input type="text" id="new-wagon-org" name="organization" placeholder="Организация" required value="{{ add_form_data.org if add_form_data else '' }}">
                <textarea name="note" rows="2" placeholder="Примечание">{{ add_form_data.note if add_form_data else '' }}</textarea>
                <div style="background:#e8f6f3;padding:10px;border-radius:5px;margin-top:10px">
                    <label style="font-weight:bold;">⏰ Глобальный срок:</label>
                    <div class="time-group">
                        <div><input type="number" name="cycle_days" min="0" value="{{ add_form_data.cycle_days if add_form_data else '0' }}"><label>Дни</label></div>
                        <div><input type="number" name="cycle_hours" min="0" value="{{ add_form_data.cycle_hours if add_form_data else '0' }}"><label>Часы</label></div>
                        <div><input type="number" name="cycle_mins" min="0" value="{{ add_form_data.cycle_mins if add_form_data else '0' }}"><label>Минуты</label></div>
                    </div>
                    <div style="margin-top:10px">
                        <label>📅 Начало отсчета (оставьте пустым для "сейчас"):</label>
                        <div class="date-time-group">
                            <input type="text" id="add_start_date" name="start_date" placeholder="ДД.ММ.ГГГГ" class="date-input" onblur="formatDateInput(this)" autocomplete="off" value="{{ add_form_data.start_date if add_form_data else '' }}">
                            <input type="text" id="add_start_time" name="start_time" placeholder="ЧЧ:ММ или ЧЧММ" class="date-input" onblur="formatTimeInput(this)" autocomplete="off" value="{{ add_form_data.start_time if add_form_data else '' }}">
                            <div class="date-buttons">
                                <button type="button" onclick="setToday('add')">Сегодня</button>
                                <button type="button" onclick="setNow('add')">Сейчас</button>
                                <button type="button" onclick="clearDateTime('add')">Очистить</button>
                            </div>
                        </div>
                        <div class="date-help">Формат: ДД.ММ.ГГГГ (можно без точек) и ЧЧ:ММ (можно без двоеточия). Оба поля либо заполнены, либо пусты.</div>
                    </div>
                </div>
                <select name="track_id" required>
                    <option value="">Выберите путь...</option>
                    {% for t in tracks %}
                        <option value="{{ t.id }}" {% if add_form_data and add_form_data.track_id|string == t.id|string %}selected{% endif %}>{{ t.name }}</option>
                    {% endfor %}
                </select>
                <button type="submit" class="btn-add">➕ Распределить</button>
            </form>
        </div>
        <div class="control-box">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <h3 style="margin:0">🔄 Переместить</h3>
                <button type="button" onclick="location.reload()" class="refresh-btn">🔄 Обновить</button>
            </div>
            <form action="/move" method="POST" onsubmit="return validateDateTime('move')">
                <input type="text" id="wagonSearchInput" placeholder="🔍 Поиск вагона..." onkeyup="filterWagons()">
                <select name="wagon_id" id="moveWagonSelect" required onchange="updateMoveNote()" size="5">
                    <option value="">Выберите вагон...</option>
                    {% for w in move_list %}
                        <option value="{{ w.id }}" data-note="{{ w.current_note }}" {% if move_form_data and move_form_data.wagon_id|string == w.id|string %}selected{% endif %}>{{ w.text }}</option>
                    {% endfor %}
                </select>
                <textarea name="note" id="moveNoteArea" rows="2" placeholder="Примечание...">{{ move_form_data.note if move_form_data else '' }}</textarea>
                <div style="background:#fef9e7;padding:10px;border-radius:5px;margin-top:10px">
                    <label style="font-weight:bold;">⏳ Локальный срок:</label>
                    <div class="time-group">
                        <div><input type="number" name="local_days" min="0" value="{{ move_form_data.local_days if move_form_data else '0' }}"><label>Дни</label></div>
                        <div><input type="number" name="local_hours" min="0" value="{{ move_form_data.local_hours if move_form_data else '0' }}"><label>Часы</label></div>
                        <div><input type="number" name="local_mins" min="0" value="{{ move_form_data.local_mins if move_form_data else '0' }}"><label>Минуты</label></div>
                    </div>
                    <div style="margin-top:10px">
                        <label>📅 Начало отсчета (оставьте пустым для "сейчас"):</label>
                        <div class="date-time-group">
                            <input type="text" id="move_start_date" name="start_date" placeholder="ДД.ММ.ГГГГ" class="date-input" onblur="formatDateInput(this)" autocomplete="off" value="{{ move_form_data.start_date if move_form_data else '' }}">
                            <input type="text" id="move_start_time" name="start_time" placeholder="ЧЧ:ММ или ЧЧММ" class="date-input" onblur="formatTimeInput(this)" autocomplete="off" value="{{ move_form_data.start_time if move_form_data else '' }}">
                            <div class="date-buttons">
                                <button type="button" onclick="setToday('move')">Сегодня</button>
                                <button type="button" onclick="setNow('move')">Сейчас</button>
                                <button type="button" onclick="clearDateTime('move')">Очистить</button>
                            </div>
                        </div>
                        <div class="date-help">Формат: ДД.ММ.ГГГГ (можно без точек) и ЧЧ:ММ (можно без двоеточия). Оба поля либо заполнены, либо пусты.</div>
                    </div>
                </div>
                <select name="new_track_id" required>
                    <option value="">На путь...</option>
                    {% for t in tracks %}
                        <option value="{{ t.id }}" {% if move_form_data and move_form_data.new_track_id|string == t.id|string %}selected{% endif %}>{{ t.name }}</option>
                    {% endfor %}
                </select>
                <button type="submit" class="btn-move">🔄 Переместить</button>
            </form>
        </div>
    </div>
    <div id="global-tooltip">
        <div class="tooltip-row"><span># Номер:</span><span id="tt-num"></span></div>
        <div class="tooltip-row"><span>🚚 ТК:</span><span id="tt-owner"></span></div>
        <div class="tooltip-row"><span>🏢 Орг:</span><span id="tt-org"></span></div>
        <div class="tooltip-row"><span>📝 Примечание:</span><span id="tt-note"></span></div>
        <div class="tooltip-row"><span>📅 Прибыл:</span><span id="tt-arr"></span></div>
        <div class="timer-block"><div class="timer-title">⏰ Локальный срок:</div><div id="tt-loc"></div></div>
        <div class="timer-block"><div class="timer-title">🌍 Глобальный срок:</div><div id="tt-glob"></div></div>
        <div id="tt-remove-container" style="margin-top:15px;text-align:center">
            <form id="tt-depart-form" method="POST" onsubmit="return confirm('Убрать в архив?')">
                <button type="submit" class="btn-remove-large">🗄️ УБРАТЬ В АРХИВ</button>
            </form>
        </div>
        <div id="tt-edit-container" style="margin-top:10px;text-align:center; border-top:1px solid #465c71; padding-top:10px;">
            <button type="button" class="btn-edit" style="background:#f39c12; color:white; border:none; padding:8px; border-radius:4px; cursor:pointer; width:100%;" onclick="openEditModal()">✏️ Редактировать вагон</button>
        </div>
        <div class="close-tooltip" onclick="closeTooltip()">❌ Закрыть</div>
    </div>
    {% for track in tracks %}
        <div class="track-wrapper" data-track-id="{{ track.id }}">
            <div class="track-header"><span>🛤️ {{ track.name }}</span><span>📦 Вагонов: {{ track.wagons|length }}</span></div>
            <div class="track-body">
                {% for w in track.wagons %}
                    {% set left_pct = (w.pos / track.total) * 100 %}
                    {% set is_loc_overdue = w.loc.overdue if w.loc.overdue is defined else false %}
                    {% set raw_loc_time = w.loc.raw if w.loc.raw is defined and w.loc.raw is number else 999999 %}
                    {% set is_global_overdue = w.is_global_overdue if w.is_global_overdue is defined else false %}
                    {% if is_loc_overdue %}
                        {% set wagon_class = "wagon wagon-overdue" %}
                    {% elif raw_loc_time < 3600 %}
                        {% set wagon_class = "wagon wagon-warn" %}
                    {% elif w.is_highlighted_return and is_global_overdue %}
                        {% set wagon_class = "wagon wagon-global-overdue" %}
                    {% elif w.is_highlighted_return %}
                        {% set wagon_class = "wagon wagon-return-highlight" %}
                    {% elif is_global_overdue %}
                        {% set wagon_class = "wagon wagon-global-overdue-normal" %}
                    {% else %}
                        {% set wagon_class = "wagon wagon-normal" %}
                    {% endif %}
                    <div class="{{ wagon_class }}" id="wagon-{{ w.id }}"
                         style="width:130px; left: {{ left_pct }}%;"
                         data-id="{{ w.id }}"
                         data-num="{{ w.num }}"
                         data-owner="{{ w.owner }}"
                         data-org="{{ w.org }}"
                         data-note="{{ w.note }}"
                         data-arrival="{{ w.arrival }}"
                         data-loc-iso="{{ w.loc.iso }}"
                         data-glob-iso="{{ w.glob.iso }}"
                         data-track-name="{{ track.name }}"
                         data-loc-raw="{{ w.loc.raw }}"
                         data-glob-raw="{{ w.glob.raw }}">
                        <div class="wagon-number">{{ w.num }}</div>
                        {% if w.loc.iso %}
                            <div class="wagon-timer" id="timer-loc-{{ w.id }}" data-time="{{ w.loc.iso }}" data-raw="{{ w.loc.raw }}">
                                <span class="timer-label">⏳</span><span>{{ w.loc.d }}д {{ "%02d"|format(w.loc.h) }}:{{ "%02d"|format(w.loc.m) }}:{{ "%02d"|format(w.loc.s) }}</span>
                            </div>
                        {% endif %}
                        {% if w.glob.iso %}
                            <div class="wagon-timer" id="timer-glob-{{ w.id }}" data-time="{{ w.glob.iso }}" data-raw="{{ w.glob.raw }}">
                                <span class="timer-label">🌍</span><span>{{ w.glob.d }}д {{ "%02d"|format(w.glob.h) }}:{{ "%02d"|format(w.glob.m) }}</span>
                            </div>
                        {% endif %}
                    </div>
                {% endfor %}
            </div>
        </div>
    {% endfor %}
</div>
<div id="editModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:2000; justify-content:center; align-items:center;">
    <div style="background:white; padding:20px; border-radius:10px; width:500px; max-width:90%;">
        <h3>✏️ Редактирование вагона</h3>
        <form id="editForm">
            <input type="hidden" id="edit_wagon_id">
            <label>Транспортная компания:</label>
            <input type="text" id="edit_owner" name="owner">
            <label>Организация:</label>
            <input type="text" id="edit_org" name="organization">
            <label>Примечание:</label>
            <textarea id="edit_note" name="note" rows="2"></textarea>
            <label>Время прибытия (ГГГГ-ММ-ДД ЧЧ:ММ:СС):</label>
            <input type="text" id="edit_arrival" name="arrival_time" placeholder="2026-04-10 14:30:00">
            <label>Глобальный срок (ГГГГ-ММ-ДД ЧЧ:ММ:СС):</label>
            <input type="text" id="edit_global" name="departure_time" placeholder="2026-04-12 14:30:00">
            <label>Локальный срок (ГГГГ-ММ-ДД ЧЧ:ММ:СС):</label>
            <input type="text" id="edit_local" name="local_departure_time" placeholder="2026-04-11 14:30:00">
            <div style="margin-top:15px; text-align:right;">
                <button type="button" onclick="closeEditModal()" style="padding:5px 10px;">Отмена</button>
                <button type="submit" style="padding:5px 10px; background:#27ae60; color:white; border:none;">Сохранить</button>
            </div>
        </form>
    </div>
</div>
<script>
let activeWagonId = null;
let activeWagonNum = null;
let activeWagonOwner = null;
let activeWagonOrg = null;
let activeWagonNote = null;
let activeWagonArrival = null;
let activeWagonGlobal = null;
let activeWagonLocal = null;
const tooltip = document.getElementById('global-tooltip');
const removeContainer = document.getElementById('tt-remove-container');
const editContainer = document.getElementById('tt-edit-container');

function normalizeDateTimeForEdit(dateTimeStr) {
    if (!dateTimeStr || dateTimeStr.trim() === '') return '';
    let str = dateTimeStr.trim();
    if (/^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$/.test(str)) return str;
    if (/^\\d{4}-\\d{2}-\\d{2}$/.test(str)) return str + ' 00:00:00';
    let match = str.match(/^(\\d{2})[.\\-](\\d{2})[.\\-](\\d{4})(?: (\\d{2}):(\\d{2})(?::(\\d{2}))?)?$/);
    if (match) {
        let day = match[1], month = match[2], year = match[3];
        let hour = match[4] || '00', minute = match[5] || '00', second = match[6] || '00';
        return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
    }
    let digits = str.replace(/[^\\d]/g, '');
    if (digits.length === 8) {
        let day = digits.slice(0,2), month = digits.slice(2,4), year = digits.slice(4,8);
        return `${year}-${month}-${day} 00:00:00`;
    }
    if (digits.length === 12) {
        let day = digits.slice(0,2), month = digits.slice(2,4), year = digits.slice(4,8);
        let hour = digits.slice(8,10), minute = digits.slice(10,12);
        return `${year}-${month}-${day} ${hour}:${minute}:00`;
    }
    return str;
}

function formatDateInput(input) {
    let value = input.value.trim();
    if (value === '') return;
    let digits = value.replace(/[^\\d]/g, '');
    if (digits.length === 8) {
        let day = digits.substring(0, 2);
        let month = digits.substring(2, 4);
        let year = digits.substring(4, 8);
        input.value = `${year}-${month}-${day}`;
    } else if (digits.length === 6) {
        let day = digits.substring(0, 2);
        let month = digits.substring(2, 4);
        let year = digits.substring(4, 6);
        input.value = `20${year}-${month}-${day}`;
    } else if (value.includes('.') && value.split('.').length === 3) {
        let parts = value.split('.');
        if (parts[0].length === 2 && parts[1].length === 2 && parts[2].length === 4) {
            input.value = `${parts[2]}-${parts[1]}-${parts[0]}`;
        }
    } else if (value.includes('-') && value.split('-').length === 3) {
        return;
    }
}

function formatTimeInput(input) {
    let value = input.value.trim();
    if (value === '') return;
    let digits = value.replace(/[^\\d]/g, '');
    if (digits.length === 4) {
        let hours = digits.substring(0, 2);
        let minutes = digits.substring(2, 4);
        if (parseInt(hours) <= 23 && parseInt(minutes) <= 59) {
            input.value = `${hours}:${minutes}`;
        }
    } else if (digits.length === 3) {
        let hours = digits.substring(0, 1);
        let minutes = digits.substring(1, 3);
        if (parseInt(hours) <= 23 && parseInt(minutes) <= 59) {
            input.value = `0${hours}:${minutes}`;
        }
    } else if (digits.length === 2) {
        let hours = digits;
        if (parseInt(hours) <= 23) {
            input.value = `${hours}:00`;
        }
    } else if (digits.length === 1) {
        let hours = digits;
        if (parseInt(hours) <= 23) {
            input.value = `0${hours}:00`;
        }
    } else if (value.includes(':') && value.split(':').length === 2) {
        return;
    }
}

function setToday(formType) {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    const dateValue = `${year}-${month}-${day}`;
    if (formType === 'add') {
        document.getElementById('add_start_date').value = dateValue;
    } else {
        document.getElementById('move_start_date').value = dateValue;
    }
}

function setNow(formType) {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const timeValue = `${hours}:${minutes}`;
    if (formType === 'add') {
        document.getElementById('add_start_time').value = timeValue;
    } else {
        document.getElementById('move_start_time').value = timeValue;
    }
}

function clearDateTime(formType) {
    if (formType === 'add') {
        document.getElementById('add_start_date').value = '';
        document.getElementById('add_start_time').value = '';
    } else {
        document.getElementById('move_start_date').value = '';
        document.getElementById('move_start_time').value = '';
    }
}

function validateDateTime(formType) {
    let dateField, timeField;
    if (formType === 'add') {
        dateField = document.getElementById('add_start_date');
        timeField = document.getElementById('add_start_time');
    } else {
        dateField = document.getElementById('move_start_date');
        timeField = document.getElementById('move_start_time');
    }
    const hasDate = dateField && dateField.value.trim() !== '';
    const hasTime = timeField && timeField.value.trim() !== '';
    if ((hasDate && !hasTime) || (!hasDate && hasTime)) {
        alert('Ошибка: Если вы заполняете дату, нужно заполнить и время, и наоборот. Либо оставьте оба поля пустыми (будет использовано текущее время).');
        return false;
    }
    if (hasDate && hasTime) {
        const datePattern = /^\\d{4}-\\d{2}-\\d{2}$/;
        const timePattern = /^\\d{2}:\\d{2}$/;
        if (!datePattern.test(dateField.value.trim())) {
            alert('Неверный формат даты. Используйте ДД.ММ.ГГГГ (или просто цифрами).');
            return false;
        }
        if (!timePattern.test(timeField.value.trim())) {
            alert('Неверный формат времени. Используйте ЧЧ:ММ (или просто ЧЧММ).');
            return false;
        }
    }
    return true;
}

function filterWagons() {
    const input = document.getElementById('wagonSearchInput');
    const filter = input.value.toLowerCase();
    const select = document.getElementById('moveWagonSelect');
    const options = select.options;
    let hasVisible = false;
    for (let i = 0; i < options.length; i++) {
        const text = options[i].text.toLowerCase();
        if (text.includes(filter) || filter === '') {
            options[i].style.display = '';
            hasVisible = true;
        } else {
            options[i].style.display = 'none';
        }
    }
    let noResultMsg = document.getElementById('noResultMsg');
    if (!hasVisible && filter !== '') {
        if (!noResultMsg) {
            const msg = document.createElement('div');
            msg.id = 'noResultMsg';
            msg.style.color = '#e74c3c';
            msg.style.fontSize = '12px';
            msg.style.marginTop = '5px';
            msg.innerText = '❌ Ничего не найдено';
            select.parentNode.insertBefore(msg, select.nextSibling);
        }
    } else if (noResultMsg) {
        noResultMsg.remove();
    }
}

function updateMoveNote() {
    const select = document.getElementById('moveWagonSelect');
    const selectedOption = select.options[select.selectedIndex];
    const note = selectedOption ? selectedOption.getAttribute('data-note') : '';
    document.getElementById('moveNoteArea').value = note || '';
}

function openTooltip(el, id, num, owner, org, note, arrival, locIso, globIso, trackName, locRaw, globRaw) {
    if (activeWagonId === id) { closeTooltip(); return; }
    document.getElementById('tt-num').innerText = num;
    document.getElementById('tt-owner').innerText = owner || '-';
    document.getElementById('tt-org').innerText = org || '-';
    document.getElementById('tt-note').innerHTML = note || '-';
    document.getElementById('tt-arr').innerText = arrival;
    const ttLoc = document.getElementById('tt-loc');
    const ttGlob = document.getElementById('tt-glob');
    if (locIso) {
        ttLoc.setAttribute('data-time', locIso);
        ttLoc.setAttribute('data-raw', locRaw);
        ttLoc.innerText = '...';
    } else {
        ttLoc.removeAttribute('data-time');
        ttLoc.innerText = 'Нет';
    }
    if (globIso) {
        ttGlob.setAttribute('data-time', globIso);
        ttGlob.setAttribute('data-raw', globRaw);
        ttGlob.innerText = '...';
    } else {
        ttGlob.removeAttribute('data-time');
        ttGlob.innerText = 'Нет';
    }
    document.getElementById('tt-depart-form').action = '/depart/' + id;
    activeWagonId = id;
    activeWagonNum = num;
    activeWagonOwner = owner;
    activeWagonOrg = org;
    activeWagonNote = note;
    activeWagonArrival = arrival;
    activeWagonGlobal = globIso ? globIso.replace('T', ' ') : '';
    activeWagonLocal = locIso ? locIso.replace('T', ' ') : '';
    document.querySelectorAll('.wagon').forEach(w => w.classList.remove('active'));
    el.classList.add('active');
    const allowedTracks = ["Ст. Черкасов Камень", "Пост №2"];
    if (allowedTracks.includes(trackName.trim())) {
        removeContainer.style.display = 'block';
    } else {
        removeContainer.style.display = 'none';
    }
    editContainer.style.display = 'block';
    const rect = el.getBoundingClientRect();
    let left = rect.right + 10;
    let top = rect.top;
    if (left + 300 > window.innerWidth) left = rect.left - 310;
    if (top + 400 > window.innerHeight) top = window.innerHeight - 410;
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
    tooltip.style.display = 'block';
    updateTooltipTimers();
}

function closeTooltip() {
    tooltip.style.display = 'none';
    if (activeWagonId) {
        const w = document.getElementById('wagon-' + activeWagonId);
        if (w) w.classList.remove('active');
    }
    activeWagonId = null;
}

function openEditModal() {
    if (!activeWagonId) return;
    document.getElementById('edit_wagon_id').value = activeWagonId;
    document.getElementById('edit_owner').value = activeWagonOwner || '';
    document.getElementById('edit_org').value = activeWagonOrg || '';
    document.getElementById('edit_note').value = activeWagonNote === '-' ? '' : activeWagonNote;
    document.getElementById('edit_arrival').value = activeWagonArrival && activeWagonArrival !== '-' ? activeWagonArrival.replace(/\\./g, '-') : '';
    document.getElementById('edit_global').value = activeWagonGlobal || '';
    document.getElementById('edit_local').value = activeWagonLocal || '';
    document.getElementById('editModal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
}

document.getElementById('editForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const wagonId = document.getElementById('edit_wagon_id').value;
    const formData = new FormData(this);
    let arrival = formData.get('arrival_time');
    let globalDeadline = formData.get('departure_time');
    let localDeadline = formData.get('local_departure_time');
    if (arrival) formData.set('arrival_time', normalizeDateTimeForEdit(arrival));
    if (globalDeadline) formData.set('departure_time', normalizeDateTimeForEdit(globalDeadline));
    if (localDeadline) formData.set('local_departure_time', normalizeDateTimeForEdit(localDeadline));
    const response = await fetch(`/admin/edit_wagon/${wagonId}`, {
        method: 'POST',
        body: formData
    });
    const result = await response.json();
    if (result.success) {
        alert(result.message);
        location.reload();
    } else {
        alert('Ошибка: ' + result.message);
    }
});

function formatTimer(d, h, m, s) {
    if (d > 0) return d + 'д ' + String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
    return String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
}

function formatTimerShort(d, h, m) {
    if (d > 0) return d + 'д ' + String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0');
    return String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0');
}

function formatNegativeTime(seconds) {
    let absSec = Math.abs(seconds);
    let s = absSec % 60;
    let m = Math.floor((absSec % 3600) / 60);
    let h = Math.floor(absSec / 3600);
    let d = Math.floor(h / 24);
    h = h % 24;
    let str = '';
    if (d > 0) str += d + 'д ';
    str += String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
    return '-' + str;
}

function updateTooltipTimers() {
    if (!activeWagonId) return;
    const now = new Date();
    const ttLoc = document.getElementById('tt-loc');
    const ttGlob = document.getElementById('tt-glob');
    const locTime = ttLoc.getAttribute('data-time');
    if (locTime) {
        const dep = new Date(locTime);
        const diff = Math.floor((dep - now) / 1000);
        if (diff > 0) {
            let s = diff % 60;
            let m = Math.floor((diff % 3600) / 60);
            let h = Math.floor(diff / 3600);
            let d = Math.floor(h / 24);
            h = h % 24;
            ttLoc.innerHTML = formatTimer(d, h, m, s);
            ttLoc.style.color = diff < 3600 ? '#e67e22' : '#2ecc71';
        } else {
            ttLoc.innerHTML = 'ПРОСРОЧЕНО на ' + formatNegativeTime(diff);
            ttLoc.style.color = '#e74c3c';
        }
    }
    const globTime = ttGlob.getAttribute('data-time');
    if (globTime) {
        const dep = new Date(globTime);
        const diff = Math.floor((dep - now) / 1000);
        if (diff > 0) {
            let s = diff % 60;
            let m = Math.floor((diff % 3600) / 60);
            let h = Math.floor(diff / 3600);
            let d = Math.floor(h / 24);
            h = h % 24;
            ttGlob.innerHTML = formatTimer(d, h, m, s);
            ttGlob.style.color = diff < 3600 ? '#e67e22' : '#2ecc71';
        } else {
            ttGlob.innerHTML = 'ИСТЕК (просрочка ' + formatNegativeTime(diff) + ')';
            ttGlob.style.color = '#e74c3c';
        }
    }
}

function updateAllTimers() {
    const now = new Date();
    document.querySelectorAll('[id^="timer-loc-"]').forEach(el => {
        const timeStr = el.getAttribute('data-time');
        if (timeStr) {
            const dep = new Date(timeStr);
            const diff = Math.floor((dep - now) / 1000);
            if (diff > 0) {
                let s = diff % 60;
                let m = Math.floor((diff % 3600) / 60);
                let h = Math.floor(diff / 3600);
                let d = Math.floor(h / 24);
                h = h % 24;
                el.innerHTML = '<span class="timer-label">⏳</span> ' + formatTimer(d, h, m, s);
                const wagon = el.closest('.wagon');
                if (diff < 300 && wagon && !wagon.classList.contains('active')) {
                    wagon.classList.remove('wagon-normal', 'wagon-return-highlight', 'wagon-warn');
                    wagon.classList.add('wagon-overdue');
                }
            } else {
                el.innerHTML = '<span class="timer-label">⚠️</span> ПРОСРОЧЕНО на ' + formatNegativeTime(diff);
                const wagon = el.closest('.wagon');
                if (wagon && !wagon.classList.contains('active')) {
                    wagon.classList.remove('wagon-normal', 'wagon-return-highlight', 'wagon-warn');
                    wagon.classList.add('wagon-overdue');
                }
            }
        }
    });
    document.querySelectorAll('[id^="timer-glob-"]').forEach(el => {
        const timeStr = el.getAttribute('data-time');
        if (timeStr) {
            const dep = new Date(timeStr);
            const diff = Math.floor((dep - now) / 1000);
            if (diff > 0) {
                let s = diff % 60;
                let m = Math.floor((diff % 3600) / 60);
                let h = Math.floor(diff / 3600);
                let d = Math.floor(h / 24);
                h = h % 24;
                el.innerHTML = '<span class="timer-label">🌍</span> ' + formatTimerShort(d, h, m);
                const wagon = el.closest('.wagon');
                if (diff <= 0 && wagon) {
                    if (wagon.classList.contains('wagon-return-highlight')) {
                        wagon.classList.remove('wagon-return-highlight');
                        wagon.classList.add('wagon-global-overdue');
                    } else if (wagon.classList.contains('wagon-normal')) {
                        wagon.classList.remove('wagon-normal');
                        wagon.classList.add('wagon-global-overdue-normal');
                    }
                }
            } else {
                el.innerHTML = '<span class="timer-label">💀</span> ИСТЕК (просрочка ' + formatNegativeTime(diff) + ')';
                const wagon = el.closest('.wagon');
                if (wagon) {
                    if (wagon.classList.contains('wagon-return-highlight')) {
                        wagon.classList.remove('wagon-return-highlight');
                        wagon.classList.add('wagon-global-overdue');
                    } else if (wagon.classList.contains('wagon-normal')) {
                        wagon.classList.remove('wagon-normal');
                        wagon.classList.add('wagon-global-overdue-normal');
                    }
                }
            }
        }
    });
    updateTooltipTimers();
}

function fetchWagonInfo(num) {
    if (!num) return;
    fetch('/api/wagon_info?num=' + encodeURIComponent(num))
        .then(r => r.json())
        .then(d => {
            if (d.owner) document.getElementById('new-wagon-owner').value = d.owner;
            if (d.org) document.getElementById('new-wagon-org').value = d.org;
        })
        .catch(e => console.log('Ошибка:', e));
}

function updateDashboard() {
    fetch('/api/dashboard_data')
        .then(response => response.json())
        .then(data => {
            const totalCountElem = document.querySelector('.total-count');
            if (totalCountElem) totalCountElem.innerHTML = '📦 Всего: ' + data.total_wagons;
            for (let newTrack of data.tracks) {
                const trackWrapper = document.querySelector(`.track-wrapper[data-track-id="${newTrack.id}"]`);
                if (!trackWrapper) continue;
                const trackHeader = trackWrapper.querySelector('.track-header span:last-child');
                if (trackHeader) trackHeader.innerHTML = '📦 Вагонов: ' + newTrack.wagons.length;
                const trackBody = trackWrapper.querySelector('.track-body');
                if (!trackBody) continue;
                let newHtml = '';
                for (let w of newTrack.wagons) {
                    let leftPct = (w.pos / newTrack.total) * 100;
                    let wagonClass = 'wagon';
                    if (w.loc_overdue) wagonClass += ' wagon-overdue';
                    else if (w.loc_raw < 3600) wagonClass += ' wagon-warn';
                    else if (w.is_highlighted_return && w.is_global_overdue) wagonClass += ' wagon-global-overdue';
                    else if (w.is_highlighted_return) wagonClass += ' wagon-return-highlight';
                    else if (w.is_global_overdue) wagonClass += ' wagon-global-overdue-normal';
                    else wagonClass += ' wagon-normal';
                    
                    let locTimerHtml = '';
                    if (w.loc_iso) {
                        let days = Math.floor(w.loc_raw / 86400);
                        let hours = Math.floor((w.loc_raw % 86400) / 3600);
                        let minutes = Math.floor((w.loc_raw % 3600) / 60);
                        let seconds = Math.floor(w.loc_raw % 60);
                        locTimerHtml = `<div class="wagon-timer" id="timer-loc-${w.id}" data-time="${w.loc_iso}" data-raw="${w.loc_raw}"><span class="timer-label">⏳</span><span>${days}д ${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}</span></div>`;
                    }
                    let globTimerHtml = '';
                    if (w.glob_iso) {
                        let days = Math.floor(w.glob_raw / 86400);
                        let hours = Math.floor((w.glob_raw % 86400) / 3600);
                        let minutes = Math.floor((w.glob_raw % 3600) / 60);
                        globTimerHtml = `<div class="wagon-timer" id="timer-glob-${w.id}" data-time="${w.glob_iso}" data-raw="${w.glob_raw}"><span class="timer-label">🌍</span><span>${days}д ${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}</span></div>`;
                    }
                    
                    newHtml += `
                        <div class="${wagonClass}" id="wagon-${w.id}"
                             style="width:130px; left: ${leftPct}%;"
                             data-id="${w.id}"
                             data-num="${w.num.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}"
                             data-owner="${w.owner.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}"
                             data-org="${w.org.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}"
                             data-note="${w.note.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}"
                             data-arrival="${w.arrival}"
                             data-loc-iso="${w.loc_iso}"
                             data-glob-iso="${w.glob_iso}"
                             data-track-name="${newTrack.name.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}"
                             data-loc-raw="${w.loc_raw}"
                             data-glob-raw="${w.glob_raw}">
                            <div class="wagon-number">${w.num.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
                            ${locTimerHtml}
                            ${globTimerHtml}
                        </div>
                    `;
                }
                trackBody.innerHTML = newHtml;
            }
            updateAllTimers();
        })
        .catch(err => console.log('Ошибка обновления дашборда:', err));
}

// Единый обработчик кликов для открытия и закрытия тултипа (делегирование)
document.addEventListener('click', function(e) {
    const wagon = e.target.closest('.wagon');
    if (wagon) {
        e.stopPropagation();
        const id = wagon.dataset.id;
        const num = wagon.dataset.num;
        const owner = wagon.dataset.owner;
        const org = wagon.dataset.org;
        const note = wagon.dataset.note;
        const arrival = wagon.dataset.arrival;
        const locIso = wagon.dataset.locIso;
        const globIso = wagon.dataset.globIso;
        const trackName = wagon.dataset.trackName;
        const locRaw = parseFloat(wagon.dataset.locRaw);
        const globRaw = parseFloat(wagon.dataset.globRaw);
        openTooltip(wagon, id, num, owner, org, note, arrival, locIso, globIso, trackName, locRaw, globRaw);
    } else {
        closeTooltip();
    }
});

setInterval(updateAllTimers, 1000);
setInterval(updateDashboard, 5000);
</script>
</body>
</html>"""

# ==================== HTML-ШАБЛОН СПРАВКИ ====================
HELP_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Инструкция диспетчера - ЖД Диспетчерская</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #2980b9; margin-top: 25px; }
        .nav-link { display: inline-block; padding: 8px 15px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-bottom: 20px; }
        .color-box { display: inline-block; width: 20px; height: 20px; border-radius: 4px; vertical-align: middle; margin-right: 8px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #ecf0f1; }
        .note { background: #fef9e7; padding: 10px; border-left: 4px solid #f39c12; margin: 15px 0; }
        .address { background: #e8f4fd; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 1.2em; text-align: center; margin: 20px 0; }
    </style>
</head>
<body>
<div class="container">
    <a href="/" class="nav-link">🏠 На главную</a>
    <h1>🚂 Инструкция для диспетчера</h1>
    
    <h2>1. Как подключиться</h2>
    <p>Откройте браузер (Chrome, Firefox, Edge) и введите адрес:</p>
    <div class="address">http://{{ server_ip }}:5000</div>
    <p>Если вы работаете с того же компьютера, где запущена программа, используйте <strong>http://127.0.0.1:5000</strong>.</p>
    <div class="note">📌 После входа вы увидите главный экран со списком путей и вагонов.</div>
    
    <h2>2. Главный экран</h2>
    <p>На главной странице отображаются:</p>
    <ul>
        <li><strong>Пути</strong> (станции, посты, цеха) в виде горизонтальных полос.</li>
        <li><strong>Вагоны</strong> – цветные прямоугольники с номером и таймерами.</li>
        <li>Панель управления слева – <strong>«Новый вагон»</strong>, справа – <strong>«Переместить»</strong>.</li>
        <li>Вверху – кнопки: История, Архив, Excel, Помощь (эта страница).</li>
    </ul>
    
    <h2>3. Добавление нового вагона</h2>
    <ul>
        <li>Заполните поля: <strong>№ вагона</strong>, <strong>Транспортная компания</strong>, <strong>Организация</strong>.</li>
        <li>При желании укажите <strong>глобальный срок</strong> – общее время на станции. Для этого задайте дни, часы, минуты.</li>
        <li>Можно указать <strong>начало отсчёта</strong> (дата и время). Если оставить поля пустыми – срок начнётся с текущего момента.</li>
        <li>Выберите <strong>путь</strong>, на который ставится вагон.</li>
        <li>Нажмите <strong>«Распределить»</strong>.</li>
    </ul>
    <div class="note">💡 Если вагон уже был в архиве, он восстановится с сохранением истории.</div>
    
    <h2>4. Перемещение вагона</h2>
    <ul>
        <li>В правой панели найдите вагон (помогает поле <strong>«Поиск вагона»</strong>).</li>
        <li>Выберите его из списка – примечание подставится автоматически.</li>
        <li>При необходимости измените <strong>примечание</strong>.</li>
        <li>Задайте <strong>локальный срок</strong> – время, которое вагон должен провести на новом пути (дни, часы, минуты).</li>
        <li>Укажите <strong>начало отсчёта</strong> (дата/время) или оставьте пустым – будет использовано текущее время.</li>
        <li>Выберите <strong>путь назначения</strong> и нажмите <strong>«Переместить»</strong>.</li>
    </ul>
    
    <h2>5. Цвета вагонов (что означают)</h2>
    <table>
        <tr><th>Цвет</th><th>Значение</th></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#3498db,#2980b9);"></span> Синий</td><td>Обычный вагон (срок в норме или не задан)</td></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#8e44ad,#9b59b6); border:1px solid #f1c40f;"></span> Фиолетовый (с жёлтой рамкой)</td><td>Вагон уже побывал на возвратном пути («Пост №2» или «Ст. Черкасов Камень»)</td></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#6c3483,#4a235a); border:2px solid #e74c3c;"></span> Тёмно-фиолетовый</td><td>Был на возвратном пути И истёк глобальный срок</td></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#922b21,#641e16); border:2px solid #e74c3c;"></span> Тёмно-красный</td><td>Обычный вагон с истёкшим глобальным сроком</td></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#f39c12,#d35400);"></span> Оранжевый</td><td>Локальный срок истекает менее чем через час</td></tr>
        <tr><td><span class="color-box" style="background: linear-gradient(135deg,#e74c3c,#c0392b);"></span> Красный</td><td>Локальный срок уже истёк (просрочка)</td></tr>
    </table>
    <p><strong>Локальный срок</strong> – время на текущем пути. <strong>Глобальный срок</strong> – общее время на станции.</p>
    
    <h2>6. Информация о вагоне</h2>
    <p>Кликните по вагону – появится всплывающее окно с подробностями:</p>
    <ul>
        <li>Номер вагона, транспортная компания, организация.</li>
        <li>Примечание, время прибытия.</li>
        <li><strong>Таймеры</strong> локального и глобального сроков (обратный отсчёт).</li>
        <li>Если вагон находится на возвратном пути («Пост №2» или «Ст. Черкасов Камень»), будет кнопка <strong>«УБРАТЬ В АРХИВ»</strong>.</li>
    </ul>
    <p>Чтобы закрыть окно, нажмите «Закрыть» или кликните вне его.</p>
    
    <h2>7. История и архив</h2>
    <p>Кнопки <strong>«История»</strong> и <strong>«Архив»</strong> вверху страницы.</p>
    <ul>
        <li><strong>История</strong> – все перемещения активных вагонов (сгруппированы по вагонам, раскрывающиеся блоки).</li>
        <li><strong>Архив</strong> – вагоны, которые были убраны с возвратных путей. Также сгруппированы с полной историей.</li>
    </ul>
    <p>Внутри каждого блока есть кнопка <strong>«📊 Excel»</strong> – выгружает историю конкретного вагона в отдельный файл.</p>
    
    <h2>8. Выгрузка в Excel</h2>
    <ul>
        <li>На главной странице – кнопка <strong>«Excel»</strong> (отчёт по всем активным вагонам).</li>
        <li>В разделе «История» – кнопка <strong>«Скачать Excel (все вагоны)»</strong> (полная история перемещений).</li>
        <li>В разделе «Архив» – кнопка <strong>«Скачать Excel (все вагоны)»</strong> (сводка + детализация по архиву).</li>
        <li>Для каждого отдельного вагона (как в истории, так и в архиве) есть своя кнопка Excel.</li>
    </ul>
    
    <h2>9. Редактирование дат в истории (для ролей supervisor и admin)</h2>
    <p>На странице «История» у последнего события каждого вагона появляется кнопка <strong>✏️</strong>.</p>
    <p><strong>Почему только последнее событие?</strong> Изменение даты более раннего события нарушило бы хронологию перемещений и могло бы привести к неверной работе таймеров локального срока. Если вы ошиблись в дате не последнего события, рекомендуется отредактировать время прибытия или сроки вагона (кнопка «Редактировать вагон»), либо удалить и добавить вагон заново.</p>
    <p>При изменении даты последнего события проверяется, что новая дата не нарушает хронологию, и автоматически пересчитывается локальный срок (если был задан). Изменение записывается в журнал действий.</p>
    
    <h2>10. Завершение работы</h2>
    <p>Диспетчеру достаточно закрыть вкладку браузера. Программа на сервере продолжит работать. Если нужно полностью остановить сервер – это делает администратор на серверной машине.</p>
    
    <div class="note">📞 При возникновении проблем обратитесь к системному администратору.</div>
    <p style="text-align: center; margin-top: 30px;">© ЖД Диспетчерская, АО "Знамя"<br>Версия {{ version }} (сетевая, для диспетчера)</p>
</div>
</body>
</html>"""


# ==================== МАРШРУТЫ ====================
@main_bp.route('/')
def index():
    tracks, move_list = get_dashboard_data()
    is_admin = (request.user_role == 'admin')
    return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                  add_form_data=None, move_form_data=None, request=request, is_admin=is_admin,
                                  version=APP_VERSION)


@main_bp.route('/help')
def help_page():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        server_ip = s.getsockname()[0]
        s.close()
    except:
        server_ip = "IP_вашего_сервера"
    return render_template_string(HELP_TEMPLATE, server_ip=server_ip, version=APP_VERSION)


@main_bp.route('/add', methods=['POST'])
def add_wagon():
    number = request.form.get('number', '').strip()
    owner = request.form.get('owner', '').strip()
    org = request.form.get('organization', '').strip()
    note = request.form.get('note', '')
    track_id_str = request.form.get('track_id', '')
    cycle_days = request.form.get('cycle_days', '0')
    cycle_hours = request.form.get('cycle_hours', '0')
    cycle_mins = request.form.get('cycle_mins', '0')
    start_date = request.form.get('start_date', '').strip()
    start_time = request.form.get('start_time', '').strip()

    add_form_data = {
        'number': number,
        'owner': owner,
        'org': org,
        'note': note,
        'cycle_days': cycle_days,
        'cycle_hours': cycle_hours,
        'cycle_mins': cycle_mins,
        'start_date': start_date,
        'start_time': start_time,
        'track_id': track_id_str
    }

    if not number or not owner or not org or not track_id_str:
        flash("Заполните все поля!", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)

    try:
        track_id = int(track_id_str)
    except ValueError:
        flash("Ошибка: Неверный ID пути.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, status, is_archived FROM wagons WHERE wagon_number = ?", (number,))
    existing = c.fetchone()

    try:
        days = int(cycle_days) if cycle_days else 0
        hours = int(cycle_hours) if cycle_hours else 0
        mins = int(cycle_mins) if cycle_mins else 0
    except ValueError:
        days, hours, mins = 0, 0, 0
    total_mins = (days * 24 * 60) + (hours * 60) + mins

    if (start_date and not start_time) or (start_time and not start_date):
        flash("Ошибка: Если вы указываете дату, нужно указать и время, и наоборот.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)

    manual_start = None
    if start_date and start_time:
        manual_start = f"{start_date} {start_time}"
        try:
            start_dt = datetime.strptime(manual_start, '%Y-%m-%d %H:%M')
            arrival_time = f"{start_date} {start_time}:00"
        except:
            arrival_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            flash("Неверный формат даты/времени, использовано текущее время", 'warning')
    else:
        arrival_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    global_dep = None
    if total_mins > 0:
        if manual_start:
            try:
                start_dt = datetime.strptime(manual_start, '%Y-%m-%d %H:%M')
                global_dep = (start_dt + timedelta(minutes=total_mins)).strftime('%Y-%m-%d %H:%M:%S')
            except:
                global_dep = (datetime.now() + timedelta(minutes=total_mins)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            global_dep = (datetime.now() + timedelta(minutes=total_mins)).strftime('%Y-%m-%d %H:%M:%S')

    if existing:
        w_id, w_status, w_archived = existing
        if w_archived == 1:
            compact_track(track_id)
            pos = find_slot_on_track(track_id, 10)[1]
            c.execute("""UPDATE wagons SET status = 'assigned', owner = ?, organization = ?, cargo_type = ?, track_id = ?, start_pos = ?, arrival_time = ?, departure_time = ?, local_departure_time = NULL, visit_count = 0, is_archived = 0 WHERE id = ?""",
                      (owner, org, note, track_id, float(pos), arrival_time, global_dep, w_id))
            conn.commit()
            conn.close()
            log_movement(number, 'added', None, None, f"Восстановлен из архива. ТК: {owner}, Орг: {org}", arrival_time)
            log_action('add', wagon_number=number, details=f"Восстановлен из архива на путь {track_id_str}")
            flash(f"✅ Вагон {number} восстановлен с временем прибытия {arrival_time[:16]}.", 'success')
            return redirect(url_for('main.index'))
        elif w_status != 'departed':
            conn.close()
            flash(f"⚠️ Вагон '{number}' уже на путях!", 'error')
            tracks, move_list = get_dashboard_data()
            is_admin = (request.user_role == 'admin')
            return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                          add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)

    compact_track(track_id)
    pos = find_slot_on_track(track_id, 10)[1]
    try:
        c.execute("""INSERT INTO wagons (wagon_number, length, cargo_type, owner, organization, track_id, start_pos, arrival_time, departure_time, local_departure_time, visit_count, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)""",
                  (number, 10.0, note, owner, org, track_id, float(pos), arrival_time, global_dep, None))
        conn.commit()
        t_name = c.execute("SELECT name FROM tracks WHERE id=?", (track_id,)).fetchone()[0]
        conn.close()
        log_movement(number, 'added', None, t_name, f"ТК: {owner}, Орг: {org}", arrival_time)
        log_action('add', wagon_number=number, details=f"Добавлен на путь {t_name}. ТК: {owner}, Орг: {org}")
        msg = f"✅ Вагон {number} добавлен с временем прибытия {arrival_time[:16]}."
        if total_mins > 0:
            msg += f" Срок: {days}д {hours}ч {mins}мин"
        if global_dep:
            msg += f" (до {global_dep[:16]})"
        flash(msg, 'success')
    except sqlite3.IntegrityError:
        conn.close()
        flash(f"⚠️ Вагон '{number}' уже существует.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=add_form_data, move_form_data=None, request=request, is_admin=is_admin)
    return redirect(url_for('main.index'))


@main_bp.route('/move', methods=['POST'])
def move_action():
    wagon_id = request.form.get('wagon_id', '')
    new_track_id_str = request.form.get('new_track_id', '')
    local_days = request.form.get('local_days', '0')
    local_hours = request.form.get('local_hours', '0')
    local_mins = request.form.get('local_mins', '0')
    start_date = request.form.get('start_date', '').strip()
    start_time = request.form.get('start_time', '').strip()
    note = request.form.get('note', '')

    move_form_data = {
        'wagon_id': wagon_id,
        'new_track_id': new_track_id_str,
        'local_days': local_days,
        'local_hours': local_hours,
        'local_mins': local_mins,
        'start_date': start_date,
        'start_time': start_time,
        'note': note
    }

    if not wagon_id or not new_track_id_str:
        flash("Выберите вагон и путь назначения!", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=None, move_form_data=move_form_data, request=request, is_admin=is_admin)
    try:
        new_track_id = int(new_track_id_str)
    except ValueError:
        flash("Ошибка: Неверный ID пути.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=None, move_form_data=move_form_data, request=request, is_admin=is_admin)
    try:
        l_days = int(local_days) if local_days else 0
        l_hours = int(local_hours) if local_hours else 0
        l_mins = int(local_mins) if local_mins else 0
    except ValueError:
        l_days, l_hours, l_mins = 0, 0, 0

    if (start_date and not start_time) or (start_time and not start_date):
        flash("Ошибка: Если вы указываете дату, нужно указать и время, и наоборот.", 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=None, move_form_data=move_form_data, request=request, is_admin=is_admin)

    manual_start = None
    if start_date and start_time:
        manual_start = f"{start_date} {start_time}"

    success, msg = move_wagon(wagon_id, new_track_id, l_days, l_hours, l_mins, manual_start, note)
    if success:
        flash(msg, 'success')
        return redirect(url_for('main.index'))
    else:
        flash(msg, 'error')
        tracks, move_list = get_dashboard_data()
        is_admin = (request.user_role == 'admin')
        return render_template_string(HTML_TEMPLATE, tracks=tracks, move_list=move_list, total_wagons=len(move_list),
                                      add_form_data=None, move_form_data=move_form_data, request=request, is_admin=is_admin)


@main_bp.route('/depart/<int:wagon_id>', methods=['POST'])
def depart_action(wagon_id):
    if depart_wagon(wagon_id):
        flash("✅ Вагон убран в архив.", 'success')
    else:
        flash("⚠️ Ошибка при удалении.", 'error')
    return redirect(url_for('main.index'))