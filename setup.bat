@echo off
REM setup.bat — Windows setup script
setlocal

echo [*] Kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python chua duoc cai. Tai tai: https://www.python.org/downloads/
    exit /b 1
)

echo [*] Kiem tra ffmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [!] ffmpeg chua duoc cai. Cac cach cai:
    echo     winget install Gyan.FFmpeg
    echo     choco install ffmpeg
    echo     Hoac tai thu cong: https://ffmpeg.org/download.html
    exit /b 1
)

echo [*] Tao virtualenv...
python -m venv venv
call venv\Scripts\activate.bat

echo [*] Cai Python packages...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [*] Khoi tao thu muc data...
if not exist "data\videos"    mkdir data\videos
if not exist "data\processed" mkdir data\processed
if not exist "logs"           mkdir logs
if not exist ".agents"        mkdir .agents

echo [*] Tao .env tu template...
if not exist "config\.env" (
    copy config\.env.example config\.env >nul
    echo [!] Hay dien credentials vao config\.env
)

echo.
echo [OK] Cai dat xong!
echo.
echo Cac buoc tiep theo:
echo   1. Dang ky TikTok Developer: https://developers.tiktok.com
echo   2. Tao app, bat scope: video.upload, video.publish
echo   3. Chay OAuth flow: python scripts\oauth_setup.py
echo   4. Dien tokens vao config\.env
echo   5. Chay thu: python scripts\run_agent.py --mode=once --video=test.mp4
endlocal
