@echo off
chcp 65001 >nul
setlocal EnableExtensions

echo ==========================================
echo   AITC — Windows 首次环境安装
echo ==========================================
echo.

where uv >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 uv，请先安装：https://docs.astral.sh/uv/
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 npm，请先安装 Node.js 22+ ^(LTS^)。
    pause
    exit /b 1
)

echo [1/3] 安装后端依赖...
cd /d "%~dp0backend"
uv sync --all-groups
if errorlevel 1 (
    echo [错误] 后端依赖安装失败。
    pause
    exit /b 1
)

echo.
echo [2/3] 准备 .env ...
cd /d "%~dp0"
if not exist .env (
    copy .env.example .env >nul
    echo   已从 .env.example 创建 .env ^(默认 Mock 模式，可不配 API Key^)
) else (
    echo   .env 已存在，跳过
)

echo.
echo [3/3] 安装前端依赖...
cd /d "%~dp0frontend"
call npm install
if errorlevel 1 (
    echo [错误] 前端依赖安装失败。
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   安装完成
echo   下一步：双击 start.bat 启动项目
echo   或双击 restart.bat 清理端口后启动
echo ==========================================
pause
