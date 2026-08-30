@echo off
chcp 65001 >nul
setlocal EnableExtensions

cd /d "%~dp0"

echo ==========================================
echo   AITC — 一键重启（Windows）
echo ==========================================
echo.

echo [1/3] 清理占用端口的旧进程...
call :kill_port 8000
call :kill_port 5173
timeout /t 1 /nobreak >nul

if not exist backend\.venv\Scripts\python.exe (
    echo [错误] 未找到后端虚拟环境，请先运行 setup.bat。
    pause
    exit /b 1
)

if not exist frontend\node_modules (
    echo [错误] 未找到前端依赖，请先运行 setup.bat。
    pause
    exit /b 1
)

if not exist .env (
    copy .env.example .env >nul
    echo   已创建 .env
)

echo.
echo [2/3] 启动后端 (uvicorn :8000)...
start "AITC Backend" /D "%~dp0backend" cmd /k "uv run python -m uvicorn app.main:app --reload --port 8000"

echo.
echo [3/3] 启动前端 (vite :5173)...
start "AITC Frontend" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo ==========================================
echo   ✅ 重启完成！
echo   前端: http://localhost:5173
echo   后端: http://localhost:8000
echo ==========================================
echo.
goto :eof

:kill_port
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%1 " ^| findstr LISTENING 2^>nul') do (
    echo   终止 PID %%a（端口 %1）
    taskkill /f /pid %%a >nul 2>&1
)
goto :eof
