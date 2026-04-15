// ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ И ФУНКЦИИ ====================
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
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(str)) return str;
    if (/^\d{4}-\d{2}-\d{2}$/.test(str)) return str + ' 00:00:00';
    let match = str.match(/^(\d{2})[.\-](\d{2})[.\-](\d{4})(?: (\d{2}):(\d{2})(?::(\d{2}))?)?$/);
    if (match) {
        let day = match[1], month = match[2], year = match[3];
        let hour = match[4] || '00', minute = match[5] || '00', second = match[6] || '00';
        return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
    }
    let digits = str.replace(/[^\d]/g, '');
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
    let digits = value.replace(/[^\d]/g, '');
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
    let digits = value.replace(/[^\d]/g, '');
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
        const datePattern = /^\d{4}-\d{2}-\d{2}$/;
        const timePattern = /^\d{2}:\d{2}$/;
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
    document.getElementById('edit_arrival').value = activeWagonArrival && activeWagonArrival !== '-' ? activeWagonArrival.replace(/\./g, '-') : '';
    document.getElementById('edit_global').value = activeWagonGlobal || '';
    document.getElementById('edit_local').value = activeWagonLocal || '';
    document.getElementById('editModal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
    const editForm = document.getElementById('editForm');
    if (editForm) {
        editForm.addEventListener('submit', async function(e) {
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

// Делегирование кликов для тултипа
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

// Запуск таймеров и обновления дашборда (только на главной странице)
if (document.querySelector('.track-wrapper')) {
    setInterval(updateAllTimers, 1000);
    setInterval(updateDashboard, 5000);
}

// ==================== ФУНКЦИИ ДЛЯ СТРАНИЦ ИСТОРИИ И АРХИВА ====================
function filterHistoryWagons() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    const searchTerm = searchInput.value.trim().toLowerCase();
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
    if (noResultsDiv) {
        noResultsDiv.style.display = (visibleCount === 0 && searchTerm !== '') ? 'block' : 'none';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Поиск для истории/архива
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', filterHistoryWagons);
        const clearBtn = document.getElementById('clearSearch');
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                searchInput.value = '';
                filterHistoryWagons();
            });
        }
    }

    // Кнопки редактирования даты в истории
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
});