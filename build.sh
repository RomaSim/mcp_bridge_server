#!/bin/bash
# Скрипт сборки MCP Bridge Server (Linux/Mac)

echo "========================================"
echo "Средство сборки MCP Bridge Server"
echo "========================================"
echo

# Проверить Python
if ! command -v python3 &> /dev/null; then
    echo "[Ошибка] Python3 не найден"
    exit 1
fi

# Проверить PyInstaller
if ! python3 -c "import PyInstaller" &> /dev/null; then
    echo "[Предупреждение] PyInstaller не установлен, выполняется установка..."
    pip3 install pyinstaller
fi

echo "Выберите вариант сборки:"
echo
echo "  1. Сборка в один файл (рекомендуется, удобно для распространения)"
echo "  2. Сборка в каталог (быстрее запуск)"
echo "  3. Сборка с использованием spec-файла (включает все оптимизации)"
echo "  4. Очистить файлы сборки"
echo "  5. Выход"
echo

read -p "Введите вариант (1-5): " choice

case $choice in
    1)
        echo
        echo "Выполняется сборка в один файл..."
        echo
        
        # Очистить старые файлы
        rm -rf build dist
        
        # Сборка
        pyinstaller --onefile \
            --name mcp-bridge-server \
            --add-data "README.md:." \
            --add-data "docs:docs" \
            --hidden-import mcp \
            --hidden-import mcp.client.stdio \
            --hidden-import mcp.client.sse \
            --hidden-import uvicorn.logging \
            --hidden-import uvicorn.loops.auto \
            --hidden-import uvicorn.protocols.http.auto \
            --exclude-module tkinter \
            --exclude-module matplotlib \
            utils/mcp_bridge.py
        
        echo
        echo "✓ Сборка завершена!"
        echo "Выходной файл: dist/mcp-bridge-server"
        
        # Добавить права на выполнение
        chmod +x dist/mcp-bridge-server
        
        # Сгенерировать информацию о версии
        VERSION="v1.0.0"
        PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')
        ARCH=$(uname -m)
        
        if [ "$ARCH" = "x86_64" ]; then
            ARCH="x64"
        elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
            ARCH="arm64"
        fi
        
        FINAL_NAME="mcp-bridge-server-${VERSION}-${PLATFORM}-${ARCH}"
        
        echo
        read -p "Переименовать в имя релизной версии? (y/n): " rename
        if [[ "$rename" == "y" || "$rename" == "Y" ]]; then
            mv dist/mcp-bridge-server "dist/${FINAL_NAME}"
            echo "✓ Переименовано в: ${FINAL_NAME}"
            
            # Сгенерировать контрольную сумму
            cd dist
            sha256sum "${FINAL_NAME}" > SHA256SUMS.txt
            echo "✓ Контрольная сумма SHA256 сгенерирована"
            cd ..
        fi
        ;;
        
    2)
        echo
        echo "Выполняется сборка в каталог..."
        echo
        
        # Очистить старые файлы
        rm -rf build dist
        
        # Сборка
        pyinstaller --onedir \
            --name mcp-bridge-server \
            --add-data "README.md:." \
            --add-data "docs:docs" \
            --hidden-import mcp \
            --hidden-import mcp.client.stdio \
            --hidden-import mcp.client.sse \
            --hidden-import uvicorn.logging \
            --hidden-import uvicorn.loops.auto \
            --hidden-import uvicorn.protocols.http.auto \
            utils/mcp_bridge.py
        
        echo
        echo "✓ Сборка завершена!"
        echo "Выходной каталог: dist/mcp-bridge-server/"
        
        chmod +x dist/mcp-bridge-server/mcp-bridge-server
        ;;
        
    3)
        echo
        echo "Сборка с использованием spec-файла..."
        echo
        
        # Очистить старые файлы
        rm -rf build dist
        
        # Сборка
        pyinstaller mcp_bridge.spec
        
        echo
        echo "✓ Сборка завершена!"
        echo "Выходной файл: dist/mcp-bridge-server"
        
        chmod +x dist/mcp-bridge-server
        ;;
        
    4)
        echo
        echo "Очистка файлов сборки..."
        
        if [ -d "build" ]; then
            rm -rf build
            echo "✓ Каталог build удалён"
        fi
        
        if [ -d "dist" ]; then
            rm -rf dist
            echo "✓ Каталог dist удалён"
        fi
        
        if [ -f "mcp-bridge-server.spec" ] && [ ! -f "mcp_bridge.spec" ]; then
            rm -f mcp-bridge-server.spec
            echo "✓ Временный spec-файл удалён"
        fi
        
        echo
        echo "✓ Очистка завершена"
        ;;
        
    5)
        exit 0
        ;;
        
    *)
        echo
        echo "[Ошибка] Неверный вариант"
        exit 1
        ;;
esac

echo
echo "========================================"
echo

# Спросить, нужно ли тестирование
if [ -f "dist/mcp-bridge-server" ]; then
    read -p "Протестировать собранную программу? (y/n): " test
    if [[ "$test" == "y" || "$test" == "Y" ]]; then
        echo
        echo "Запуск программы..."
        echo "Нажмите Ctrl+C, чтобы остановить тест"
        echo
        ./dist/mcp-bridge-server --help
    fi
fi