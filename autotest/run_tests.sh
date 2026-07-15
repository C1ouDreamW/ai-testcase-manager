#!/usr/bin/env bash
# 一键运行自动化测试：./run_tests.sh [api|ui|smoke|all|allure]
#   allure - 仅从已有结果生成 Allure 报告（跳过测试执行）
set -euo pipefail
cd "$(dirname "$0")"

SUITE="${1:-all}"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers"

if [ ! -d .venv ]; then
  echo "==> 初始化虚拟环境 (uv)"
  uv sync
fi

if [ ! -d .browsers ] && { [ "$SUITE" = "ui" ] || [ "$SUITE" = "all" ] || [ "$SUITE" = "smoke" ]; }; then
  echo "==> 安装 Playwright Chromium"
  uv run playwright install chromium
fi

run_tests() {
  local extra_args=("${@}")
  rm -rf reports/allure-results
  uv run pytest "${extra_args[@]}" --alluredir=reports/allure-results
}

case "$SUITE" in
  api)
    run_tests api
    ;;
  ui)
    run_tests ui --screenshot only-on-failure --output ui/artifacts
    ;;
  smoke)
    run_tests -m smoke --screenshot only-on-failure --output ui/artifacts
    ;;
  all)
    run_tests api ui --screenshot only-on-failure --output ui/artifacts
    ;;
  allure)
    ;;
  *)
    echo "用法: $0 [api|ui|smoke|all|allure]" && exit 1
    ;;
esac

if [ -d reports/allure-results ]; then
  rm -rf reports/allure-report
  allure generate reports/allure-results -o reports/allure-report --clean
  echo "==> Allure 报告: reports/allure-report/index.html"
fi
