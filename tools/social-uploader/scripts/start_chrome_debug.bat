@echo off
chcp 65001 >nul 2>&1

echo 正在关闭现有的 Chrome 进程...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM 按优先级尝试常见 Chrome 安装路径
set CHROME_PATH=

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
    goto :found
)
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    goto :found
)
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
    goto :found
)

echo [错误] 未找到 Google Chrome，请手动指定路径或安装 Chrome
echo    下载地址: https://www.google.com/chrome/
pause
exit /b 1

:found
echo 正在以调试模式启动 Google Chrome (端口 9222)...
start "" "%CHROME_PATH%" --remote-debugging-port=9222 --restore-last-session

echo 启动成功！现在你可以运行自动化脚本了。
echo.
echo 如果这是第一次使用，请先在浏览器中登录目标平台：
echo   - TikTok: https://www.tiktok.com
echo   - Instagram: https://www.instagram.com
echo   - YouTube: https://studio.youtube.com
echo.
pause
