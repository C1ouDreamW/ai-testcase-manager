#!/usr/bin/env bash
# 一键运行自动化测试：./run_tests.sh [api|ui|smoke|all]
set -euo pipefail
cd "$(dirname "$0")"

SUITE="${1:-all}"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers"

if [ ! -d .browsers ] && { [ "$SUITE" = "ui" ] || [ "$SUITE" = "all" ] || [ "$SUITE" = "smoke" ]; }; then
  echo "==> 安装 Playwright Chromium"
  uv run playwright install chromium
fi

mkdir -p reports
COMMON=(--screenshot only-on-failure --output ui/artifacts)

case "$SUITE" in
  api)
    uv run pytest api --html reports/api-report.html --self-contained-html ;;
  ui)
    uv run pytest ui "${COMMON[@]}" --html reports/ui-report.html --self-contained-html ;;
  smoke)
    uv run pytest -m smoke "${COMMON[@]}" --html reports/smoke-report.html --self-contained-html ;;
  all)
    uv run pytest api ui "${COMMON[@]}" --html reports/full-report.html --self-contained-html ;;
  *)
    echo "用法: $0 [api|ui|smoke|all]" && exit 1 ;;
esac
