@echo off
REM ================================================================
REM Compilazione con cx_Freeze - Applicazione (folder)
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
SET "BUILD_DIR=build_cxfreeze_%PROJECT_NAME%"
SET "DIST_DIR=dist_cxfreeze_%PROJECT_NAME%"
SET "RELEASE_DIR=release_cxfreeze_%PROJECT_NAME%"
SET "DESIRED_EXE_NAME=BetterfoxUpdater.exe"

:: Percorso UPX (opzionale, se vuoi comprimere l'eseguibile dopo il freeze)
SET "UPX_PATH=C:\Scripts\Tools\upx_tool\upx.exe"

SET "CXFREEZE_ERROR=0"
SET "UPX_ERROR=0"

title %PROJECT_NAME% - Compilazione con cx_Freeze

echo ============================================================
echo  %PROJECT_NAME% - Compilazione con cx_Freeze
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
pip install cx_Freeze >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERRORE: Installazione di cx_Freeze fallita.
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
    GOTO :found_ico_cx
)
:found_ico_cx
IF DEFINED ICON_NAME (
    echo [5] Icona rilevata: !ICON_NAME!
    SET "USE_ICON=1"
) ELSE (
    echo [5] Nessuna icona .ico trovata in %RESOURCES_DIR%.
    SET "USE_ICON=0"
)
echo.

REM [6] Selezione file .py principale
SET "SCRIPT_NAME="
SET "PY_COUNT=0"

FOR %%f IN ("%~dp0%SRC_DIR%\*.py") DO (
    SET /A PY_COUNT+=1
    SET "FILE_!PY_COUNT!=%%~nxf"
)

IF !PY_COUNT! EQU 0 (
    echo ERRORE: Nessun file .py in %SRC_DIR%.
    goto end
) ELSE IF !PY_COUNT! EQU 1 (
    SET "SCRIPT_NAME=!FILE_1!"
    echo - File principale selezionato automaticamente: !SCRIPT_NAME!
) ELSE (
    echo Trovati !PY_COUNT! file .py in %SRC_DIR%:
    SET /A COUNT=1
    FOR %%f IN ("%~dp0%SRC_DIR%\*.py") DO (
        echo   !COUNT!: %%~nxf
        SET "FILE_!COUNT!=%%~nxf"
        SET /A COUNT+=1
    )
    :select_loop_cx
    SET /P "CHOICE=Inserisci il numero del file principale (1-%PY_COUNT%): "
    IF "!CHOICE!"=="" goto select_loop_cx
    SET /A test=!CHOICE! >nul 2>&1
    IF !ERRORLEVEL! NEQ 0 goto select_loop_cx
    IF !CHOICE! GEQ 1 IF !CHOICE! LEQ !PY_COUNT! (
        CALL SET "SCRIPT_NAME=%%FILE_!CHOICE!%%"
        echo - File principale selezionato: !SCRIPT_NAME!
    ) ELSE (
        goto select_loop_cx
    )
)
IF NOT EXIST "%SRC_DIR%\!SCRIPT_NAME!" (
    echo ERRORE: Il file !SCRIPT_NAME! non esiste in %SRC_DIR%.
    goto end
)
echo.

REM [7] Freeze con cx_Freeze
echo [7] Freeze con cx_Freeze in corso...
IF NOT EXIST "%BUILD_DIR%" (
    MD "%BUILD_DIR%" >nul 2>&1
    echo - Cartella build creata: %BUILD_DIR%
)
IF NOT EXIST "%DIST_DIR%" (
    MD "%DIST_DIR%" >nul 2>&1
    echo - Cartella dist creata: %DIST_DIR%
)

REM Costruiamo il comando base per cxfreeze
SET "CXFREEZE_CMD=cxfreeze --target-dir ""%DIST_DIR%"" --target-name ""%DESIRED_EXE_NAME%"" --include-files ""%RESOURCES_DIR%;resources"""

IF "%USE_ICON%"=="1" (
    REM Solo su Windows, cxfreeze supporta --icon
    SET "CXFREEZE_CMD=%CXFREEZE_CMD% --icon ""%RESOURCES_DIR%\%ICON_NAME%"""
)

REM Aggiungiamo lo script principale
SET "CXFREEZE_CMD=%CXFREEZE_CMD% ""%SRC_DIR%\%SCRIPT_NAME%"""

REM Eseguiamo il comando, reindirizzando l'output
%CXFREEZE_CMD% > temp_cxfreeze_log.txt 2>&1

IF %ERRORLEVEL% NEQ 0 (
    echo Errore: cx_Freeze ha fallito.
    move /Y temp_cxfreeze_log.txt error_log.txt >nul 2>&1
    echo Controlla error_log.txt per maggiori dettagli.
    SET "CXFREEZE_ERROR=1"
    GOTO cleanup
) ELSE (
    echo Freeze completato con successo.
    del temp_cxfreeze_log.txt
)
echo.
TIMEOUT /T 1 >nul

REM [8] Creazione cartella di release, spostamento dell’eseguibile e copia risorse aggiuntive
echo [8] Creazione cartella di release, spostamento dell’eseguibile e copia delle risorse...
IF NOT EXIST "%RELEASE_DIR%" (
    MD "%RELEASE_DIR%" >nul 2>&1
    echo - Cartella release creata: %RELEASE_DIR%
)

REM In cx_Freeze, l'eseguibile si troverà in DIST_DIR, ma con diverse DLL e file associati
IF EXIST "%DIST_DIR%\%DESIRED_EXE_NAME%" (
    xcopy /E /I /Y "%DIST_DIR%" "%RELEASE_DIR%" >nul
    echo - Tutti i file generati copiati in %RELEASE_DIR%.
) ELSE (
    echo - ERRORE: Eseguibile non trovato dopo il freeze (controlla la cartella dist).
    SET "CXFREEZE_ERROR=1"
)
echo.

REM [9] Compressione con UPX (Opzionale - comprime solo l'eseguibile, non unifica in un file unico)
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

REM [10] Pulizia delle cartelle temporanee e dei file generati...
echo [10] Pulizia temporanea...
IF EXIST "%BUILD_DIR%" (
    RMDIR /S /Q "%BUILD_DIR%"
    echo - Cartella build rimossa.
)
IF EXIST "%SRC_DIR%\__pycache__" (
    RMDIR /S /Q "%SRC_DIR%\__pycache__"
    echo - Cartella __pycache__ rimossa.
)
IF EXIST "%SRC_DIR%\*.spec" (
    DEL /F /Q "%SRC_DIR%\*.spec"
    echo - File .spec (PyInstaller) rimossi (se presenti).
)
IF EXIST "temp_cxfreeze_log.txt" (
    DEL /F /Q "temp_cxfreeze_log.txt" >nul 2>&1
    echo - File temp_cxfreeze_log.txt rimosso.
)
echo - Pulizia completata.
echo.

:cleanup
IF "%CXFREEZE_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compilazione (freeze) con cx_Freeze.
)
IF "%UPX_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compressione con UPX.
)

IF "%CXFREEZE_ERROR%"=="0" IF "%UPX_ERROR%"=="0" (
    echo - Operazione completata con successo!
) ELSE (
    echo - Operazione completata con errori. Controlla i messaggi sopra per maggiori dettagli.
)
echo.

:: Sezione finale con nome del progetto e anno
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
