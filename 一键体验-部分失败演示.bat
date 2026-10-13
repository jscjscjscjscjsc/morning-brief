@echo off
rem ============================================================
rem  晨报卡 — 失败状态演示（大赛要求：演示里必须有一个失败/空状态）
rem  这个入口专门演示「数据来源出问题时，卡片怎么如实告诉你」。
rem  真正的启动逻辑在 tools\launch.py（自动找宿主、配模型通路、起看门狗）；
rem  这里只指定演示用的作品包和独立存档。
rem ============================================================
chcp 65001 >nul
title 晨报卡 — 演示：来源失败时会发生什么
setlocal

echo.
echo  这个入口专门演示「数据来源出问题时，卡片怎么如实告诉你」。
echo  稍等 10-20 秒，会弹出一个窗口。
echo  操作顺序：点「生成晨报」→ 点「批准并取数」→ 等一下，看结果区的失败提示。
echo.

set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0tools\launch.py" --bundle "my-entry\demo-partial\bundle" --port 8161 --no-watchdog
echo.
echo  体验结束。
pause
