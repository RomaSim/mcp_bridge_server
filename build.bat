@echo off
chcp 65001 >nul
REM Скрипт сборки MCP Bridge Server (Windows)

echo ========================================
echo Средство сборки MCP Bridge Server
echo ========================================
echo.

REM Проверить Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [Ошибка] Python не найден
    pause
    exit /b 1
)

REM Проверить PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [Предупреждение] PyInstaller не установлен, выполняется установка...
    pip install pyinstaller
)

echo Выберите вариант сборки:
echo.
echo   1. Сборка в один файл (рекомендуется, удобно для распространения)
echo   2. Сборка в каталог (быстрее запуск)
echo   3. Сборка с использованием spec-файла (включает все оптимизации)
echo   4. Очистить файлы сборки
echo   5. Выход
echo.

set /p choice="Введите вариант (1-5): "

if "%choice%"=="1" (
    echo.
    echo Выполняется сборка в один файл...
    echo.
    
    REM Очистить старые файлы
    if exist build rmdir /s /q build
    if exist dist rmdir /s /q dist
    
    REM Сборка
    pyinstaller --onefile ^
        --name mcp-bridge-server ^
        --add-data "README.md;." ^
        --add-data "docs;docs" ^
        --hidden-import mcp ^
        --hidden-import mcp.client.stdio ^
        --hidden-import mcp.client.sse ^
        --hidden-import uvicorn.logging ^
        --hidden-import uvicorn.loops.auto ^
        --hidden-import uvicorn.protocols.http.auto ^
        --exclude-module tkinter ^
        --exclude-module matplotlib ^
        utils\mcp_bridge.py
    
    echo.
    echo ✓ Сборка завершена!
    echo Выходной файл: dist\mcp-bridge-server.exe
    
) else if "%choice%"=="2" (
    echo.
    echo Выполняется сборка в каталог...
    echo.
    
    REM Очистить старые файлы
    if exist build rmdir /s /q build
    if exist dist rmdir /s /q dist
    
    REM Сборка
    pyinstaller --onedir ^
        --name mcp-bridge-server ^
        --add-data "README.md;." ^
        --add-data "docs;docs" ^
        --hidden-import mcp ^
        --hidden-import mcp.client.stdio ^
        --hidden-import mcp.client.sse ^
        --hidden-import uvicorn.logging ^
        --hidden-import uvicorn.loops.auto ^
        --hidden-import uvicorn.protocols.http.auto ^
        utils\mcp_bridge.py
    
    echo.
    echo ✓ Сборка завершена!
    echo Выходной каталог: dist\mcp-bridge-server\
    
) else if "%choice%"=="3" (
    echo.
    echo Сборка с использованием spec-файла...
    echo.
    
    REM Очистить старые файлы
    if exist build rmdir /s /q build
    if exist dist rmdir /s /q dist
    
    REM Сборка
    pyinstaller mcp_bridge.spec
    
    echo.
    echo ✓ Сборка завершена!
    echo Выходной файл: dist\mcp-bridge-server.exe
    
) else if "%choice%"=="4" (
    echo.
    echo Очистка файлов сборки...
    
    if exist build (
        rmdir /s /q build
        echo ✓ Каталог build удалён
    )
    
    if exist dist (
        rmdir /s /q dist
        echo ✓ Каталог dist удалён
    )
    
    if exist *.spec (
        del *.spec
        echo ✓ Временные spec-файлы удалены
    )
    
    echo.
    echo ✓ Очистка завершена
    
) else if "%choice%"=="5" (
    exit /b 0
) else (
    echo.
    echo [Ошибка] Неверный вариант
)

echo.
echo ========================================
echo.

REM Спросить, нужно ли тестирование
if exist dist\mcp-bridge-server.exe (
    set /p test="Протестировать собранную программу? (y/n): "
    if /i "%test%"=="y" (
        echo.
        echo Запуск программы...
        echo Нажмите Ctrl+C, чтобы остановить тест
        echo.
        dist\mcp-bridge-server.exe --help
    )
)

pause