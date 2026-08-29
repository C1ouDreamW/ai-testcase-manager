@echo off
setlocal
cd /d "%~dp0"

set "SUITE=%~1"
if "%SUITE%"=="" set "SUITE=all"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0.browsers"

if not exist ".browsers" (
  if /i "%SUITE%"=="ui" uv run playwright install chromium
  if /i "%SUITE%"=="all" uv run playwright install chromium
  if /i "%SUITE%"=="smoke" uv run playwright install chromium
)

if not exist "reports" mkdir "reports"

set "COMMON=--screenshot only-on-failure --output ui/artifacts"

if /i "%SUITE%"=="api" (
  uv run pytest api --html reports/api-report.html --self-contained-html
) else if /i "%SUITE%"=="ui" (
  uv run pytest ui %COMMON% --html reports/ui-report.html --self-contained-html
) else if /i "%SUITE%"=="smoke" (
  uv run pytest -m smoke %COMMON% --html reports/smoke-report.html --self-contained-html
) else if /i "%SUITE%"=="all" (
  uv run pytest api ui %COMMON% --html reports/full-report.html --self-contained-html
) else (
  echo 用法: run_tests.bat [api^|ui^|smoke^|all]
  exit /b 1
)
endlocal
