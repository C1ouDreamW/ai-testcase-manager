@echo off
chcp 65001 >nul
setlocal EnableExtensions

cd /d "%~dp0"

if not exist backend\.venv\Scripts\python.exe (
    echo [错误] 未找到后端虚拟环境。
    echo 请先双击运行 setup.bat。
    pause
    exit /b 1
)

if not exist frontend\node_modules (
    echo [错误] 未找到前端依赖。
    echo 请先双击运行 setup.bat。
    pause
    exit /b 1
)

if not exist .env (
    echo [提示] 未找到 .env，正在从 .env.example 复制...
    copy .env.example .env >nul
)

echo ==========================================
echo   AITC — 启动前后端
echo ==========================================
echo.

echo [AITC] 启动后端 http://localhost:8000 ...
start "AITC Backend" /D "%~dp0backend" cmd /k "uv run python -m uvicorn app.main:app --reload --port 8000"

echo [AITC] 启动前端 http://localhost:5173 ...
start "AITC Frontend" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo ==========================================
echo   启动完成（两个新窗口分别跑前后端）
echo   前端:    http://localhost:5173
echo   后端:    http://localhost:8000
echo   API 文档: http://localhost:8000/docs
echo   默认账号: admin / nini123456（见 .env 的 AUTH 配置）
echo ==========================================
echo.
echo 关闭对应窗口即可停止服务。
pause
