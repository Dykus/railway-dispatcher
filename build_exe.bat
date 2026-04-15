@echo off
chcp 65001 >nul
echo ========================================
echo    Building RailwayDispatcher EXE
echo ========================================

:: Проверяем наличие папки venv
if not exist "venv\" (
    echo [ERROR] Virtual environment not found. Creating one...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Активируем venv
echo Activating virtual environment...
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: Проверяем наличие PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Убедимся, что все зависимости установлены
if exist "requirements.txt" (
    echo Installing dependencies from requirements.txt...
    pip install -r requirements.txt
) else (
    echo Warning: requirements.txt not found, installing minimal set...
    pip install flask pandas openpyxl pystray pillow pyinstaller
)

:: Очистка предыдущей сборки
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo Running PyInstaller...
pyinstaller railway_dispatcher.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Build successful!
echo    EXE is located in "dist\"
echo ========================================
echo.
echo To test, run:
echo   .\dist\RailwayDispatcher.exe
echo.
pause