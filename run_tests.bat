@echo off
cd /d "%~dp0"
echo ========================================
echo   Запуск проверок ЖД Диспетчерской...
echo ========================================
echo.
REM Запускаем тесты с подробным выводом и генерацией HTML-отчёта
pytest tests/test_scenarios.py -v -s --html=report.html --self-contained-html
echo.
echo ========================================
echo   Проверки завершены.
echo   Отчёт сохранён в report.html
echo ========================================
REM Открываем отчёт в браузере
start report.html
pause