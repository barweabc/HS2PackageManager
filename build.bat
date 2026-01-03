@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ========================================
echo    HS2 资源包管理工具 打包脚本
echo ========================================

set PYTHON_CMD=python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    set PYTHON_CMD=py
)

echo 正在清理旧的构建文件...
if exist "build" rd /s /q "build"
if exist "*.spec" del /q "*.spec"

@REM 从 pyproject.toml 中读取 project.version
set VERSION=unknown
for /f "usebackq tokens=*" %%a in (`%PYTHON_CMD% -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"`) do (
    set VERSION=%%a
)

echo 正在开始打包 [版本: !VERSION!] 请稍候...
%PYTHON_CMD% -m PyInstaller --onefile --noconsole --name "HS2资源包管理工具_v!VERSION!" --add-data "pyproject.toml;." --clean --noconfirm "main.py"

if %errorlevel% equ 0 (
    echo 正在清理临时文件...
    if exist "build" rd /s /q "build"
    if exist "*.spec" del /q "*.spec"
    echo.
    echo ========================================
    echo 打包完成 [版本: !VERSION!]
    echo 可执行文件位于 dist 目录
    echo ========================================
) else (
    echo.
    echo [错误] 打包过程中出现问题。
)

@REM pause