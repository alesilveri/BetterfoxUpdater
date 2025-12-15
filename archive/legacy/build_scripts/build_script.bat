@echo off
REM ================================================================
REM Compilazione Multi-Tool Universale (Nuitka, PyInstaller, cx-Freeze)
REM ================================================================
SETLOCAL ENABLEDELAYEDEXPANSION

:: Spostati nella cartella dello script
cd /d "%~dp0"
chcp 65001 >nul

:: -------------------------------------------------
:: Configurazione Generale
:: -------------------------------------------------
SET "PROJECTS_DIR=projects"

:: Contatori di errore
SET "NUITKA_ERROR=0"
SET "PYINSTALLER_ERROR=0"
SET "CXFREEZE_ERROR=0"
SET "UPX_ERROR=0"

title Compilazione Multi-Tool Universale

echo ============================================================
echo  Compilazione Multi-Tool Universale (Nuitka, PyInstaller, cx-Freeze)
echo ============================================================
echo.

:: -------------------------------------------------
:: Passo [1] Verifica Python
:: -------------------------------------------------
echo [1] Verifica della versione di Python...
python --version | findstr /R "Python [0-9]*\.[0-9]*\.[0-9]*"
IF %ERRORLEVEL% NEQ 0 (
    echo ERRORE: Python non trovato nel PATH.
    goto terminate
)
FOR /F "tokens=2 delims= " %%v IN ('python --version') DO SET "PYTHON_VERSION=%%v"
echo - Versione di Python: !PYTHON_VERSION!
echo.

:: -------------------------------------------------
:: Passo [2] Scansione dei Progetti Disponibili
:: -------------------------------------------------
echo [2] Scansione dei progetti disponibili in "%PROJECTS_DIR%"...
SET "PROJECT_LIST="
SET "COUNT=0"

FOR /D %%P IN ("%PROJECTS_DIR%\*") DO (
    IF EXIST "%%P\src\*.py" (
        SET /A COUNT+=1
        SET "PROJECT_!COUNT!=%%~nP"
        SET "PROJECT_LIST=!PROJECT_LIST! !COUNT!"
    )
)

IF !COUNT! EQU 0 (
    echo ERRORE: Nessun progetto trovato in "%PROJECTS_DIR%".
    goto terminate
)

echo Trovati !COUNT! progetti:
FOR /L %%i IN (1,1,!COUNT!) DO (
    echo   %%i. !PROJECT_%%i!
)
echo.
echo Seleziona i progetti da compilare (es. 1 2 3) o 0 per tutti:
SET /P "SELECTION=Inserisci i numeri separati da spazio: "

:: Verifica selezione
IF "!SELECTION!"=="" (
    echo ERRORE: Nessuna selezione effettuata.
    goto terminate
)

:: Imposta una variabile per progetti da compilare
SET "SELECTED_PROJECTS="

FOR %%i IN (!SELECTION!) DO (
    IF %%i EQU 0 (
        SET "SELECTED_PROJECTS=ALL"
        GOTO :selected_all
    )
    IF %%i GEQ 1 IF %%i LEQ !COUNT! (
        SET "SELECTED_PROJECTS=!SELECTED_PROJECTS! %%i"
    ) ELSE (
        echo ATTENZIONE: Numero %%i fuori range. Ignorato.
    )
)

:selected_all
IF "!SELECTED_PROJECTS!"=="ALL" (
    SET "SELECTED_PROJECTS="
    FOR /L %%i IN (1,1,!COUNT!) DO (
        SET "SELECTED_PROJECTS=!SELECTED_PROJECTS! %%i"
    )
)
echo Selezionati i progetti: !SELECTED_PROJECTS!
echo.

:: -------------------------------------------------
:: Passo [3] Loop sui Progetti Selezionati
:: -------------------------------------------------
FOR %%i IN (!SELECTED_PROJECTS!) DO (
    SET "CURRENT_PROJECT=PROJECT_%%i"
    CALL SET "CURRENT_PROJECT=!%%CURRENT_PROJECT%%!"
    echo ===========================================================
    echo Compilazione del progetto: !CURRENT_PROJECT!
    echo ===========================================================
    echo.

    SET "PROJECT_PATH=%PROJECTS_DIR%\!CURRENT_PROJECT!"
    SET "SRC_DIR=!PROJECT_PATH!\src"
    SET "RESOURCES_DIR=!PROJECT_PATH!\resources"
    SET "VENV_DIR=!PROJECT_PATH!\venv"
    SET "BUILD_DIR=!PROJECT_PATH!\build_!CURRENT_PROJECT!"
    SET "DIST_DIR=!PROJECT_PATH!\dist_!CURRENT_PROJECT!"
    SET "RELEASE_DIR=!PROJECT_PATH!\release_!CURRENT_PROJECT!"
    SET "DESIRED_EXE_NAME=!CURRENT_PROJECT!.exe"
    SET "ONEFILE_TEMPDIR=!PROJECT_PATH!\onefile_temp"
    SET "UPX_PATH=C:\Scripts\Tools\upx_tool\upx.exe"  REM Modifica con il percorso corretto di UPX

    :: -------------------------------------------------
    :: Passo [4] Creazione/Attivazione venv e Installazione Dipendenze
    :: -------------------------------------------------
    echo [4] Creazione e attivazione dell'ambiente virtuale...
    IF NOT EXIST "!VENV_DIR!\Scripts\activate.bat" (
        python -m venv "!VENV_DIR!" >nul 2>&1
        IF !ERRORLEVEL! NEQ 0 (
            echo ERRORE: Creazione dell'ambiente virtuale fallita per !CURRENT_PROJECT!.
            SET "NUITKA_ERROR=1"
            SET "PYINSTALLER_ERROR=1"
            SET "CXFREEZE_ERROR=1"
            GOTO :next_project
        )
        echo - Ambiente virtuale creato per !CURRENT_PROJECT!.
    ) ELSE (
        echo - Ambiente virtuale già esistente per !CURRENT_PROJECT!.
    )
    CALL "!VENV_DIR!\Scripts\activate.bat" >nul 2>&1
    IF !ERRORLEVEL! NEQ 0 (
        echo ERRORE: Attivazione dell'ambiente virtuale fallita per !CURRENT_PROJECT!.
        SET "NUITKA_ERROR=1"
        SET "PYINSTALLER_ERROR=1"
        SET "CXFREEZE_ERROR=1"
        GOTO :next_project
    )
    echo - Ambiente virtuale attivato per !CURRENT_PROJECT!.
    echo.
    
    echo [5] Installazione delle dipendenze di runtime...
    pip install --upgrade pip setuptools wheel >nul 2>&1
    pip install -r "!PROJECT_PATH!\requirements.txt" >nul 2>&1
    IF !ERRORLEVEL! NEQ 0 (
        echo ERRORE: Installazione delle dipendenze di runtime fallita per !CURRENT_PROJECT!.
        SET "NUITKA_ERROR=1"
        SET "PYINSTALLER_ERROR=1"
        SET "CXFREEZE_ERROR=1"
        GOTO :next_project
    )
    echo - Dipendenze di runtime installate per !CURRENT_PROJECT!.
    echo.
    
    echo [6] Installazione delle dipendenze di sviluppo...
    pip install -r "!PROJECT_PATH!\requirements-dev.txt" >nul 2>&1
    IF !ERRORLEVEL! NEQ 0 (
        echo ERRORE: Installazione delle dipendenze di sviluppo fallita per !CURRENT_PROJECT!.
        SET "NUITKA_ERROR=1"
        SET "PYINSTALLER_ERROR=1"
        SET "CXFREEZE_ERROR=1"
        GOTO :next_project
    )
    echo - Dipendenze di sviluppo installate per !CURRENT_PROJECT!.
    echo.
    
    :: -------------------------------------------------
    :: Passo [7] Pulizia Build/Dist/Release
    :: -------------------------------------------------
    echo [7] Pulizia delle cartelle di build...
    IF EXIST "!BUILD_DIR!" (
        RMDIR /S /Q "!BUILD_DIR!"
        echo - Cartella build rimossa per !CURRENT_PROJECT!.
    )
    IF EXIST "!DIST_DIR!" (
        RMDIR /S /Q "!DIST_DIR!"
        echo - Cartella dist rimossa per !CURRENT_PROJECT!.
    )
    IF EXIST "!RELEASE_DIR!" (
        RMDIR /S /Q "!RELEASE_DIR!"
        echo - Cartella release rimossa per !CURRENT_PROJECT!.
    )
    echo.
    
    :: -------------------------------------------------
    :: Passo [8] Rilevazione Icona .ico in Resources
    :: -------------------------------------------------
    echo [8] Rilevazione dell'icona .ico in !RESOURCES_DIR!...
    SET "ICON_NAME="
    FOR %%I IN ("!RESOURCES_DIR!\*.ico") DO (
        SET "ICON_NAME=%%~nI%%~xI"
        GOTO :found_ico
    )
    :found_ico
    IF DEFINED ICON_NAME (
        echo - Icona rilevata: !ICON_NAME!
    ) ELSE (
        echo - Nessuna icona .ico trovata in !RESOURCES_DIR!.
    )
    echo.
    
    :: -------------------------------------------------
    :: Passo [9] Selezione dello Strumento di Compilazione
    :: -------------------------------------------------
    echo [9] Selezione dello strumento di compilazione per !CURRENT_PROJECT!:
    echo.
    echo   1. Nuitka
    echo   2. PyInstaller
    echo   3. cx-Freeze
    echo   4. Salta
    echo.
    SET /P "TOOL_CHOICE=Seleziona l'opzione (1-4): "
    
    IF "%TOOL_CHOICE%"=="1" GOTO compile_nuitka
    IF "%TOOL_CHOICE%"=="2" GOTO compile_pyinstaller
    IF "%TOOL_CHOICE%"=="3" GOTO compile_cxfreeze
    IF "%TOOL_CHOICE%"=="4" GOTO :next_project
    
    echo Opzione non valida. Riprova.
    echo.
    GOTO :select_tool
    
    :: -------------------------------------------------
    :: Passo [10] Compilazione con Nuitka
    :: -------------------------------------------------
    :compile_nuitka
    echo [10] Compilazione con Nuitka in corso per !CURRENT_PROJECT!...
    IF NOT EXIST "!ONEFILE_TEMPDIR!" (
        MD "!ONEFILE_TEMPDIR!" >nul 2>&1
        echo - Cartella temporanea creata: !ONEFILE_TEMPDIR!
    )
    IF NOT EXIST "!DIST_DIR!" (
        MD "!DIST_DIR!" >nul 2>&1
        echo - Cartella dist creata: !DIST_DIR!
    )
    
    :: Costruzione del comando Nuitka
    SET "NUITKA_CMD=python -m nuitka --onefile --onefile-tempdir=""!ONEFILE_TEMPDIR!"" --windows-disable-console --enable-plugin=tk-inter --include-data-dir=""!RESOURCES_DIR!=resources"" --output-dir=""!DIST_DIR!"" "
    
    IF DEFINED ICON_NAME (
        SET "NUITKA_CMD=!NUITKA_CMD! --windows-icon-from-ico=""!RESOURCES_DIR!\!ICON_NAME!"" "
    )
    
    SET "NUITKA_CMD=!NUITKA_CMD! ""!SRC_DIR!\!SCRIPT_NAME!"" "
    
    echo - Esecuzione di Nuitka...
    echo !NUITKA_CMD! > "!PROJECT_PATH!\temp_nuitka_log.txt"
    %NUITKA_CMD% >> "!PROJECT_PATH!\temp_nuitka_log.txt" 2>&1
    
    IF !ERRORLEVEL! NEQ 0 (
        echo ERRORE: Nuitka ha fallito per !CURRENT_PROJECT!.
        move /Y "!PROJECT_PATH!\temp_nuitka_log.txt" "!PROJECT_PATH!\error_nuitka_log.txt" >nul 2>&1
        echo Controlla error_nuitka_log.txt per maggiori dettagli.
        SET "NUITKA_ERROR=1"
        GOTO :next_project
    ) ELSE (
        echo - Compilazione con Nuitka completata per !CURRENT_PROJECT!.
        DEL "!PROJECT_PATH!\temp_nuitka_log.txt" >nul 2>&1
    )
    echo.
    
    :: Spostamento dell'eseguibile e copia delle risorse
    echo [11] Spostamento dell'eseguibile e copia delle risorse...
    IF NOT EXIST "!RELEASE_DIR!" (
        MD "!RELEASE_DIR!" >nul 2>&1
        echo - Cartella release creata: !RELEASE_DIR!
    )
    
    SET "GENERATED_EXE=!DIST_DIR!\!SCRIPT_NAME:.py=.exe!"
    IF EXIST "!GENERATED_EXE!" (
        REN "!GENERATED_EXE!" "!DESIRED_EXE_NAME!"
        MOVE /Y "!DIST_DIR!\!DESIRED_EXE_NAME!" "!RELEASE_DIR!\" >nul 2>&1
        echo - Eseguibile rinominato e spostato in release: !RELEASE_DIR!\!DESIRED_EXE_NAME!
    
        :: Copia della cartella resources nella release
        IF EXIST "!RESOURCES_DIR!" (
            echo - Copia della cartella resources in release...
            xcopy /E /I /Y "!RESOURCES_DIR!" "!RELEASE_DIR!\!RESOURCES_DIR!" >nul
            IF !ERRORLEVEL! NEQ 0 (
                echo ERRORE: Copia della cartella resources fallita.
                SET "NUITKA_ERROR=1"
            ) ELSE (
                echo - Cartella resources copiata in release.
            )
        ) ELSE (
            echo - Nessuna cartella resources da copiare.
        )
    ) ELSE (
        echo ERRORE: Eseguibile non trovato dopo la compilazione con Nuitka.
        SET "NUITKA_ERROR=1"
    )
    echo.
    
    :: (Opzionale) Compressione con UPX
    IF EXIST "!UPX_PATH!" (
        IF EXIST "!RELEASE_DIR!\!DESIRED_EXE_NAME!" (
            echo [12] Compressione con UPX in corso...
            "!UPX_PATH!" --best --lzma --force "!RELEASE_DIR!\!DESIRED_EXE_NAME!" >nul 2>&1
            IF !ERRORLEVEL! NEQ 0 (
                SET "UPX_ERROR=1"
                echo - ERRORE durante la compressione con UPX.
            ) ELSE (
                echo - Compressione con UPX completata.
            )
        )
    )
    echo.
    
    GOTO :next_project
    
    :: -------------------------------------------------
    :: Passo [12] Compilazione con PyInstaller
    :: -------------------------------------------------
    :compile_pyinstaller
    echo [12] Compilazione con PyInstaller in corso per !CURRENT_PROJECT!...
    IF NOT EXIST "!DIST_DIR!" (
        MD "!DIST_DIR!" >nul 2>&1
        echo - Cartella dist creata: !DIST_DIR!
    )
    
    :: Costruzione del comando PyInstaller
    SET "PYINSTALLER_CMD=pyinstaller --onefile --noconsole --icon=""!RESOURCES_DIR!\!ICON_NAME!"" --add-data=""!RESOURCES_DIR!;resources"" --distpath ""!DIST_DIR!"" ""!SRC_DIR!\!SCRIPT_NAME!"" "
    
    echo - Esecuzione di PyInstaller...
    echo !PYINSTALLER_CMD! > "!PROJECT_PATH!\temp_pyinstaller_log.txt"
    %PYINSTALLER_CMD% >> "!PROJECT_PATH!\temp_pyinstaller_log.txt" 2>&1
    
    IF !ERRORLEVEL! NEQ 0 (
        echo ERRORE: PyInstaller ha fallito per !CURRENT_PROJECT!.
        move /Y "!PROJECT_PATH!\temp_pyinstaller_log.txt" "!PROJECT_PATH!\error_pyinstaller_log.txt" >nul 2>&1
        echo Controlla error_pyinstaller_log.txt per maggiori dettagli.
        SET "PYINSTALLER_ERROR=1"
        GOTO :next_project
    ) ELSE (
        echo - Compilazione con PyInstaller completata per !CURRENT_PROJECT!.
        DEL "!PROJECT_PATH!\temp_pyinstaller_log.txt" >nul 2>&1
    )
    echo.
    
    :: Spostamento dell'eseguibile e copia delle risorse
    echo [13] Spostamento dell'eseguibile e copia delle risorse...
    IF NOT EXIST "!RELEASE_DIR!" (
        MD "!RELEASE_DIR!" >nul 2>&1
        echo - Cartella release creata: !RELEASE_DIR!
    )
    
    SET "GENERATED_EXE=!DIST_DIR!\!SCRIPT_NAME:.py=.exe!"
    IF EXIST "!GENERATED_EXE!" (
        REN "!GENERATED_EXE!" "!DESIRED_EXE_NAME!"
        MOVE /Y "!DIST_DIR!\!DESIRED_EXE_NAME!" "!RELEASE_DIR!\" >nul 2>&1
        echo - Eseguibile rinominato e spostato in release: !RELEASE_DIR!\!DESIRED_EXE_NAME!
    
        :: Copia della cartella resources nella release
        IF EXIST "!RESOURCES_DIR!" (
            echo - Copia della cartella resources in release...
            xcopy /E /I /Y "!RESOURCES_DIR!" "!RELEASE_DIR!\!RESOURCES_DIR!" >nul
            IF !ERRORLEVEL! NEQ 0 (
                echo ERRORE: Copia della cartella resources fallita.
                SET "PYINSTALLER_ERROR=1"
            ) ELSE (
                echo - Cartella resources copiata in release.
            )
        ) ELSE (
            echo - Nessuna cartella resources da copiare.
        )
    ) ELSE (
        echo ERRORE: Eseguibile non trovato dopo la compilazione con PyInstaller.
        SET "PYINSTALLER_ERROR=1"
    )
    echo.
    
    :: (Opzionale) Compressione con UPX
    IF EXIST "!UPX_PATH!" (
        IF EXIST "!RELEASE_DIR!\!DESIRED_EXE_NAME!" (
            echo [14] Compressione con UPX in corso...
            "!UPX_PATH!" --best --lzma --force "!RELEASE_DIR!\!DESIRED_EXE_NAME!" >nul 2>&1
            IF !ERRORLEVEL! NEQ 0 (
                SET "UPX_ERROR=1"
                echo - ERRORE durante la compressione con UPX.
            ) ELSE (
                echo - Compressione con UPX completata.
            )
        )
    )
    echo.
    
    GOTO :next_project
    
    :: -------------------------------------------------
    :: Passo [14] Compilazione con cx-Freeze
    :: -------------------------------------------------
    :compile_cxfreeze
    echo [14] Compilazione con cx-Freeze in corso per !CURRENT_PROJECT!...
    
    :: Creazione dinamica di setup_cxfreeze.py
    echo [14.1] Creazione di setup_cxfreeze.py...
    (
    echo import sys
    echo import os
    echo from cx_Freeze import setup, Executable
    echo.
    echo # -------------------------------------------------
    echo # Configurazione Generale
    echo # -------------------------------------------------
    echo PROJECT_NAME = "!CURRENT_PROJECT!"
    echo VERSION = "1.0"
    echo.
    echo SRC_DIR = "src"
    echo RESOURCES_DIR = "resources"
    echo.
    echo MAIN_SCRIPT = os.path.join(SRC_DIR, "!SCRIPT_NAME!")
    echo.
    echo ICON_PATH = os.path.join(RESOURCES_DIR, "icon.ico") REM Assicurati che esista
    echo.
    echo # Opzioni di build
    echo build_exe_options = {
    echo     "packages": ["os", "sys", "logging", "requests", "pathlib", "shutil", "datetime",
    echo                  "tkinter", "re", "platform", "subprocess", "configparser", "time",
    echo                  "darkdetect", "ttkbootstrap", "threading", "ctypes", "json"],
    echo     "include_files": [
    echo         (RESOURCES_DIR, "resources")
    echo     ],
    echo     "include_msvcr": True,
    echo     "excludes": [],
    echo     "optimize": 2,
    echo }
    echo.
    echo # Base dell'eseguibile
    echo base = "Win32GUI" if sys.platform == "win32" else None
    echo.
    echo # Creazione dell'Executable
    echo executables = [
    echo     Executable(
    echo         script=MAIN_SCRIPT,
    echo         base=base,
    echo         icon=ICON_PATH,
    echo         target_name="!DESIRED_EXE_NAME!"
    echo     )
    echo ]
    echo.
    echo # Setup di cx-Freeze
    echo setup(
    echo     name=PROJECT_NAME,
    echo     version=VERSION,
    echo     description="!PROJECT_NAME! Application",
    echo     options={"build_exe": build_exe_options},
    echo     executables=executables
    echo )
    ) > "!PROJECT_PATH!\setup_cxfreeze.py"
    echo - setup_cxfreeze.py creato per !CURRENT_PROJECT!.
    echo.
    
    :: Esecuzione di cx-Freeze
    echo [14.2] Esecuzione di cx-Freeze...
    python "!PROJECT_PATH!\setup_cxfreeze.py" build > "!PROJECT_PATH!\temp_cxfreeze_log.txt" 2>&1
    
    IF !ERRORLEVEL! NEQ 0 (
        echo ERRORE: cx-Freeze ha fallito per !CURRENT_PROJECT!.
        move /Y "!PROJECT_PATH!\temp_cxfreeze_log.txt" "!PROJECT_PATH!\error_cxfreeze_log.txt" >nul 2>&1
        echo Controlla error_cxfreeze_log.txt per maggiori dettagli.
        SET "CXFREEZE_ERROR=1"
        GOTO :next_project
    ) ELSE (
        echo - Compilazione con cx-Freeze completata per !CURRENT_PROJECT!.
        DEL "!PROJECT_PATH!\temp_cxfreeze_log.txt" >nul 2>&1
    )
    echo.
    
    :: Spostamento dell'eseguibile e copia delle risorse
    echo [15] Spostamento dell'eseguibile e copia delle risorse...
    IF NOT EXIST "!RELEASE_DIR!" (
        MD "!RELEASE_DIR!" >nul 2>&1
        echo - Cartella release creata: !RELEASE_DIR!
    )
    
    :: Supponiamo che l'eseguibile si trovi in build_!CURRENT_PROJECT!\!DESIRED_EXE_NAME!
    SET "GENERATED_EXE=!BUILD_DIR!\!DESIRED_EXE_NAME!"
    IF EXIST "!GENERATED_EXE!" (
        MOVE /Y "!GENERATED_EXE!" "!RELEASE_DIR!\" >nul 2>&1
        echo - Eseguibile spostato in release: !RELEASE_DIR!\!DESIRED_EXE_NAME!
    
        :: Copia della cartella resources nella release
        IF EXIST "!RESOURCES_DIR!" (
            echo - Copia della cartella resources in release...
            xcopy /E /I /Y "!RESOURCES_DIR!" "!RELEASE_DIR!\!RESOURCES_DIR!" >nul
            IF !ERRORLEVEL! NEQ 0 (
                echo ERRORE: Copia della cartella resources fallita.
                SET "CXFREEZE_ERROR=1"
            ) ELSE (
                echo - Cartella resources copiata in release.
            )
        ) ELSE (
            echo - Nessuna cartella resources da copiare.
        )
    ) ELSE (
        echo ERRORE: Eseguibile non trovato dopo la compilazione con cx-Freeze.
        SET "CXFREEZE_ERROR=1"
    )
    echo.
    
    :: (Opzionale) Compressione con UPX
    IF EXIST "!UPX_PATH!" (
        IF EXIST "!RELEASE_DIR!\!DESIRED_EXE_NAME!" (
            echo [16] Compressione con UPX in corso...
            "!UPX_PATH!" --best --lzma --force "!RELEASE_DIR!\!DESIRED_EXE_NAME!" >nul 2>&1
            IF !ERRORLEVEL! NEQ 0 (
                SET "UPX_ERROR=1"
                echo - ERRORE durante la compressione con UPX.
            ) ELSE (
                echo - Compressione con UPX completata.
            )
        )
    )
    echo.
    
    :next_project
    echo ============================================================
    echo Compilazione completata per !CURRENT_PROJECT!.
    echo ============================================================
    echo.
)

:: -------------------------------------------------
:: Pulizia Finale
:: -------------------------------------------------
echo [Finale] Pulizia delle cartelle temporanee generali...
:: Qui puoi aggiungere eventuali pulizie globali se necessario
echo - Pulizia completata.
echo.

:cleanup
IF "%NUITKA_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compilazione con Nuitka.
)
IF "%PYINSTALLER_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compilazione con PyInstaller.
)
IF "%CXFREEZE_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compilazione con cx-Freeze.
)
IF "%UPX_ERROR%"=="1" (
    echo [ATTENZIONE] Errore durante la compressione con UPX.
)

IF "%NUITKA_ERROR%"=="0" IF "%PYINSTALLER_ERROR%"=="0" IF "%CXFREEZE_ERROR%"=="0" IF "%UPX_ERROR%"=="0" (
    echo - Tutte le operazioni sono state completate con successo!
) ELSE (
    echo - Alcune operazioni sono state completate con errori. Controlla i messaggi sopra per dettagli.
)
echo.

:: Se l'operazione è completata, aggiungi una sezione finale con nome del progetto e anno
echo ============================================================
echo  Compilazione Multi-Tool - %DATE:~6,4%
echo ============================================================
echo.

echo Fine. Premi un tasto per chiudere...
pause >nul
ENDLOCAL
exit /b 0

:: -------------------------------------------------
:: Funzione di Terminazione in Caso di Errore
:: -------------------------------------------------
:terminate
echo.
echo ============================================================
echo  Compilazione Multi-Tool - %DATE:~6,4%
echo ============================================================
echo.
echo Fine. Premi un tasto per chiudere...
pause >nul
ENDLOCAL
exit /b 1
