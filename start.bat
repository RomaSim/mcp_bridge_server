@echo off
chcp 65001 >nul
REM Скрипт запуска MCP Bridge Server (Windows)

echo ========================================
echo Средство запуска MCP Bridge Server
echo ========================================
echo.

REM Проверить, установлен ли Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [Ошибка] Python не найден. Сначала установите Python 3.8+
    pause
    exit /b 1
)

echo Выберите режим запуска:
echo.
echo   1. Запуск по умолчанию (интерактивный, порт 3849)
echo   2. Автоматически завершить процесс, занимающий порт (порт 3849)
echo   3. Запуск с пользовательским портом
echo   4. Просмотр справки
echo   5. Выход
echo.

set /p choice="Введите вариант (1-5): "

if "%choice%"=="1" (
    echo.
    echo Запуск в интерактивном режиме...
    python utils\mcp_bridge_ru.py
) else if "%choice%"=="2" (
    echo.
    echo Запуск с автоматическим завершением процесса, занимающего порт...
    python utils\mcp_bridge_ru.py --auto-kill-port
) else if "%choice%"=="3" (
    echo.
    set /p port="Введите номер порта: "
    set /p auto_kill="Автоматически завершить процесс, занимающий порт? (y/n): "
    
    if /i "%auto_kill%"=="y" (
        python utils\mcp_bridge_ru.py --port %port% --auto-kill-port
    ) else (
        python utils\mcp_bridge_ru.py --port %port%
    )
) else if "%choice%"=="4" (
    echo.
    python utils\mcp_bridge_ru.py --help
    echo.
    pause
    goto :eof
) else if "%choice%"=="5" (
    exit /b 0
) else (
    echo.
    echo [Ошибка] Неверный вариант
    pause
    exit /b 1
)

pause