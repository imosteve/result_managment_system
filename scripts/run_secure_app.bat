@echo off
setlocal enabledelayedexpansion

:: ---------- CONFIG - EDIT THESE ----------
set "ARCHIVE=C:\Users\imosteve\Documents\student_results_app_secure.rar"
set "VENV_ACTIVATE=C:\venvs\rms\Scripts\activate.bat"
:: -----------------------------------------

:: find WinRAR (common install locations)
if exist "%ProgramFiles%\WinRAR\WinRAR.exe" (
    set "WINRAR=%ProgramFiles%\WinRAR\WinRAR.exe"
) else if exist "%ProgramFiles(x86)%\WinRAR\WinRAR.exe" (
    set "WINRAR=%ProgramFiles(x86)%\WinRAR\WinRAR.exe"
) else (
    echo WinRAR not found in Program Files. If WinRAR is installed elsewhere, edit the WINRAR path in this file.
    pause
    exit /b 1
)

:: prompt for archive password (won't echo)
<nul set /p=Enter archive password: 
set /p "PW="

:: create a unique temp extraction folder
set "EXTRACT_DIR=%TEMP%\rms_app_%RANDOM%_%RANDOM%"
mkdir "%EXTRACT_DIR%"

echo Extracting archive to "%EXTRACT_DIR%" ...
"%WINRAR%" x -y -p"%PW%" "%ARCHIVE%" "%EXTRACT_DIR%\" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Extraction failed. Wrong password or archive corrupt.
    rd /s /q "%EXTRACT_DIR%" 2>nul
    pause
    exit /b 1
)

:: Activate the virtual environment (edit VENV_ACTIVATE above)
if not exist "%VENV_ACTIVATE%" (
    echo Virtual environment activate script not found: "%VENV_ACTIVATE%"
    echo Please edit the batch file and set VENV_ACTIVATE to your venv activate.bat
    rd /s /q "%EXTRACT_DIR%" 2>nul
    pause
    exit /b 1
)

call "%VENV_ACTIVATE%"

:: run the Streamlit app from the extracted folder
cd /d "%EXTRACT_DIR%\student_results_app"
echo Running Streamlit (listen on 0.0.0.0:8501). Press CTRL+C in this window to stop the server.
streamlit run main.py --server.address 0.0.0.0 --server.port 8501

:: Streamlit exited — cleanup
echo.
echo Stopping and cleaning up extracted files...

:: try to deactivate venv (if available)
if defined VIRTUAL_ENV (
    if exist "%VIRTUAL_ENV%\Scripts\deactivate.bat" (
        call "%VIRTUAL_ENV%\Scripts\deactivate.bat"
    )
)

:: IMPORTANT: go back to a safe directory before deletion
cd /d "%TEMP%"

:: remove extracted files
rd /s /q "%EXTRACT_DIR%" 2>nul

echo Done.
endlocal
pause
