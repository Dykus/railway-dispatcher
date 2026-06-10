@echo off
cd /d "%~dp0"
echo ========================================
echo   Запуск проверок ЖД Диспетчерской...
echo ========================================
echo.
REM Запускаем все тесты в папке tests (рекурсивно)
pytest tests/ -v -s --html=report.html --self-contained-html
echo.
echo ========================================
echo   Проверки завершены.
echo   Отчёт сохранён в report.html
echo ========================================
REM Открываем отчёт в браузере
start report.html
pause