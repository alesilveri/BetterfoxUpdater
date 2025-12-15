@echo off
SETLOCAL
cd /d "%~dp0"
chcp 65001 >nul

SET "VENV=venv"
echo [1] Rigenero venv...
IF EXIST "%VENV%" RMDIR /S /Q "%VENV%"
python -m venv "%VENV%" || exit /b 1
CALL "%VENV%\Scripts\activate.bat" || exit /b 1

echo [2] Aggiorno pip/setuptools/wheel...
pip install --upgrade pip setuptools wheel

echo [3] Installo dipendenze app...
pip install -r requirements.txt || exit /b 1

echo [4] Installo PyInstaller...
pip install pyinstaller || exit /b 1

SET "BUILD=build_app"
SET "DIST=dist_app"
SET "RELEASE=release_app"
IF EXIST "%BUILD%" RMDIR /S /Q "%BUILD%"
IF EXIST "%DIST%" RMDIR /S /Q "%DIST%"
IF EXIST "%RELEASE%" RMDIR /S /Q "%RELEASE%"

echo [5] Lancio PyInstaller (onefile, windowed)...
IF EXIST "app\resources\betterfox.ico" (
    pyinstaller --onefile --windowed --name "BetterfoxUpdater" --workpath "%BUILD%" --distpath "%DIST%" --icon "app\resources\betterfox.ico" --add-data "app\resources;app/resources" app\main.py > build_log.txt 2>&1
) ELSE (
    echo - Icona non trovata, procedo senza.
    pyinstaller --onefile --windowed --name "BetterfoxUpdater" --workpath "%BUILD%" --distpath "%DIST%" --add-data "app\resources;app/resources" app\main.py > build_log.txt 2>&1
)
IF %ERRORLEVEL% NEQ 0 (
    echo Build fallita, vedi build_log.txt
    exit /b 1
)

echo [6] Preparo release...
mkdir "%RELEASE%" >nul 2>&1
move /Y "%DIST%\BetterfoxUpdater.exe" "%RELEASE%" >nul
xcopy /E /I /Y "app\resources" "%RELEASE%\resources" >nul
RMDIR /S /Q "%BUILD%"
RMDIR /S /Q "%DIST%"
IF EXIST "build_log.txt" DEL /F /Q "build_log.txt"

echo [OK] Build completata: %RELEASE%\BetterfoxUpdater.exe
ENDLOCAL
