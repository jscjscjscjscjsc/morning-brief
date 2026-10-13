@echo off
title 晨报卡 — 演示：来源失败时会发生什么
echo 这个入口专门演示「数据来源出问题时，卡片怎么如实告诉你」。
echo 稍等 10-20 秒，会弹出一个窗口。
echo 操作顺序：点「生成晨报」→ 点「批准并取数」→ 等一下，看结果区的失败提示。
echo.
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set OCTO_HUB=C:\rustbuild\octosense-hub\x86_64-pc-windows-gnu\release\hub.exe
set OCTO_CARD_HOST=C:\rustbuild\octosense-hub\x86_64-pc-windows-gnu\release\card-host.exe
set OCTOSENSE_APP_HUB=C:\Users\Admin（无密码）\Desktop\数据文件\黑客松比赛项目\OctoSense-App-Hub
cd /d "C:\Users\Admin（无密码）\Desktop\数据文件\黑客松比赛项目"
python "OctoScript-App-Design-Flow\tools\octo" run "my-entry\demo-partial\bundle" --port 8161 --timeout 120
echo.
echo 体验结束。
pause
