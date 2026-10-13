@echo off
chcp 65001 >nul
title 晨报卡（改版 UI）
setlocal

rem 统一走 tools\launch.py：它会选好模型通路、语音桥、空闲端口，
rem 并在旁边挂一只看门狗（万一界面白屏会自动把卡片拉起来）。
set "ROOT=%~dp0"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if not exist "%ROOT%tools\launch.py" (
  echo 找不到启动器：%ROOT%tools\launch.py
  pause
  exit /b 1
)
where python >nul 2>&1
if errorlevel 1 (
  echo 找不到 Python，请确认 Python 已安装并加入 PATH。
  pause
  exit /b 1
)
cd /d "%ROOT%"
python -u tools\launch.py %*
if errorlevel 1 (
  echo.
  echo 启动失败，请查看上方错误信息。
  pause
  exit /b 1
)
exit /b 0
