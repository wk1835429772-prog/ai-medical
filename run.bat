@echo off
echo ========================================
echo   临床助手 - 启动中...
echo ========================================
cd /d "%~dp0"
if not exist ".venv" (
    echo [1/2] 首次运行，正在安装依赖...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)
echo [2/2] 启动应用...
streamlit run app.py --server.port 8501
pause
