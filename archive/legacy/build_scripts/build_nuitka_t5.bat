@echo off
REM ================================================================
REM Compilazione con Nuitka (Onefile) - Versione Ottimizzata
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
SET "BUILD_DIR=build_nuitka_%PROJECT_NAME%"
SET "DIST_DIR=dist_nuitka_%PROJECT_NAME%"
SET "RELEASE_DIR=release_nuitka_%PROJECT_NAME%"
SET "DESIRED_EXE_NAME=BetterfoxUpdater.exe"
SET "ONEFILE_TEMPDIR=.\onefile_temp"  REM cartella d'estrazione a runtime
SET "UPX_PATH=C:\Scripts\Tools\upx_tool\upx.exe"

SET "NUITKA_ERROR=0"
SET "UPX_ERROR=0"

title %PROJECT_NAME% - Compilazione con Nuitka (Onefile)

echo ============================================================
echo  %PROJECT_NAME% - Compilazione con Nuitka (Onefile, Ottimizzata)
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
    GOTO :found_ico
)
:found_ico
IF DEFINED ICON_NAME (
    echo [5] Icona rilevata: !ICON_NAME!
) ELSE (
    echo [5] Nessuna icona .ico trovata in %RESOURCES_DIR%.
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
    :select_loop
    SET /P "CHOICE=Inserisci il numero del file principale (1-%PY_COUNT%): "
    IF "!CHOICE!"=="" goto select_loop
    SET /A test=!CHOICE! >nul 2>&1
    IF !ERRORLEVEL! NEQ 0 goto select_loop
    IF !CHOICE! GEQ 1 IF !CHOICE! LEQ !PY_COUNT! (
        CALL SET "SCRIPT_NAME=%%FILE_!CHOICE!%%"
        echo - File principale selezionato: !SCRIPT_NAME!
    ) ELSE (
        goto select_loop
    )
)
IF NOT EXIST "%SRC_DIR%\!SCRIPT_NAME!" (
    echo ERRORE: Il file !SCRIPT_NAME! non esiste in %SRC_DIR%.
    goto end
)
echo.

REM [7] Compilazione Nuitka (Onefile) - silenziosa con log temporaneo
echo [7] Compilazione con Nuitka in corso...
IF NOT EXIST "%ONEFILE_TEMPDIR%" (
    MD "%ONEFILE_TEMPDIR%" >nul 2>&1
    echo - Cartella temporanea creata: %ONEFILE_TEMPDIR%
)
IF NOT EXIST "%DIST_DIR%" (
    MD "%DIST_DIR%" >nul 2>&1
    echo - Cartella dist creata: %DIST_DIR%
)

REM Costruzione del comando Nuitka
SET "NUITKA_CMD=python -m nuitka --onefile --onefile-tempdir=""%ONEFILE_TEMPDIR%"" --windows-disable-console --enable-plugin=tk-inter --include-data-dir=""%RESOURCES_DIR%=resources"" --output-dir=""%DIST_DIR%"" "

IF DEFINED ICON_NAME (
    SET "NUITKA_CMD=!NUITKA_CMD! --windows-icon-from-ico=""%RESOURCES_DIR%\!ICON_NAME!"" "
)

SET "NUITKA_CMD=!NUITKA_CMD! ""%SRC_DIR%\!SCRIPT_NAME!"" "

echo - Esecuzione di Nuitka...
echo !NUITKA_CMD! > temp_nuitka_log.txt
%NUITKA_CMD% >> temp_nuitka_log.txt 2>&1

IF %ERRORLEVEL% NEQ 0 (
    echo Errore: Nuitka ha fallito.
    move /Y temp_nuitka_log.txt error_log.txt >nul 2>&1
    echo Controlla error_log.txt per maggiori dettagli.
    SET "NUITKA_ERROR=1"
    GOTO cleanup
) ELSE (
    echo Compilazione completata.
    del temp_nuitka_log.txt >nul 2>&1
)
echo.

REM [8] Creazione cartella di release, rinomina .exe e copia delle risorse
IF NOT EXIST "%RELEASE_DIR%" (
    MD "%RELEASE_DIR%" >nul 2>&1
    echo - Cartella release creata: %RELEASE_DIR%
)

SET "GENERATED_EXE=%DIST_DIR%\!SCRIPT_NAME:.py=.exe!"
IF EXIST "!GENERATED_EXE!" (
    REN "!GENERATED_EXE!" "%DESIRED_EXE_NAME%"
    MOVE /Y "%DIST_DIR%\%DESIRED_EXE_NAME%" "%RELEASE_DIR%\" >nul 2>&1
    echo - Eseguibile rinominato e spostato in release: %RELEASE_DIR%\%DESIRED_EXE_NAME%

    REM Copia la cartella resources nella cartella di release
    IF EXIST "%RESOURCES_DIR%" (
        echo - Copia della cartella resources in release...
        xcopy /E /I /Y "%RESOURCES_DIR%" "%RELEASE_DIR%\%RESOURCES_DIR%" >nul
        IF %ERRORLEVEL% NEQ 0 (
            echo ERRORE: Copia della cartella resources fallita.
            SET "NUITKA_ERROR=1"
        ) ELSE (
            echo - Cartella resources copiata in release.
        )
    ) ELSE (
        echo - Nessuna cartella resources da copiare.
    )
) ELSE (
    echo - ERRORE: Eseguibile non trovato dopo la compilazione.
    SET "NUITKA_ERROR=1"
)
echo.

REM [9] (Opzionale) Compressione con UPX
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

REM [10] Pulizia delle cartelle temporanee e dei file generati
echo [10] Pulizia delle cartelle temporanee...
IF EXIST "%BUILD_DIR%" (
    RMDIR /S /Q "%BUILD_DIR%"
    echo - Cartella build rimossa.
)
IF EXIST "%DIST_DIR%" (
    RMDIR /S /Q "%DIST_DIR%"
    echo - Cartella dist rimossa.
)
IF EXIST "%ONEFILE_TEMPDIR%" (
    RMDIR /S /Q "%ONEFILE_TEMPDIR%"
    echo - Cartella temporanea rimossa.
)
IF EXIST "%SRC_DIR%\__pycache__" (
    RMDIR /S /Q "%SRC_DIR%\__pycache__"
    echo - Cartella __pycache__ rimossa.
)
IF EXIST "temp_nuitka_log.txt" (
    DEL /F /Q "temp_nuitka_log.txt" >nul 2>&1
    echo - File temp_nuitka_log.txt rimosso.
)
echo - Pulizia completata.
echo.

:cleanup
IF "%NUITKA_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compilazione con Nuitka.
)
IF "%UPX_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compressione con UPX.
)
IF "%NUITKA_ERROR%"=="0" IF "%UPX_ERROR%"=="0" (
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
