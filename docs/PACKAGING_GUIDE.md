# Руководство по упаковке MCP Bridge Server

## Выбор инструмента упаковки

Рекомендуется использовать **PyInstaller** — он поддерживает упаковку Python-приложений в независимые исполняемые файлы.

## Подготовка окружения

```bash
# Установка PyInstaller
pip install pyinstaller

# Если нужно оптимизировать размер упаковки, установите UPX
# Windows: скачайте с https://github.com/upx/upx/releases
# Linux: sudo apt-get install upx
# Mac: brew install upx
```

## Файл конфигурации упаковки

Используйте предоставленный файл конфигурации `mcp_bridge.spec` для упаковки.

### Основные команды упаковки

```bash
# Упаковка в один файл (рекомендуется для распространения)
pyinstaller --onefile --name mcp-bridge-server utils/mcp_bridge.py

# Упаковка с использованием spec-файла (включает все оптимизации)
pyinstaller mcp_bridge.spec
```

### Расширенные параметры упаковки

```bash
# Windows — без окна консоли (не рекомендуется, так как нужны логи)
pyinstaller --onefile --noconsole --name mcp-bridge-server utils/mcp_bridge.py

# Windows — с иконкой
pyinstaller --onefile --icon=icon.ico --name mcp-bridge-server utils/mcp_bridge.py

# Сжатие исполняемого файла (требуется UPX)
pyinstaller --onefile --upx-dir=/path/to/upx --name mcp-bridge-server utils/mcp_bridge.py
```

## Упаковка для разных платформ

### Windows

```bash
# Упаковка на Windows
pyinstaller mcp_bridge.spec

# Выходной файл: dist/mcp-bridge-server.exe
```

Рекомендуемые имена файлов:
- `mcp-bridge-server-win-x64.exe` (64-бит)
- `mcp-bridge-server-win-x86.exe` (32-бит)

### Linux

```bash
# Упаковка на Linux
pyinstaller mcp_bridge.spec

# Выходной файл: dist/mcp-bridge-server
# Предоставить права на выполнение
chmod +x dist/mcp-bridge-server
```

Рекомендуемые имена файлов:
- `mcp-bridge-server-linux-x64`
- `mcp-bridge-server-linux-arm64`

### macOS

```bash
# Упаковка на macOS
pyinstaller mcp_bridge.spec

# Выходной файл: dist/mcp-bridge-server
chmod +x dist/mcp-bridge-server
```

Рекомендуемые имена файлов:
- `mcp-bridge-server-macos-x64`
- `mcp-bridge-server-macos-arm64` (Apple Silicon)

## Замечания по упаковке

### 1. Скрытые импорты

Некоторые библиотеки могут требовать явного объявления:

```python
# Добавьте в spec-файл
hiddenimports=[
    'mcp',
    'mcp.client.stdio',
    'mcp.client.sse',
    'fastapi',
    'uvicorn',
    'pydantic',
]
```

### 2. Файлы данных

Если есть дополнительные ресурсные файлы:

```python
# Добавьте в spec-файл
datas=[
    ('README.md', '.'),
    ('docs', 'docs'),
],
```

### 3. Исключение ненужных модулей

Для уменьшения размера файла:

```python
excludes=[
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'PIL',
    'PyQt5',
]
```

### 4. Проблема отсутствия консоли в Windows

**Не используйте `--noconsole`**, потому что:
- Пользователям нужно видеть журнал работы сервиса
- Обнаружение порта требует интерактивного ввода
- При отладке нужна информация об ошибках

Если действительно нужна версия без консоли, можно предоставить две версии:
- `mcp-bridge-server.exe` — версия с консолью (рекомендуется)
- `mcp-bridge-server-silent.exe` — версия без консоли (только для сервисного режима)

## Тестирование упакованной программы

### Базовое тестирование функциональности

```bash
# 1. Тест запуска по умолчанию
./dist/mcp-bridge-server

# 2. Тест параметра порта
./dist/mcp-bridge-server --port 8080

# 3. Тест справки
./dist/mcp-bridge-server --help

# 4. Тест автоматической обработки порта
./dist/mcp-bridge-server --auto-kill-port
```

### Полный контрольный список тестирования

- [ ] Программа нормально запускается
- [ ] Файл конфигурации автоматически создаётся в правильном месте
- [ ] Функция обнаружения порта работает корректно
- [ ] Можно загрузить MCP-сервисы
- [ ] API-интерфейсы отвечают корректно
- [ ] Функция перезапуска сервиса работает корректно
- [ ] Функция остановки сервиса работает корректно
- [ ] Ctrl+C корректно завершает работу
- [ ] Размер файла разумный (< 100 МБ)

## Оптимизация размера упаковки

### 1. Использование виртуального окружения

```bash
# Создайте чистое виртуальное окружение
python -m venv venv_build
source venv_build/bin/activate  # Linux/Mac
venv_build\Scripts\activate     # Windows

# Установите только необходимые зависимости
pip install -r requirements.txt
pip install pyinstaller

# Упаковка
pyinstaller mcp_bridge.spec
```

### 2. Использование сжатия UPX

```bash
# Автоматическое использование UPX (если установлен)
pyinstaller --upx-dir=/usr/bin mcp_bridge.spec
```

### 3. Исключение отладочной информации

```bash
pyinstaller --strip mcp_bridge.spec  # Linux/Mac
```

## Автоматическая упаковка CI/CD

### Пример GitHub Actions

Создайте `.github/workflows/build.yml`:

```yaml
name: Build Executables

on:
  push:
    tags:
      - 'v*'

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller
      - name: Build
        run: pyinstaller mcp_bridge.spec
      - name: Upload artifact
        uses: actions/upload-artifact@v2
        with:
          name: mcp-bridge-server-win-x64
          path: dist/mcp-bridge-server.exe

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller
      - name: Build
        run: pyinstaller mcp_bridge.spec
      - name: Upload artifact
        uses: actions/upload-artifact@v2
        with:
          name: mcp-bridge-server-linux-x64
          path: dist/mcp-bridge-server

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller
      - name: Build
        run: pyinstaller mcp_bridge.spec
      - name: Upload artifact
        uses: actions/upload-artifact@v2
        with:
          name: mcp-bridge-server-macos-x64
          path: dist/mcp-bridge-server
```

## Рекомендации по публикации

### 1. Именование версий

```
mcp-bridge-server-{version}-{platform}-{arch}.{ext}

Примеры:
- mcp-bridge-server-v1.0.0-win-x64.exe
- mcp-bridge-server-v1.0.0-linux-x64
- mcp-bridge-server-v1.0.0-macos-arm64
```

### 2. Содержимое публикации

Каждый Release должен содержать:
- Исполняемый файл Windows (.exe)
- Исполняемый файл Linux
- Исполняемый файл macOS
- Исходный код (автоматически)
- README.md
- CHANGELOG.md
- Ссылки на документацию

### 3. Проверка файлов

Для каждого файла сгенерируйте контрольную сумму SHA256:

```bash
# Windows
certutil -hashfile mcp-bridge-server.exe SHA256

# Linux/Mac
sha256sum mcp-bridge-server
```

Опубликуйте контрольные суммы в Release Notes.

## Часто задаваемые вопросы

### В: После упаковки файл слишком большой (>50 МБ)

**О**: Попробуйте следующие методы:
1. Используйте чистое виртуальное окружение
2. Исключите ненужные модули
3. Используйте сжатие UPX
4. Проверьте, не включены ли ненужные файлы данных

### В: После упаковки программа не запускается

**О**: Проверьте:
1. Включены ли все необходимые зависимости
2. Просмотрите предупреждения в `build/mcp-bridge-server/warn-*.txt`
3. Протестируйте на целевой системе
4. Проверьте, не остались ли необъявленные скрытые импорты

### В: Медленный запуск

**О**:
1. Режим одного файла работает медленнее (требуется распаковка)
2. Рассмотрите использование режима каталога (`--onedir`)
3. Первый запуск будет медленным, последующие — быстрее

### В: Ложное срабатывание антивируса

**О**:
1. Подпишите исполняемый файл сертификатом подписи кода
2. Отправьте образец производителям антивирусов
3. Укажите это в README

## Лучшие практики

1. **Минимизируйте зависимости** — устанавливайте только необходимые пакеты
2. **Тестируйте на нескольких системах** — проверяйте на чистых системах
3. **Предоставляйте контрольные суммы** — позволяйте пользователям проверять целостность файлов
4. **Сохраняйте исходный код** — всегда предоставляйте версию с исходным кодом
5. **完善 документацию** — подробные инструкции по установке и использованию
6. **Контроль версий** — используйте семантическое версионирование
7. **Автоматизируйте сборку** — используйте CI/CD

## Пример скрипта упаковки

Создайте `build.sh` (Linux/Mac) или `build.bat` (Windows):

```bash
#!/bin/bash
# build.sh

echo "=== Скрипт упаковки MCP Bridge Server ==="

# Очистка старых файлов
rm -rf build dist

# Упаковка
pyinstaller mcp_bridge.spec

# Переименование
VERSION="v1.0.0"
PLATFORM="linux-x64"
mv dist/mcp-bridge-server dist/mcp-bridge-server-${VERSION}-${PLATFORM}

# Генерация контрольной суммы
cd dist
sha256sum mcp-bridge-server-${VERSION}-${PLATFORM} > SHA256SUMS.txt

echo "=== Упаковка завершена ==="
echo "Выходной файл: dist/mcp-bridge-server-${VERSION}-${PLATFORM}"
```

Теперь вы можете легко упаковать проект в независимый исполняемый файл! 🚀
