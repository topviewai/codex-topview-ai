@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ==========================================
echo   社交媒体视频上传工具 - 一键安装 (Windows)
echo ==========================================
echo.

REM ---------- 检查 Python ----------
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 python，请先安装 Python 3.9+
    echo    下载地址: https://www.python.org/downloads/
    echo    安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PY_VERSION=%%i
for /f "tokens=*" %%i in ('python -c "import sys; print(sys.version_info.major)"') do set PY_MAJOR=%%i
for /f "tokens=*" %%i in ('python -c "import sys; print(sys.version_info.minor)"') do set PY_MINOR=%%i

if %PY_MAJOR% lss 3 (
    echo [错误] Python 版本需要 ^>= 3.9，当前为 %PY_VERSION%
    pause
    exit /b 1
)
if %PY_MAJOR% equ 3 if %PY_MINOR% lss 9 (
    echo [错误] Python 版本需要 ^>= 3.9，当前为 %PY_VERSION%
    pause
    exit /b 1
)
echo [OK] 检测到 Python %PY_VERSION%

REM ---------- 创建虚拟环境 ----------
if exist ".venv" (
    echo [提示] 发现已有 .venv，跳过创建
) else (
    echo [安装] 创建虚拟环境 .venv ...
    python -m venv .venv
    echo [OK] 虚拟环境已创建
)

set PIP=.venv\Scripts\pip.exe
set PYTHON_VENV=.venv\Scripts\python.exe

REM ---------- 升级 pip ----------
echo [安装] 升级 pip / setuptools / wheel ...
if exist "vendor_wheels" (
    %PIP% install --no-index --find-links vendor_wheels --upgrade pip setuptools wheel -q 2>nul
    if %errorlevel% neq 0 (
        %PIP% install --upgrade pip setuptools wheel -q
    )
) else (
    %PIP% install --upgrade pip setuptools wheel -q
)

REM ---------- 安装依赖 ----------
echo [安装] 安装依赖包 ...
echo [提示] 离线 wheel 包为 macOS 版本，Windows 将从网络安装依赖
%PIP% install certifi charset-normalizer click cssselect DataRecorder "DownloadKit>=2.0.7" et_xmlfile filelock idna lxml openpyxl packaging psutil requests requests-file "tldextract>=3.4.4" urllib3 websocket-client -q
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)
echo [OK] 依赖安装完成

REM ---------- 安装本地 DrissionPage ----------
echo [安装] 安装本地 DrissionPage (v4.1.1.2) ...
%PIP% install "%~dp0DrissionPage" -q
echo [OK] DrissionPage 已安装

REM ---------- 安装主项目 ----------
echo [安装] 安装 social-uploader CLI ...
%PIP% install -e "%~dp0." -q
echo [OK] social-uploader 已安装

REM ---------- 验证 ----------
echo.
echo ==========================================
echo   验证安装
echo ==========================================
.venv\Scripts\social-upload.exe --help

echo.
echo ==========================================
echo   安装完成！
echo ==========================================
echo.
echo 使用方式：
echo   1. 双击 start_chrome_debug.bat 启动 Chrome 调试模式
echo   2. 在浏览器中手动登录目标平台（TikTok / Instagram / YouTube）
echo   3. 上传视频：
echo      .venv\Scripts\social-upload tiktok --video "视频.mp4" --title "标题" --description "描述"
echo      .venv\Scripts\social-upload instagram --video "视频.mp4" --caption "文案"
echo      .venv\Scripts\social-upload youtube --video "视频.mp4" --title "标题" --description "描述"
echo.
pause
