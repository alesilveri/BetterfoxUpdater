@echo off
REM ================================================================
REM Compilazione con PyInstaller (Onefile) - Applicazione Autonoma
REM ================================================================
SETLOCAL ENABLEDELAYEDEXPANSION

:: Spostati nella cartella dello script
cd /d "%~dp0"
chcp 65001 >nul

:: -------------------------------------------------
:: Configurazione
:: -------------------------------------------------
FOR %%a IN ("%CD%") DO SET "PROJECT_NAME=%%~na"
SET "SRC_DIR=src"
SET "RESOURCES_DIR=resources"
SET "VENV_DIR=venv"
SET "BUILD_DIR=build_pyinstaller_%PROJECT_NAME%"
SET "DIST_DIR=dist_pyinstaller_%PROJECT_NAME%"
SET "RELEASE_DIR=release_pyinstaller_%PROJECT_NAME%"
SET "DESIRED_EXE_NAME=BetterfoxUpdater.exe"

:: Percorso UPX (opzionale, PyInstaller lo utilizza se presente)
SET "UPX_PATH=C:\Scripts\Tools\upx_tool\upx.exe"

SET "PYINSTALLER_ERROR=0"
SET "UPX_ERROR=0"

title %PROJECT_NAME% - Compilazione con PyInstaller (Onefile)

echo ============================================================
echo  %PROJECT_NAME% - Compilazione con PyInstaller (Onefile, Autonoma)
echo ============================================================
echo.

REM [1] Verifica Python
echo [1] Versione di Python:
python --version | findstr /R "Python [0-9]*\.[0-9]*\.[0-9]*"
IF %ERRORLEVEL% NEQ 0 (
    echo ERRORE: Python non trovato nel PATH.
    goto end
)
FOR /F "tokens=2 delims= " %%v IN ('python --version') DO SET "PYTHON_VERSION=%%v"
echo.

REM [2] Creazione/Attivazione venv e installazione dipendenze (silenziosa)
echo [2] Ambiente virtuale...
IF NOT EXIST "%VENV_DIR%\Scripts\activate.bat" (
    python -m venv "%VENV_DIR%" >nul 2>&1
    IF %ERRORLEVEL% NEQ 0 (
        echo ERRORE: Creazione venv fallita.
        goto end
    )
    echo - Ambiente virtuale creato.
) ELSE (
    echo - Ambiente virtuale già esistente.
)
CALL "%VENV_DIR%\Scripts\activate.bat" >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERRORE: Attivazione venv fallita.
    goto end
)
echo - Ambiente virtuale attivato.
echo.

echo [3] Installazione dipendenze...
pip install --upgrade pip setuptools wheel >nul 2>&1
pip install -r requirements.txt >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERRORE: Installazione dipendenze fallita.
    goto end
)
pip install pyinstaller >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERRORE: Installazione di PyInstaller fallita.
    goto end
)
echo - Dipendenze installate.
echo.

REM [4] Pulizia build/dist/release
echo [4] Pulizia delle cartelle di build...
IF EXIST "%BUILD_DIR%" (
    RMDIR /S /Q "%BUILD_DIR%"
    echo - Cartella build rimossa.
)
IF EXIST "%DIST_DIR%" (
    RMDIR /S /Q "%DIST_DIR%"
    echo - Cartella dist rimossa.
)
IF EXIST "%RELEASE_DIR%" (
    RMDIR /S /Q "%RELEASE_DIR%"
    echo - Cartella release rimossa.
)
echo.

REM [5] Rilevazione .ico in resources
SET "ICON_NAME="
FOR %%I IN ("%~dp0%RESOURCES_DIR%\*.ico") DO (
    SET "ICON_NAME=%%~nI%%~xI"
    GOTO :found_ico_py
)
:found_ico_py
IF DEFINED ICON_NAME (
    echo [5] Icona rilevata: !ICON_NAME!
    SET "USE_ICON=1"
) ELSE (
    echo [5] Nessuna icona .ico trovata in %RESOURCES_DIR%.
    SET "USE_ICON=0"
)
echo.

REM [6] Selezione file .py principale (default fisso)
SET "SCRIPT_NAME=betterfox_updater_app.py"
IF NOT EXIST "app\\main.py" (
    echo ERRORE: %SCRIPT_NAME% non trovato in %SRC_DIR%.
    goto end
)
echo - File principale: %SCRIPT_NAME%
echo.

REM [7/9] Compilazione con PyInstaller (onefile, windowed, clean, noupx)...
echo [7] Compilazione con PyInstaller in corso...
IF NOT EXIST "%BUILD_DIR%" (
    MD "%BUILD_DIR%" >nul 2>&1
    echo - Cartella build creata: %BUILD_DIR%
)
IF NOT EXIST "%DIST_DIR%" (
    MD "%DIST_DIR%" >nul 2>&1
    echo - Cartella dist creata: %DIST_DIR%
)

IF "%USE_ICON%"=="1" (
    pyinstaller --onefile --windowed --name "%DESIRED_EXE_NAME%" --icon "%RESOURCES_DIR%\%ICON_NAME%" --workpath "%BUILD_DIR%" --distpath "%DIST_DIR%" "app\\main.py" --add-data "%RESOURCES_DIR%;resources" > temp_pyinstaller_log.txt 2>&1
) ELSE (
    pyinstaller --onefile --windowed --name "%DESIRED_EXE_NAME%" --workpath "%BUILD_DIR%" --distpath "%DIST_DIR%" "app\\main.py" --add-data "%RESOURCES_DIR%;resources" > temp_pyinstaller_log.txt 2>&1
)

IF %ERRORLEVEL% NEQ 0 (
    echo Errore: PyInstaller ha fallito.
    REM Sposta il log in un file di errore
    move /Y temp_pyinstaller_log.txt error_log.txt >nul 2>&1
    echo Controlla error_log.txt per maggiori dettagli.
    SET "PYINSTALLER_ERROR=1"
    GOTO cleanup
) ELSE (
    echo Compilazione completata.
    del temp_pyinstaller_log.txt
)
echo.
TIMEOUT /T 1 >nul

REM [8] Creazione cartella di release, spostamento dell'eseguibile e copia delle risorse
echo [8] Creazione cartella di release, spostamento dell'eseguibile e copia delle risorse...
IF NOT EXIST "%RELEASE_DIR%" (
    MD "%RELEASE_DIR%" >nul 2>&1
    echo - Cartella release creata: %RELEASE_DIR%
)
IF EXIST "%DIST_DIR%\%DESIRED_EXE_NAME%" (
    MOVE /Y "%DIST_DIR%\%DESIRED_EXE_NAME%" "%RELEASE_DIR%\" >nul 2>&1
    echo - Eseguibile spostato in release: %RELEASE_DIR%\%DESIRED_EXE_NAME%
    
    REM Copia la cartella resources nella cartella di release
    IF EXIST "%RESOURCES_DIR%" (
        echo - Copia della cartella resources in release...
        xcopy /E /I /Y "%RESOURCES_DIR%" "%RELEASE_DIR%\%RESOURCES_DIR%" >nul
        IF %ERRORLEVEL% NEQ 0 (
            echo ERRORE: Copia della cartella resources fallita.
            SET "PYINSTALLER_ERROR=1"
        ) ELSE (
            echo - Cartella resources copiata in release.
        )
    ) ELSE (
        echo - Nessuna cartella resources da copiare.
    )
) ELSE (
    echo - ERRORE: Eseguibile non trovato dopo la compilazione.
    SET "PYINSTALLER_ERROR=1"
)
echo.

REM [9] Compressione con UPX (Opzionale)
IF EXIST "%UPX_PATH%" (
    IF EXIST "%RELEASE_DIR%\%DESIRED_EXE_NAME%" (
        echo [9] Compressione con UPX in corso...
        "%UPX_PATH%" --best --lzma --force "%RELEASE_DIR%\%DESIRED_EXE_NAME%" >nul 2>&1
        IF %ERRORLEVEL% NEQ 0 (
            SET "UPX_ERROR=1"
            echo - ERRORE durante la compressione con UPX.
        ) ELSE (
            echo - Compressione con UPX completata.
        )
    )
)
echo.

REM [10] Pulizia temporanea di PyInstaller e altri file temporanei
echo [10] Pulizia delle cartelle temporanee e dei file generati...
IF EXIST "%BUILD_DIR%" (
    RMDIR /S /Q "%BUILD_DIR%"
    echo - Cartella build rimossa.
)
IF EXIST "%DIST_DIR%" (
    RMDIR /S /Q "%DIST_DIR%"
    echo - Cartella dist rimossa.
)
IF EXIST "%SRC_DIR%\__pycache__" (
    RMDIR /S /Q "%SRC_DIR%\__pycache__"
    echo - Cartella __pycache__ rimossa.
)
IF EXIST "%SRC_DIR%\*.spec" (
    DEL /F /Q "%SRC_DIR%\*.spec"
    echo - File .spec rimossi.
)
REM Rimuove eventuali file temporanei residui
IF EXIST "temp_pyinstaller_log.txt" (
    DEL /F /Q "temp_pyinstaller_log.txt" >nul 2>&1
    echo - File temp_pyinstaller_log.txt rimosso.
)
echo - Pulizia completata.
echo.

REM [11] Se ci sono errori, lasciare i log
:cleanup
IF "%PYINSTALLER_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compilazione con PyInstaller.
)
IF "%UPX_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compressione con UPX.
)
IF "%PYINSTALLER_ERROR%"=="0" IF "%UPX_ERROR%"=="0" (
    echo - Operazione completata con successo!
) ELSE (
    echo - Operazione completata con errori. Controlla i messaggi sopra per dettagli.
)
echo.

:: Se l'operazione è completata, aggiungi una sezione finale con nome del progetto e anno
echo ============================================================
echo  %PROJECT_NAME% - %DATE:~6,4%
echo ============================================================
echo.

echo Fine. Premi un tasto per chiudere...
pause >nul
ENDLOCAL
exit /b 0

:end
echo.
echo ============================================================
echo  %PROJECT_NAME% - %DATE:~6,4%
echo ============================================================
echo.
echo Fine. Premi un tasto per chiudere...
pause >nul
ENDLOCAL
exit /b 1
