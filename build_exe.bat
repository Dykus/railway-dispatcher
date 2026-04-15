@echo off
echo ========================================
echo    Building RailwayDispatcher EXE
echo ========================================

:: Check if virtual environment is activated
if not defined VIRTUAL_ENV (
    echo [ERROR] Virtual environment is not activated!
    echo Please activate venv first:
    echo   .\venv\Scripts\activate
    exit /b 1
)

:: Ensure PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Clean previous builds
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
echo    EXE is located in "dist\RailwayDispatcher\"
echo ========================================
echo.
echo To test, run:
echo   .\dist\RailwayDispatcher\RailwayDispatcher.exe
echo.
pause