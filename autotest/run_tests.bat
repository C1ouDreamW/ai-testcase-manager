@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
rem Run automated tests: run_tests.bat [api|ui|smoke|all|allure]
cd /d "%~dp0"

set "SUITE=%~1"
if "%SUITE%"=="" set "SUITE=all"
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0.browsers"
if not defined UV_CACHE_DIR set "UV_CACHE_DIR=%~dp0..\temp\uv-cache"
set "TEST_EXIT=0"

if not exist .venv\Scripts\python.exe (
    echo ==^> Initializing virtual environment with uv
    uv sync
    if errorlevel 1 ( echo Failed to install dependencies & pause & exit /b 1 )
)

if not exist .browsers (
    if not "%SUITE%"=="api" (
        echo ==^> Installing Playwright Chromium
        uv run playwright install chromium
    )
)

if exist reports\allure-results rmdir /s /q reports\allure-results
mkdir reports\allure-results
if "%SUITE%"=="allure" (
    goto :allure_report
)

if "%SUITE%"=="api" (
    set "ALLURE_DIR=reports\allure-results"
    uv run pytest api --alluredir=reports\allure-results
    set "TEST_EXIT=!ERRORLEVEL!"
) else if "%SUITE%"=="ui" (
    set "ALLURE_DIR=reports\allure-results"
    uv run pytest ui --screenshot only-on-failure --output ui\artifacts --alluredir=reports\allure-results
    set "TEST_EXIT=!ERRORLEVEL!"
) else if "%SUITE%"=="smoke" (
    set "ALLURE_DIR=reports\allure-results"
    uv run pytest -m smoke --screenshot only-on-failure --output ui\artifacts --alluredir=reports\allure-results
    set "TEST_EXIT=!ERRORLEVEL!"
) else if "%SUITE%"=="all" (
    set "ALLURE_DIR=reports\allure-results"
    uv run pytest api ui --screenshot only-on-failure --output ui\artifacts --alluredir=reports\allure-results
    set "TEST_EXIT=!ERRORLEVEL!"
) else (
    echo Usage: %~nx0 [api^|ui^|smoke^|all^|allure]
    exit /b 1
)

:allure_report
if exist reports\allure-report rmdir /s /q reports\allure-report
allure generate reports\allure-results -o reports\allure-report --clean
set "ALLURE_EXIT=%ERRORLEVEL%"
echo ==^> Allure report: reports\allure-report\index.html
if not "%TEST_EXIT%"=="0" exit /b %TEST_EXIT%
exit /b %ALLURE_EXIT%
