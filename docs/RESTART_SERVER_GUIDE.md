# Руководство по использованию функции отдельного перезапуска сервиса

## Обзор функции

MCP Bridge Server теперь поддерживает отдельный перезапуск или остановку указанного MCP-сервиса без перезапуска всех сервисов. Это очень полезно в следующих случаях:

- 🔄 Возникла проблема с одним сервисом, и его нужно перезапустить.
- ➕ Добавлена конфигурация нового сервиса, которую нужно загрузить.
- 🔧 Изменена конфигурация одного сервиса, и её нужно применить.
- 🛑 Нужно временно отключить ненужный сервис.

## Новые конечные точки API

### 1. Перезапуск указанного сервиса

**Конечная точка**: `POST /restart-server`

**Тело запроса**:
```json
{
  "serverName": "имя_сервиса",
  "config": {  // необязательно, если указано — используется новая конфигурация
    "enabled": true,
    "command": "path/to/command",
    "args": ["arg1", "arg2"],
    "env": {},
    "description": "Описание сервиса"
  }
}
```

**Ответ**:
```json
{
  "success": true,
  "message": "Сервис xxx перезапущен",
  "toolCount": 10
}
```

**Пример**:
```bash
# Перезапуск с текущей конфигурацией
curl -X POST http://localhost:3849/restart-server \
  -H "Content-Type: application/json" \
  -d '{"serverName": "Knowledge Graph Memory Server"}'

# Перезапуск с новой конфигурацией
curl -X POST http://localhost:3849/restart-server \
  -H "Content-Type: application/json" \
  -d '{
    "serverName": "filesystem",
    "config": {
      "enabled": true,
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\NewPath"],
      "env": {}
    }
  }'
```

### 2. Остановка указанного сервиса

**Конечная точка**: `POST /shutdown-server`

**Тело запроса**:
```json
{
  "serverName": "имя_сервиса"
}
```

**Ответ**:
```json
{
  "success": true,
  "message": "Сервис xxx остановлен"
}
```

**Пример**:
```bash
curl -X POST http://localhost:3849/shutdown-server \
  -H "Content-Type: application/json" \
  -d '{"serverName": "12306-mcp"}'
```

## Сценарии использования

### Сценарий 1: Сервис работает неправильно и требует перезапуска

```python
import requests

# Перезапуск проблемного сервиса
response = requests.post(
    "http://localhost:3849/restart-server",
    json={"serverName": "Knowledge Graph Memory Server"}
)

if response.status_code == 200:
    print("Сервис успешно перезапущен")
```

### Сценарий 2: Перезагрузка одного сервиса после изменения конфигурации

```python
import requests

# Чтение текущей конфигурации
config_response = requests.get("http://localhost:3849/config")
config = config_response.json()["config"]

# Изменение конфигурации одного сервиса
config["mcpServers"]["filesystem"]["args"] = [
    "-y", 
    "@modelcontextprotocol/server-filesystem", 
    "D:\\NewDirectory"
]

# Перезапуск только этого сервиса
response = requests.post(
    "http://localhost:3849/restart-server",
    json={
        "serverName": "filesystem",
        "config": config["mcpServers"]["filesystem"]
    }
)
```

### Сценарий 3: Временное отключение ненужного сервиса

```python
import requests

# Отключение временно ненужного сервиса
response = requests.post(
    "http://localhost:3849/shutdown-server",
    json={"serverName": "hotnews-stdio"}
)
```

## Улучшения обработки ошибок

### Исправлена ошибка "Attempted to exit cancel scope"

Ранее при перезапуске сервиса можно было увидеть эту ошибку:
```
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

**Причина**: в асинхронной среде контекстный менеджер (context manager) должен входить и выходить в одной и той же задаче.

**Решение**:
- Использовать `asyncio.create_task()` для выполнения очистки в новой задаче.
- Добавить соответствующую задержку для гарантии корректного освобождения ресурсов.
- Улучшить перехват ошибок, чтобы даже при неудачной очистке клиент корректно удалялся.

## Тестовый скрипт Python

Используйте предоставленный тестовый скрипт `test_restart_server.py`:

```bash
# Убедитесь, что сервер запущен
python utils/mcp_bridge.py

# В другом терминале запустите тест
python test_restart_server.py
```

## Использование в JavaScript/браузере

```javascript
// Перезапуск сервиса
async function restartServer(serverName) {
  const response = await fetch('http://localhost:3849/restart-server', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ serverName })
  });
  
  const result = await response.json();
  console.log(result.message);
  return result;
}

// Использование
await restartServer('Knowledge Graph Memory Server');
```

## Примечания

1. **Имя сервиса должно быть точным**: используйте `GET /tools` для просмотра точных имён всех сервисов.
2. **Перезапуск прерывает соединения**: вызовы инструментов, использующие этот сервис, завершатся ошибкой.
3. **Кэш конфигурации**: если параметр config не указан, используется последняя загруженная конфигурация.
4. **Очистка ресурсов**: операция остановки выполняется асинхронно в фоновом режиме, обеспечивая корректное освобождение ресурсов.

## Отличие от глобальной перезагрузки

| Функция | Отдельный перезапуск | Глобальная перезагрузка (/reload) |
|---------|----------------------|-----------------------------------|
| Область влияния | Только указанный сервис | Все сервисы |
| Влияние на производительность | Минимальное | Значительное |
| Подходящий сценарий | Проблема с одним сервисом | Полное обновление файла конфигурации |
| Остальные сервисы | Продолжают работать | Все перезапускаются |

## Часто задаваемые вопросы

**В: Как узнать, какие сервисы работают?**  
О: Используйте конечную точку `GET /tools`, чтобы получить список всех сервисов.

**В: Повлияет ли перезапуск сервиса на другие сервисы?**  
О: Нет, перезапускается только указанный сервис, остальные продолжают нормально работать.

**В: Что делать, если перезапуск не удался?**  
О: Сервис будет удалён из списка; можно повторно загрузить все сервисы через `/reload`.

**В: Можно ли перезапустить несуществующий сервис?**  
О: Если имя сервиса есть в конфигурации, но он не запущен, будет предпринята попытка запуска; если его нет и в конфигурации, вернётся ошибка 404.
