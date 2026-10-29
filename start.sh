#!/bin/bash
# Скрипт запуска MCP Bridge Server (Linux/Mac)

echo "========================================"
echo "Средство запуска MCP Bridge Server"
echo "========================================"
echo

# Проверить, установлен ли Python
if ! command -v python3 &> /dev/null; then
    echo "[Ошибка] Python3 не найден. Сначала установите Python 3.8+"
    exit 1
fi

echo "Выберите режим запуска:"
echo
echo "  1. Запуск по умолчанию (интерактивный, порт 3849)"
echo "  2. Автоматически завершить процесс, занимающий порт (порт 3849)"
echo "  3. Запуск с пользовательским портом"
echo "  4. Просмотр справки"
echo "  5. Выход"
echo

read -p "Введите вариант (1-5): " choice

case $choice in
    1)
        echo
        echo "Запуск в интерактивном режиме..."
        python3 utils/mcp_bridge.py
        ;;
    2)
        echo
        echo "Запуск с автоматическим завершением процесса, занимающего порт..."
        python3 utils/mcp_bridge.py --auto-kill-port
        ;;
    3)
        echo
        read -p "Введите номер порта: " port
        read -p "Автоматически завершить процесс, занимающий порт? (y/n): " auto_kill
        
        if [[ "$auto_kill" == "y" || "$auto_kill" == "Y" ]]; then
            python3 utils/mcp_bridge.py --port $port --auto-kill-port
        else
            python3 utils/mcp_bridge.py --port $port
        fi
        ;;
    4)
        echo
        python3 utils/mcp_bridge.py --help
        echo
        read -p "Нажмите Enter для продолжения..."
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