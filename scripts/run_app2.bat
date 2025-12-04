@echo off
REM ------------------------------
REM START: Streamlit + NGINX launcher
REM Run this file as Administrator
REM ------------------------------

REM --------- Config ----------
set NGINX_DIR=C:\nginx
set APP_DIR=C:\Users\imosteve\Documents\Result system\python system\student_results_app
set VENV_ACTIVATE=C:\venvs\rms\Scripts\activate.bat
set STREAMLIT_CMD=streamlit run main.py --server.address 0.0.0.0 --server.port 8501
REM --------------------------

echo Starting Nginx from %NGINX_DIR%...
pushd "%NGINX_DIR%"

REM Test nginx config first (prints result)
.\nginx.exe -t
if %errorlevel% neq 0 (
    echo nginx config test failed. Check %NGINX_DIR%\logs\error.log
    pause
    popd
    exit /b 1
)

REM Start nginx in new window and with correct working dir
start "nginx" /D "%NGINX_DIR%" "%NGINX_DIR%\nginx.exe"

REM Wait up to 8 seconds for nginx to appear in tasklist
set /a WAIT=0
:wait_nginx
tasklist | findstr /I nginx.exe >nul
if %errorlevel%==0 (
    echo Nginx started successfully.
) else (
    if %WAIT% GEQ 8 (
        echo Timeout waiting for nginx to start. Check %NGINX_DIR%\logs\error.log
        popd
        pause
        exit /b 1
    )
    set /a WAIT+=1
    timeout /t 1 >nul
    goto wait_nginx
)

popd

REM Start Streamlit in the app folder inside the venv
echo Starting Streamlit...
pushd "%APP_DIR%"
call "%VENV_ACTIVATE%"

REM Open browser to the local hostname (optional)
start "" "http://suisportal.local"

REM Run streamlit (this blocks until you close it)
%STREAMLIT_CMD%

REM When Streamlit exits, kill nginx
echo Streamlit exited. Stopping Nginx...
taskkill /IM nginx.exe /F >nul 2>&1

popd

echo Done.
pause
