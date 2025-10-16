@echo off
cd /d "C:\Users\imosteve\Documents\Result system\python system\student_results_app"

:: activate the virtual environment
call "C:\venvs\rms\Scripts\activate.bat"

:: run the app on 0.0.0.0 so other devices in LAN can access
streamlit run main.py --server.address 0.0.0.0 --server.port 8501

pause
