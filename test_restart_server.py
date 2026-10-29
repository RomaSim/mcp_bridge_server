#!/usr/bin/env python3
"""
Тестирование функции отдельного перезапуска сервиса
"""

import requests
import json

BASE_URL = "http://localhost:3849"

def test_restart_server():
    """Тестирование перезапуска отдельного сервиса"""
    
    print("=== Тестирование функции отдельного перезапуска сервиса ===\n")
    
    # 1. Получить все текущие сервисы
    print("1. Получение всех текущих сервисов...")
    response = requests.get(f"{BASE_URL}/tools")
    if response.status_code == 200:
        services = response.json().get("services", [])
        print(f"   В настоящее время {len(services)} сервисов:")
        for service in services:
            print(f"   - {service['name']}: {service['description']}")
    else:
        print(f"   Не удалось получить список сервисов: {response.status_code}")
        return
    
    if not services:
        print("   Нет доступных сервисов")
        return
    
    # 2. Выбрать первый сервис для тестирования перезапуска
    target_server = services[0]['name']
    print(f"\n2. Перезапуск сервиса: {target_server}")
    
    response = requests.post(
        f"{BASE_URL}/restart-server",
        json={"serverName": target_server}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✓ {result['message']}")
        print(f"   ✓ Количество инструментов: {result.get('toolCount', 0)}")
    else:
        print(f"   ✗ Ошибка перезапуска: {response.status_code}")
        print(f"   Ошибка: {response.text}")
        return
    
    # 3. Проверить, работает ли сервис нормально
    print(f"\n3. Проверка работоспособности сервиса...")
    response = requests.get(f"{BASE_URL}/tools?serverName={target_server}")
    if response.status_code == 200:
        tools = response.json().get("tools", [])
        print(f"   ✓ Сервис работает нормально, инструментов: {len(tools)}")
    else:
        print(f"   ✗ Ошибка сервиса: {response.status_code}")


def test_shutdown_server():
    """Тестирование закрытия отдельного сервиса"""
    
    print("\n\n=== Тестирование функции закрытия отдельного сервиса ===\n")
    
    # 1. Получить все текущие сервисы
    print("1. Получение всех текущих сервисов...")
    response = requests.get(f"{BASE_URL}/tools")
    if response.status_code == 200:
        services = response.json().get("services", [])
        print(f"   В настоящее время {len(services)} сервисов")
    else:
        print(f"   Не удалось получить список сервисов: {response.status_code}")
        return
    
    if len(services) < 2:
        print("   Недостаточно сервисов, тест закрытия пропущен")
        return
    
    # 2. Закрыть второй сервис
    target_server = services[1]['name']
    print(f"\n2. Закрытие сервиса: {target_server}")
    
    response = requests.post(
        f"{BASE_URL}/shutdown-server",
        json={"serverName": target_server}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✓ {result['message']}")
    else:
        print(f"   ✗ Ошибка закрытия: {response.status_code}")
        print(f"   Ошибка: {response.text}")
        return
    
    # 3. Проверить, что сервис закрыт
    print(f"\n3. Проверка списка сервисов...")
    response = requests.get(f"{BASE_URL}/tools")
    if response.status_code == 200:
        services_after = response.json().get("services", [])
        print(f"   В настоящее время {len(services_after)} сервисов (было: {len(services)})")
        if len(services_after) == len(services) - 1:
            print(f"   ✓ Сервис {target_server} успешно закрыт")
        else:
            print(f"   ⚠ Количество сервисов не соответствует ожидаемому")


if __name__ == "__main__":
    try:
        # Сначала тестировать перезапуск
        test_restart_server()
        
        # Затем тестировать закрытие
        # test_shutdown_server()  # Если хотите протестировать закрытие, раскомментируйте
        
        print("\n\nТестирование завершено!")
        
    except requests.exceptions.ConnectionError:
        print("Ошибка: не удалось подключиться к серверу. Убедитесь, что MCP Bridge Server запущен")
    except Exception as e:
        print(f"Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()