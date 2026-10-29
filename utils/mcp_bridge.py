#!/usr/bin/env python3
"""
MCP Bridge Server — версия на Python
Предоставляет HTTP-интерфейс для управления MCP-серверами и их вызова.
"""

import asyncio
import json
import os
import signal
import sys
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import asynccontextmanager
import uuid
import threading
import time
import json
from collections import OrderedDict

# Попытка импортировать информацию о версии
try:
    # Если это упакованное приложение — используем относительный импорт
    if getattr(sys, 'frozen', False):
        __version__ = "1.0.0"
    else:
        # Среда разработки — импорт из version.py
        parent_dir = Path(__file__).parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        from version import __version__
except ImportError:
    __version__ = "1.0.0"

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Импорт MCP SDK
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

PORT = 3849


def is_port_in_use(port: int) -> bool:
    """Проверить, занят ли порт"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except OSError:
            return True


def get_process_using_port(port: int) -> Optional[Dict[str, Any]]:
    """Получить информацию о процессе, занимающем порт"""
    try:
        if sys.platform == "win32":
            # В Windows используем netstat
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                encoding='gbk',
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            for line in result.stdout.split('\n'):
                if f':{port} ' in line or f':{port}\t' in line:
                    parts = line.split()
                    if len(parts) >= 5 and parts[1].endswith(f':{port}'):
                        pid = parts[-1]
                        # Получить имя процесса
                        try:
                            tasklist_result = subprocess.run(
                                ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                                capture_output=True,
                                text=True,
                                encoding='gbk',
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                            )
                            process_name = tasklist_result.stdout.split()[0] if tasklist_result.stdout else "Unknown"
                            return {"pid": pid, "name": process_name}
                        except:
                            return {"pid": pid, "name": "Unknown"}
        else:
            # В Linux/Mac используем lsof
            result = subprocess.run(
                ['lsof', '-i', f':{port}', '-t'],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                pid = result.stdout.strip().split('\n')[0]
                # Получить имя процесса
                try:
                    name_result = subprocess.run(
                        ['ps', '-p', pid, '-o', 'comm='],
                        capture_output=True,
                        text=True
                    )
                    process_name = name_result.stdout.strip()
                    return {"pid": pid, "name": process_name}
                except:
                    return {"pid": pid, "name": "Unknown"}
    except Exception as e:
        print(f"Не удалось получить информацию о процессе: {e}")
    
    return None


def kill_process_by_pid(pid: str) -> bool:
    """Завершить процесс по PID"""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ['taskkill', '/F', '/PID', pid], 
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        else:
            subprocess.run(['kill', '-9', pid], check=True)
        return True
    except Exception as e:
        print(f"Не удалось завершить процесс: {e}")
        return False


def check_and_handle_port(port: int, auto_kill: bool = False) -> bool:
    """
    Проверить и обработать занятость порта
    
    Аргументы:
        port: Порт для проверки
        auto_kill: Автоматически завершать процесс, занимающий порт (через переменную окружения или аргумент командной строки)
    
    Возвращает:
        True — если порт доступен, False — если порт занят и пользователь отказался завершать процесс
    """
    if not is_port_in_use(port):
        return True
    
    print(f"\n⚠️  Порт {port} уже занят")
    
    # Получить информацию о занимающем процессе
    process_info = get_process_using_port(port)
    if process_info:
        print(f"   Занимающий процесс: {process_info['name']} (PID: {process_info['pid']})")
    
    # Проверить переменную окружения
    if auto_kill or os.environ.get('MCP_AUTO_KILL_PORT', '').lower() in ['true', '1', 'yes']:
        print(f"   Автоматическое завершение занимающего процесса...")
        if process_info and kill_process_by_pid(process_info['pid']):
            print(f"   ✓ Процесс завершён")
            # Подождать освобождения порта
            import time
            time.sleep(1)
            if not is_port_in_use(port):
                print(f"   ✓ Порт {port} освобождён")
                return True
            else:
                print(f"   ✗ Порт {port} всё ещё занят")
                return False
        else:
            print(f"   ✗ Не удалось завершить процесс")
            return False
    
    # Интерактивный запрос
    try:
        print(f"\nВыберите действие:")
        print(f"  1. Завершить занимающий процесс и продолжить")
        print(f"  2. Использовать другой порт")
        print(f"  3. Выйти из программы")
        
        choice = input("\nВведите вариант (1/2/3): ").strip()
        
        if choice == '1':
            if process_info and kill_process_by_pid(process_info['pid']):
                print(f"✓ Процесс завершён")
                # Подождать освобождения порта
                import time
                time.sleep(1)
                if not is_port_in_use(port):
                    print(f"✓ Порт {port} освобождён")
                    return True
                else:
                    print(f"✗ Порт {port} всё ещё занят, освободите порт вручную")
                    return False
            else:
                print(f"✗ Не удалось завершить процесс")
                return False
        
        elif choice == '2':
            new_port = input(f"Введите новый номер порта (текущий: {port}): ").strip()
            try:
                new_port_num = int(new_port)
                if 1 <= new_port_num <= 65535:
                    global PORT
                    PORT = new_port_num
                    print(f"✓ Переключено на порт {PORT}")
                    return check_and_handle_port(PORT, auto_kill)
                else:
                    print(f"✗ Номер порта должен быть в диапазоне 1–65535")
                    return False
            except ValueError:
                print(f"✗ Некорректный номер порта")
                return False
        
        else:
            print("Выход из программы")
            return False
    
    except (KeyboardInterrupt, EOFError):
        print("\n\nОтменено")
        return False


def get_config_path() -> Path:
    """Получить путь к файлу конфигурации"""
    system = sys.platform
    
    if system == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            appdata = str(Path.home() / "AppData" / "Roaming")
        config_dir = Path(appdata) / "mcp-bridge" / "config"
    elif system == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "mcp-bridge" / "config"
    elif system.startswith("linux"):
        config_dir = Path.home() / ".config" / "mcp-bridge" / "config"
    else:
        config_dir = Path.home() / ".mcp-bridge" / "config"
    
    # Создать каталог
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        print(f"Каталог конфигурации: {config_dir}")
    except Exception as e:
        print(f"Не удалось создать каталог конфигурации: {config_dir}, ошибка: {e}")
    
    return config_dir / "mcp-config.json"


class MCPServerConfig(BaseModel):
    """Конфигурация MCP-сервера"""
    enabled: bool = True
    disabled: bool = False
    type: str = "stdio"  # "stdio" или "sse"
    # Конфигурация типа stdio
    command: Optional[str] = None
    args: List[str] = []
    env: Dict[str, str] = {}
    # Конфигурация типа sse
    url: Optional[str] = None
    # Общая конфигурация
    timeout: int = 30
    description: str = ""
    # Конфигурация кэша
    max_output_bytes: int = 1000  # Порог размера вывода в байтах для срабатывания кэша
    output_truncate_strategy: str = "tail"  # Стратегия обрезки: "tail", "head", "middle"
    cache_large_results: bool = True  # Включить кэширование больших результатов
    result_cache_ttl: int = 300  # Время жизни кэша (секунды)
    max_memory_cache_size: int = 10240  # Порог памяти для кэша (байты); при превышении используется файловый кэш


class Config(BaseModel):
    """Структура файла конфигурации"""
    mcpServers: Dict[str, MCPServerConfig]


class ExecuteRequest(BaseModel):
    """Запрос на выполнение инструмента"""
    name: str
    arguments: Dict[str, Any] = {}
    serverName: Optional[str] = None  # Необязательное имя сервиса для указания конкретного сервиса


class ConfigUpdateRequest(BaseModel):
    """Запрос на обновление конфигурации"""
    config: Dict[str, Any]


class ServerRestartRequest(BaseModel):
    """Запрос на перезапуск сервера"""
    serverName: str
    config: Optional[Dict[str, Any]] = None  # Необязательная новая конфигурация


class GetResultRequest(BaseModel):
    """Запрос на получение кэшированного результата"""
    cache_id: str
    start: Optional[int] = 0
    end: Optional[int] = None


class SearchCacheRequest(BaseModel):
    """Запрос на поиск в кэше"""
    cache_id: str
    keyword: str
    case_sensitive: Optional[bool] = False
    max_results: Optional[int] = 50


class GetCacheContextRequest(BaseModel):
    """Запрос на получение контекста из кэша"""
    cache_id: str
    line_num: int
    context_lines: Optional[int] = 3


class MCPManager:
    """Менеджер MCP-сервисов"""
    
    def __init__(self):
        self.clients: Dict[str, Dict[str, Any]] = {}
        self.tool_call_history: Dict[str, int] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.config_cache: Dict[str, Any] = {}  # Кэш конфигурации для перезапуска отдельного сервиса
        
        # Связано с системой кэширования
        self.memory_cache: OrderedDict = OrderedDict()  # Кэш в памяти
        self.cache_lock = threading.RLock()  # Блокировка доступа к кэшу
        self.max_memory_cache_items = 100  # Максимальное число элементов в кэше памяти
    
    async def load_config(self, config_path: Path) -> Dict[str, Any]:
        """Загрузить файл конфигурации"""
        try:
            if not config_path.exists():
                print(f"Файл конфигурации не существует, создаём конфигурацию по умолчанию: {config_path}")
                
                default_config = {
                    "mcpServers": {
                        "example_service": {
                            "enabled": True,
                            "command": "path/to/your/mcp/server/executable",
                            "args": ["--port", "8080"],
                            "description": "Это пример сервиса, замените его на свою конфигурацию. Он умеет...",
                            "env": {}
                        }
                    }
                }
                
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                
                print(f"✓ Конфигурация по умолчанию создана: {config_path}")
                self.config_cache = default_config  # Кэшировать конфигурацию
                return default_config
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.config_cache = config  # Кэшировать конфигурацию
                return config
        
        except Exception as e:
            print(f"Не удалось прочитать конфигурацию: {e}")
            return {"mcpServers": {}}
    
    async def init_server(self, server_name: str, server_config: Dict[str, Any]):
        """Инициализировать отдельный MCP-сервер"""
        if server_name in self.clients:
            print(f"Сервер {server_name} уже инициализирован")
            return
        
        server_type = server_config.get("type", "stdio").lower()
        timeout = server_config.get("timeout", 30)
        
        try:
            print(f"Инициализация сервера {server_name} (тип: {server_type})...")
            
            if server_type == "sse":
                # Сервер типа SSE
                await self._init_sse_server(server_name, server_config, timeout)
            else:
                # Сервер типа stdio
                await self._init_stdio_server(server_name, server_config, timeout)
            
            print(f"✓ Сервер {server_name} успешно инициализирован, загружено инструментов: {len(self.clients[server_name]['tools'])}")
        
        except asyncio.TimeoutError:
            print(f"✗ Превышено время инициализации сервера {server_name} ({timeout} с)")
            raise
        except Exception as e:
            print(f"✗ Не удалось инициализировать сервер {server_name}: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _init_stdio_server(self, server_name: str, server_config: Dict[str, Any], timeout: int):
        """Инициализировать сервер типа stdio"""
        command = server_config.get("command")
        if not command:
            raise ValueError(f"Сервер типа stdio должен указывать поле command")
        
        args = server_config.get("args", [])
        env = server_config.get("env", {})
        
        # Объединить переменные окружения
        server_env = {**os.environ, **env}
        
        print(f"  Команда выполнения: {command} {' '.join(args)}")
        
        # Создать параметры сервера
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=server_env
        )
        
        print(f"  Запуск дочернего процесса...")
        
        # Подключиться к серверу через асинхронный контекстный менеджер
        stdio_context = stdio_client(server_params)
        read, write = await asyncio.wait_for(
            stdio_context.__aenter__(),
            timeout=timeout
        )
        print(f"  Дочерний процесс запущен, установка сессии...")
        
        # Создать контекстный менеджер сессии
        session_context = ClientSession(read, write)
        session = await asyncio.wait_for(
            session_context.__aenter__(),
            timeout=timeout
        )
        print(f"  Сессия установлена, инициализация...")
        
        try:
            # Инициализировать сессию
            await asyncio.wait_for(
                session.initialize(),
                timeout=timeout
            )
            print(f"  Сессия инициализирована")
        except asyncio.TimeoutError:
            print(f"  ✗ Превышено время инициализации сессии")
            await session_context.__aexit__(None, None, None)
            await stdio_context.__aexit__(None, None, None)
            raise
        
        # Получить список инструментов
        try:
            print(f"  Получение списка инструментов...")
            tools_response = await asyncio.wait_for(
                session.list_tools(),
                timeout=timeout
            )
            tools = tools_response.tools if hasattr(tools_response, 'tools') else []
            print(f"  Успешно получено инструментов: {len(tools)}")
        except asyncio.TimeoutError:
            print(f"  ✗ Превышено время получения списка инструментов")
            await session_context.__aexit__(None, None, None)
            await stdio_context.__aexit__(None, None, None)
            raise
        
        self.clients[server_name] = {
            "type": "stdio",
            "session": session,
            "session_context": session_context,
            "tools": tools,
            "config": server_config,
            "stdio_context": stdio_context,
            "read": read,
            "write": write
        }
    
    async def _init_sse_server(self, server_name: str, server_config: Dict[str, Any], timeout: int):
        """Инициализировать сервер типа SSE"""
        url = server_config.get("url")
        if not url:
            raise ValueError(f"Сервер типа sse должен указывать поле url")
        
        print(f"  Подключение к SSE-серверу: {url}")
        
        sse_context = None
        read = None
        write = None
        session_context = None
        
        try:
            # Подключиться к SSE-серверу через асинхронный контекстный менеджер
            sse_context = sse_client(url)
            
            # Установить SSE-соединение
            try:
                read, write = await asyncio.wait_for(
                    sse_context.__aenter__(),
                    timeout=timeout
                )
                print(f"  SSE-соединение установлено")
            except asyncio.TimeoutError:
                print(f"  ✗ Превышено время подключения к SSE-серверу ({timeout} с)")
                print(f"  Подсказка: проверьте корректность URL или увеличьте значение timeout")
                raise
            except Exception as e:
                print(f"  ✗ Не удалось подключиться к SSE-серверу: {e}")
                print(f"  Подсказка: убедитесь, что формат URL корректен и сервер доступен")
                raise
            
            # Создать контекстный менеджер сессии
            session_context = ClientSession(read, write)
            session = await asyncio.wait_for(
                session_context.__aenter__(),
                timeout=timeout
            )
            print(f"  Сессия установлена, инициализация...")
            
            # Инициализировать сессию
            try:
                await asyncio.wait_for(
                    session.initialize(),
                    timeout=timeout
                )
                print(f"  Сессия инициализирована")
            except asyncio.TimeoutError:
                print(f"  ✗ Превышено время инициализации сессии")
                raise
            
            # Получить список инструментов
            try:
                print(f"  Получение списка инструментов...")
                tools_response = await asyncio.wait_for(
                    session.list_tools(),
                    timeout=timeout
                )
                tools = tools_response.tools if hasattr(tools_response, 'tools') else []
                print(f"  Успешно получено инструментов: {len(tools)}")
            except asyncio.TimeoutError:
                print(f"  ✗ Превышено время получения списка инструментов")
                raise
            
            self.clients[server_name] = {
                "type": "sse",
                "session": session,
                "session_context": session_context,
                "tools": tools,
                "config": server_config,
                "sse_context": sse_context,
                "read": read,
                "write": write
            }
            
        except Exception:
            # Очистить ресурсы
            if session_context and read is not None:
                print(f"  Очистка сессии...")
                try:
                    await session_context.__aexit__(*sys.exc_info())
                except Exception:
                    pass
            
            if sse_context and read is not None:
                print(f"  Очистка SSE-соединения...")
                try:
                    await sse_context.__aexit__(*sys.exc_info())
                except Exception:
                    pass
            raise
    
    async def init_all_servers(self, config: Dict[str, Any]):
        """Инициализировать все серверы"""
        servers = config.get("mcpServers", {})
        
        tasks = []
        for name, cfg in servers.items():
            # Проверить флаг enabled
            if cfg.get("enabled", True) is False:
                print(f"ℹ️  Сервис {name} отключён, пропускаем загрузку.")
                continue
            
            # Создать задачу инициализации
            task = self._init_server_with_error_handling(name, cfg)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _init_server_with_error_handling(self, name: str, cfg: Dict[str, Any]):
        """Инициализация сервера с обработкой ошибок"""
        try:
            await self.init_server(name, cfg)
        except Exception as e:
            print(f"Пропускаем сервер {name}: {e}")
    
    def get_services(self) -> List[Dict[str, str]]:
        """Получить список всех сервисов"""
        services = []
        for server_name, client_data in self.clients.items():
            config = client_data["config"]
            services.append({
                "name": server_name,
                "description": config.get("description", f"Сервис инструментов с именем {server_name}."),
                "is_core": config.get("is_core", False)  # Читать флаг is_core из конфигурации, по умолчанию False
            })
        return services
    
    def get_tools_by_server(self, server_name: str) -> Dict[str, Any]:
        """Получить список инструментов указанного сервера (включая описание сервиса)"""
        if server_name not in self.clients:
            raise ValueError(f"Сервис {server_name} не существует или не был успешно загружен")
        
        client_data = self.clients[server_name]
        config = client_data["config"]
        tools = client_data["tools"]
        
        return {
            "service_name": server_name,
            "service_description": config.get("description", f"Сервис инструментов с именем {server_name}."),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                }
                for tool in tools
            ]
        }
    
    def get_tool_detail(self, tool_name: str, server_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Получить подробную информацию об инструменте
        
        Аргументы:
            tool_name: Имя инструмента
            server_name: Необязательное имя сервиса
        
        Возвращает:
            Подробная информация об инструменте, включая полное определение параметров
        """
        target_server = None
        target_tool = None
        
        if server_name:
            if server_name not in self.clients:
                raise ValueError(f"Сервис {server_name} не существует или не загружен")
            
            tools = self.clients[server_name]["tools"]
            for tool in tools:
                if tool.name == tool_name:
                    target_server = server_name
                    target_tool = tool
                    break
            
            if not target_tool:
                raise ValueError(f"В сервисе {server_name} не существует инструмента {tool_name}")
        else:
            # Искать во всех сервисах
            for srv_name, client_data in self.clients.items():
                tools = client_data["tools"]
                for tool in tools:
                    if tool.name == tool_name:
                        target_server = srv_name
                        target_tool = tool
                        break
                if target_tool:
                    break
            
            if not target_tool:
                raise ValueError(f"Инструмент {tool_name} не существует")
        
        # Извлечь полную информацию об инструменте
        return {
            "name": target_tool.name,
            "description": target_tool.description,
            "serverName": target_server,
            "inputSchema": target_tool.inputSchema if hasattr(target_tool, 'inputSchema') else {},
            "parameters": target_tool.inputSchema if hasattr(target_tool, 'inputSchema') else {}
        }
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any], server_name: Optional[str] = None) -> Any:
        """
        Выполнить инструмент
        
        Аргументы:
            tool_name: Имя инструмента
            args: Параметры инструмента
            server_name: Необязательное имя сервиса, указывающее, из какого сервиса вызывать инструмент
        
        Возвращает:
            Результат выполнения инструмента
        
        Исключения:
            ValueError: Если инструмент не существует, сервис не существует или достигнут лимит вызовов
        """
        target_server = None
        target_session = None
        
        # Очистить параметры: удалить ключи со значением None, так как некоторые MCP-сервисы не поддерживают null
        cleaned_args = {k: v for k, v in args.items() if v is not None}
        
        # Если указано имя сервиса — искать только в нём
        if server_name:
            if server_name not in self.clients:
                raise ValueError(f"Сервис {server_name} не существует или не загружен")
            
            client_data = self.clients[server_name]
            tools = client_data["tools"]
            
            # Искать инструмент в указанном сервисе
            tool_found = False
            for tool in tools:
                if tool.name == tool_name:
                    tool_found = True
                    target_server = server_name
                    target_session = client_data["session"]
                    break
            
            if not tool_found:
                raise ValueError(f"В сервисе {server_name} не существует инструмента {tool_name}")
        
        else:
            # Имя сервиса не указано — искать во всех сервисах (обратная совместимость)
            matching_servers = []
            
            for srv_name, client_data in self.clients.items():
                tools = client_data["tools"]
                for tool in tools:
                    if tool.name == tool_name:
                        matching_servers.append(srv_name)
                        if not target_server:  # Запомнить первый совпавший сервис
                            target_server = srv_name
                            target_session = client_data["session"]
                        break
            
            if not target_server:
                raise ValueError(f"Инструмент {tool_name} не существует")
            
            # Если несколько сервисов предоставляют одноимённый инструмент — предупредить
            if len(matching_servers) > 1:
                print(f"⚠️  Предупреждение: инструмент {tool_name} существует в нескольких сервисах: {', '.join(matching_servers)}")
                print(f"   Будет использован сервис {target_server}; рекомендуется указывать параметр serverName во избежание неоднозначности")
        
        # Проверить количество вызовов
        call_key = f"{target_server}:{tool_name}"
        call_count = self.tool_call_history.get(call_key, 0)
        
        if call_count >= 3:
            raise ValueError(f"Инструмент {tool_name} (сервис: {target_server}) достиг максимального числа вызовов (3 раза)")
        
        try:
            # Вывести отладочную информацию
            print(f"[Выполнение инструмента] Сервис: {target_server}, Инструмент: {tool_name}")
            print(f"[Исходные параметры] {args}")
            print(f"[Очищенные параметры] {cleaned_args}")
            
            # Вызвать инструмент
            result = await target_session.call_tool(tool_name, cleaned_args)
            
            # Получить конфигурацию сервиса
            server_config = self.clients[target_server]["config"]
            
            # Преобразовать MCP-результат в сериализуемый формат
            if hasattr(result, 'model_dump'):
                # Использовать метод model_dump (если доступен)
                serializable_result = result.model_dump()
            elif hasattr(result, '__dict__'):
                # Попробовать преобразовать объект в словарь
                import copy
                try:
                    serializable_result = copy.deepcopy(result.__dict__)
                except Exception:
                    # Если deepcopy не удался, попробовать ручное преобразование
                    serializable_result = {}
                    for attr_name in dir(result):
                        if not attr_name.startswith('_'):
                            attr_value = getattr(result, attr_name)
                            if isinstance(attr_value, (str, int, float, bool, list, dict, type(None))):
                                serializable_result[attr_name] = attr_value
                            else:
                                # Попробовать преобразовать в строковое представление
                                try:
                                    serializable_result[attr_name] = str(attr_value)
                                except:
                                    serializable_result[attr_name] = f"<unserializable: {type(attr_value).__name__}>"
            else:
                # Если преобразовать нельзя, использовать результат напрямую
                serializable_result = result
            
            # Обработать результат через систему кэширования
            cached_result = self.cache_result(serializable_result, server_config)
            
            # Сбросить счётчик вызовов
            self.tool_call_history[call_key] = 0
            
            return cached_result
        
        except Exception as e:
            # Увеличить счётчик вызовов
            self.tool_call_history[call_key] = call_count + 1
            
            # Вывести подробную информацию об ошибке
            print(f"[Ошибка выполнения инструмента] Сервис: {target_server}, Инструмент: {tool_name}")
            print(f"[Тип ошибки] {type(e).__name__}")
            print(f"[Сообщение об ошибке] {str(e)}")
            raise
    
    def reset_tool_call_history(self):
        """Сбросить историю вызовов инструментов"""
        self.tool_call_history.clear()
    
    async def shutdown(self):
        """Закрыть все соединения с серверами"""
        for name in list(self.clients.keys()):
            await self.shutdown_server(name)
    
    async def shutdown_server(self, server_name: str):
        """Закрыть соединение с указанным сервером"""
        if server_name not in self.clients:
            print(f"Сервер {server_name} не существует, закрывать нечего")
            return
        
        client_data = self.clients[server_name]
        
        try:
            # Создать новую задачу для закрытия, чтобы избежать ошибок cancel scope
            async def cleanup():
                try:
                    # Сначала закрыть контекст сессии
                    session_context = client_data.get("session_context")
                    if session_context:
                        try:
                            await session_context.__aexit__(None, None, None)
                        except Exception as e:
                            print(f"  Ошибка при закрытии контекста сессии: {e}")
                    
                    # В зависимости от типа закрыть соответствующий транспортный уровень
                    server_type = client_data.get("type", "stdio")
                    if server_type == "sse":
                        sse_context = client_data.get("sse_context")
                        if sse_context:
                            try:
                                await sse_context.__aexit__(None, None, None)
                            except Exception as e:
                                print(f"  Ошибка при закрытии SSE-соединения: {e}")
                    else:
                        stdio_context = client_data.get("stdio_context")
                        if stdio_context:
                            try:
                                await stdio_context.__aexit__(None, None, None)
                            except Exception as e:
                                print(f"  Ошибка при закрытии stdio-соединения: {e}")
                except Exception as e:
                    print(f"  Ошибка при очистке ресурсов: {e}")
            
            # Использовать asyncio.create_task для выполнения очистки в новой задаче,
            # но не ждать её завершения — пусть работает в фоне
            asyncio.create_task(cleanup())
            
            # Дать немного времени, чтобы очистка началась
            await asyncio.sleep(0.1)
            
            print(f"Сервер закрыт: {server_name}")
        except Exception as e:
            print(f"Не удалось закрыть сервер {server_name}: {e}")
        finally:
            # В любом случае удалить из словаря
            self.clients.pop(server_name, None)
    
    def _get_cache_directory(self) -> Path:
        """Получить путь к каталогу кэша"""
        # Определить каталог кэша в зависимости от ОС
        if sys.platform == "win32":
            cache_dir = Path(os.environ.get("APPDATA", "")) / "mcp-bridge" / "cache"
        elif sys.platform == "darwin":
            cache_dir = Path.home() / "Library" / "Application Support" / "mcp-bridge" / "cache"
        else:  # Linux и прочие
            cache_dir = Path.home() / ".cache" / "mcp-bridge"
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
    
    def _store_in_file_cache(self, content: Any, ttl: int) -> str:
        """Сохранить содержимое в файловый кэш и вернуть ID"""
        cache_id = str(uuid.uuid4())
        cache_file = self._get_cache_directory() / f"{cache_id}.txt"
        
        # Сериализовать содержимое
        if isinstance(content, str):
            content_str = content
        else:
            content_str = json.dumps(content, ensure_ascii=False, indent=2)
        
        # Записать в файл
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(content_str)
        
        # Создать файл метаданных
        metadata_file = self._get_cache_directory() / f"{cache_id}.meta"
        metadata = {
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
            "size": len(content_str.encode('utf-8'))
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f)
        
        return cache_id
    
    def _get_from_file_cache(self, cache_id: str) -> Optional[Any]:
        """Получить содержимое из файлового кэша"""
        cache_file = self._get_cache_directory() / f"{cache_id}.txt"
        metadata_file = self._get_cache_directory() / f"{cache_id}.meta"
        
        # Проверить существование файлов
        if not cache_file.exists() or not metadata_file.exists():
            return None
        
        # Проверить срок годности
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            if time.time() > metadata.get("expires_at", 0):
                # Просрочено — удалить файлы
                cache_file.unlink(missing_ok=True)
                metadata_file.unlink(missing_ok=True)
                return None
        except:
            return None
        
        # Прочитать содержимое
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Попробовать распарсить JSON; если не JSON — вернуть исходную строку
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
        except:
            return None
    
    def _store_in_memory_cache(self, content: Any, ttl: int) -> str:
        """Сохранить содержимое в кэш памяти и вернуть ID"""
        cache_id = str(uuid.uuid4())
        
        with self.cache_lock:
            # Очистить просроченные элементы
            current_time = time.time()
            expired_keys = []
            for key, (_, expire_time) in list(self.memory_cache.items()):
                if current_time > expire_time:
                    expired_keys.append(key)
            for key in expired_keys:
                self.memory_cache.pop(key, None)
            
            # Если достигнут максимум — удалить самые старые
            while len(self.memory_cache) >= self.max_memory_cache_items:
                oldest_key = next(iter(self.memory_cache))
                self.memory_cache.pop(oldest_key, None)
            
            # Сохранить новый элемент
            self.memory_cache[cache_id] = (content, current_time + ttl)
        
        return cache_id
    
    def _get_from_memory_cache(self, cache_id: str) -> Optional[Any]:
        """Получить содержимое из кэша памяти"""
        with self.cache_lock:
            if cache_id not in self.memory_cache:
                return None
            
            content, expire_time = self.memory_cache[cache_id]
            current_time = time.time()
            
            if current_time > expire_time:
                # Просрочено — удалить элемент
                self.memory_cache.pop(cache_id, None)
                return None
            
            # Переместить в конец (стратегия LRU)
            self.memory_cache.pop(cache_id)
            self.memory_cache[cache_id] = (content, expire_time)
            
            return content
    
    def cache_result(self, content: Any, server_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Определить стратегию кэширования в зависимости от размера содержимого и конфигурации"""
        # Получить параметры конфигурации
        if server_config is None:
            server_config = {}
        
        # Совместимость со старым именем max_output_length; приоритет — новое max_output_bytes
        max_output_bytes = server_config.get("max_output_bytes", server_config.get("max_output_length", 1000))
        cache_large_results = server_config.get("cache_large_results", True)
        result_cache_ttl = server_config.get("result_cache_ttl", 300)
        max_memory_cache_size = server_config.get("max_memory_cache_size", 10240)  # 10 КБ
        
        # Сериализовать содержимое для расчёта размера (в байтах)
        if isinstance(content, str):
            content_str = content
        else:
            content_str = json.dumps(content, ensure_ascii=False)
        
        content_size = len(content_str.encode('utf-8'))
        
        if cache_large_results and content_size > max_output_bytes:
            # Содержимое превышает порог — нужно кэшировать
            if content_size <= max_memory_cache_size:
                # Использовать кэш в памяти
                cache_id = self._store_in_memory_cache(content, result_cache_ttl)
                cache_type = "memory"
            else:
                # Использовать файловый кэш
                cache_id = self._store_in_file_cache(content, result_cache_ttl)
                cache_type = "file"
            
            return {
                "result_type": "cached_reference",
                "cache_id": cache_id,
                "cache_type": cache_type,
                "total_size": content_size,
                "message": f"Результат слишком большой ({content_size} байт), сохранён в кэш {'в памяти' if cache_type == 'memory' else 'в файле'}. Используйте /result/{cache_id} для получения полного результата"
            }
        else:
            # Содержимое маленькое — вернуть напрямую
            return {
                "result_type": "direct",
                "result": content
            }
    
    def get_cached_result(self, cache_id: str) -> Optional[Any]:
        """Получить кэшированный результат"""
        # Сначала попробовать из кэша памяти
        result = self._get_from_memory_cache(cache_id)
        if result is not None:
            return result
        
        # Если в памяти нет — попробовать из файлового кэша
        return self._get_from_file_cache(cache_id)
    
    def get_cached_result_partial(self, cache_id: str, start: int = 0, end: Optional[int] = None) -> Dict[str, Any]:
        """Получить часть кэшированного результата"""
        content = self.get_cached_result(cache_id)
        if content is None:
            return {"error": "Cache ID не существует или истёк"}
        
        if isinstance(content, str):
            # Разбиение строкового содержимого
            total_len = len(content)
            actual_end = min(end, total_len) if end is not None else total_len
            actual_start = max(0, start)
            
            return {
                "content": content[actual_start:actual_end],
                "total_length": total_len,
                "start": actual_start,
                "end": actual_end,
                "has_more": actual_end < total_len
            }
        elif isinstance(content, list):
            # Разбиение содержимого-списка
            total_len = len(content)
            actual_end = min(end, total_len) if end is not None else total_len
            actual_start = max(0, start)
            
            return {
                "content": content[actual_start:actual_end],
                "total_length": total_len,
                "start": actual_start,
                "end": actual_end,
                "has_more": actual_end < total_len
            }
        else:
            # Другие типы (dict, объекты): сериализовать в JSON-строку и разбить
            content_str = json.dumps(content, ensure_ascii=False, indent=2)
            total_len = len(content_str)
            actual_end = min(end, total_len) if end is not None else total_len
            actual_start = max(0, start)
            
            return {
                "content": content_str[actual_start:actual_end],
                "total_length": total_len,
                "start": actual_start,
                "end": actual_end,
                "has_more": actual_end < total_len
            }
    
    def search_in_cache(self, cache_id: str, keyword: str, 
                       case_sensitive: bool = False,
                       max_results: int = 50) -> Dict[str, Any]:
        """
        Найти ключевое слово в содержимом кэша (потоковая обработка, оптимизация производительности)
        
        Args:
            cache_id: Cache ID
            keyword: Ключевое слово для поиска
            case_sensitive: Учитывать регистр
            max_results: Максимальное число результатов
        
        Returns:
            Результаты поиска с номерами строк, столбцами и фрагментами содержимого
        """
        # Сначала попробовать из кэша памяти
        content = self._get_from_memory_cache(cache_id)
        
        if content is not None:
            # Кэш в памяти: поиск напрямую
            return self._search_in_memory(content, keyword, case_sensitive, max_results)
        
        # Попробовать из файлового кэша
        cache_file = self._get_cache_directory() / f"{cache_id}.txt"
        if cache_file.exists():
            # Файловый кэш: потоковое чтение и поиск
            return self._search_in_file_streaming(cache_file, keyword, case_sensitive, max_results)
        
        raise ValueError("Кэш не существует или истёк")
    
    def _search_in_memory(self, content: Any, keyword: str, 
                         case_sensitive: bool, max_results: int) -> Dict[str, Any]:
        """Поиск по содержимому в памяти"""
        # Преобразовать в строку
        if isinstance(content, str):
            text = content
        else:
            text = json.dumps(content, ensure_ascii=False, indent=2)
        
        return self._search_in_text(text, keyword, case_sensitive, max_results)
    
    def _search_in_file_streaming(self, cache_file: Path, keyword: str,
                                  case_sensitive: bool, max_results: int) -> Dict[str, Any]:
        """Потоковое чтение файла и поиск (постоянное потребление памяти)"""
        matches = []
        search_keyword = keyword if case_sensitive else keyword.lower()
        line_num = 0
        
        try:
            # Использовать буферизованное чтение по 8 КБ
            with open(cache_file, 'r', encoding='utf-8', buffering=8192) as f:
                for line in f:
                    line_num += 1
                    search_line = line if case_sensitive else line.lower()
                    
                    # Найти все позиции совпадений
                    pos = 0
                    while True:
                        idx = search_line.find(search_keyword, pos)
                        if idx == -1:
                            break
                        
                        matches.append({
                            "line": line_num,
                            "column": idx,
                            "content": line.strip()[:200]  # Ограничить длину во избежание избыточности
                        })
                        
                        if len(matches) >= max_results:
                            break
                        
                        pos = idx + 1
                    
                    if len(matches) >= max_results:
                        break
        except Exception as e:
            print(f"Ошибка потокового поиска в файле: {e}")
            raise
        
        return {
            "keyword": keyword,
            "total_matches": len(matches),
            "matches": matches,
            "truncated": len(matches) >= max_results
        }
    
    def _search_in_text(self, text: str, keyword: str,
                       case_sensitive: bool, max_results: int) -> Dict[str, Any]:
        """Найти ключевое слово в тексте"""
        matches = []
        search_keyword = keyword if case_sensitive else keyword.lower()
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            search_line = line if case_sensitive else line.lower()
            
            # Найти все позиции совпадений
            pos = 0
            while True:
                idx = search_line.find(search_keyword, pos)
                if idx == -1:
                    break
                
                matches.append({
                    "line": line_num,
                    "column": idx,
                    "content": line.strip()[:200]  # Ограничить длину
                })
                
                if len(matches) >= max_results:
                    break
                
                pos = idx + 1
            
            if len(matches) >= max_results:
                break
        
        return {
            "keyword": keyword,
            "total_matches": len(matches),
            "matches": matches,
            "truncated": len(matches) >= max_results
        }
    
    def get_context_around_line(self, cache_id: str, line_num: int,
                                context_lines: int = 3) -> Dict[str, Any]:
        """
        Получить указанную строку и её контекст
        
        Args:
            cache_id: Cache ID
            line_num: Номер целевой строки (с 1)
            context_lines: Число строк контекста
        
        Returns:
            Содержимое с целевой строкой и контекстом
        """
        content = self.get_cached_result(cache_id)
        if content is None:
            raise ValueError("Кэш не существует или истёк")
        
        # Преобразовать в строку
        if isinstance(content, str):
            text = content
        else:
            text = json.dumps(content, ensure_ascii=False, indent=2)
        
        lines = text.split('\n')
        total_lines = len(lines)
        
        # Рассчитать диапазон контекста
        start_line = max(1, line_num - context_lines)
        end_line = min(total_lines, line_num + context_lines)
        
        # Извлечь содержимое контекста
        context_content = '\n'.join(lines[start_line-1:end_line])
        
        return {
            "target_line": line_num,
            "context_start": start_line,
            "context_end": end_line,
            "total_lines": total_lines,
            "content": context_content
        }
    
    async def restart_server(self, server_name: str, server_config: Optional[Dict[str, Any]] = None):
        """Перезапустить указанный сервер"""
        # Если конфигурация не передана — использовать кэшированную
        if server_config is None:
            if server_name not in self.config_cache.get("mcpServers", {}):
                raise ValueError(f"Конфигурация сервера {server_name} не существует")
            server_config = self.config_cache["mcpServers"][server_name]
        
        # Сначала закрыть
        await self.shutdown_server(server_name)
        
        # Подождать немного для гарантии освобождения ресурсов
        await asyncio.sleep(0.5)
        
        # Повторно инициализировать
        await self.init_server(server_name, server_config)


# Глобальный экземпляр менеджера
manager: Optional[MCPManager] = None
config_path: Optional[Path] = None


def log(message: str, log_type: str = "info", *args):
    """Вывод журнала"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color = "\033[32m" if log_type == "info" else "\033[31m"
    reset = "\033[0m"
    print(f"{color}[{timestamp}] {message}{reset}", *args)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global manager, config_path
    
    # Инициализация при запуске
    try:
        manager = MCPManager()
        
        # Получить путь к конфигурации
        env_config_path = os.environ.get("MCP_CONFIG_PATH", "")
        if env_config_path:
            config_path = Path(env_config_path)
        else:
            config_path = get_config_path()
        
        print(f"Чтение файла конфигурации: {config_path}")
        config = await manager.load_config(config_path)
        await manager.init_all_servers(config)
        
        print(f"\n🚀 MCP-мост запущен")
        print(f"   Адрес: http://localhost:{PORT}")
        print(f"   Количество загруженных сервисов: {len(manager.get_services())}")
        print(f"\nДоступные интерфейсы:")
        print(f"   GET  /health                     - Проверка состояния")
        print(f"   GET  /tools                      - Получить список и описания всех [сервисов]")
        print(f"   GET  /tools?serverName=<name>    - Получить список [инструментов] указанного сервиса")
        print(f"   GET  /tool-detail?toolName=<n>   - Получить подробное определение параметров инструмента")
        print(f"   POST /execute                    - Выполнить инструмент (необязательный параметр serverName)")
        print(f"   POST /result                     - Получить кэшированный результат (по частям)")
        print(f"   GET  /result/{'{cache_id}'}            - Получить кэшированный результат (по частям, простой интерфейс)")
        print(f"   POST /search-cache               - Поиск ключевого слова в кэше")
        print(f"   POST /get-cache-context          - Получить контекст указанной строки из кэша")
        print(f"   GET  /config                     - Прочитать содержимое файла конфигурации")
        print(f"   POST /config                     - Обновить файл конфигурации и перезагрузить")
        print(f"   POST /reload                     - Вручную перезагрузить все сервисы")
        print(f"   POST /restart-server             - Перезапустить указанный сервис")
        print(f"   POST /shutdown-server            - Закрыть указанный сервис")
        print(f"   POST /reset-history              - Сбросить историю вызовов\n")
    
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    yield
    
    # Очистка при закрытии
    if manager:
        print("\nЗакрытие сервисов...")
        await manager.shutdown()
        print("Сервер закрыт")


# Создать приложение FastAPI с использованием lifespan
app = FastAPI(title="MCP Bridge Server", version="1.0.0", lifespan=lifespan)

# Настроить CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Проверка состояния"""
    return {"status": "ok", "timestamp": datetime.now().timestamp()}


@app.get("/tools")
async def get_tools(serverName: Optional[str] = Query(None)):
    """Получить список инструментов"""
    try:
        if serverName:
            # Получить инструменты указанного сервера
            tools = manager.get_tools_by_server(serverName)
            return {"success": True, "tools": tools}
        else:
            # Получить список всех сервисов
            services = manager.get_services()
            return {"success": True, "services": services}
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tool-detail")
async def get_tool_detail(
    toolName: str = Query(..., description="Имя инструмента"),
    serverName: Optional[str] = Query(None, description="Имя сервиса (необязательно)")
):
    """
    Получить подробную информацию об инструменте
    
    Аргументы:
        - toolName: Имя инструмента (обязательно)
        - serverName: Имя сервиса (необязательно; при одноимённых инструментах рекомендуется указывать)
    
    Возвращает полное определение инструмента, включая схему параметров, для отладки и понимания требований к параметрам
    """
    try:
        detail = manager.get_tool_detail(toolName, serverName)
        return {"success": True, "tool": detail}
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute")
async def execute_tool(request: ExecuteRequest):
    """
    Выполнить инструмент
    
    Тело запроса:
        - name: Имя инструмента (обязательно)
        - arguments: Параметры инструмента (необязательно, по умолчанию пустой объект)
        - serverName: Имя сервиса (необязательно; указывает, из какого сервиса вызывать инструмент)
    
    Примеры:
        Без указания сервиса (для обратной совместимости):
        {"name": "read_file", "arguments": {"path": "/tmp/test.txt"}}
        
        С указанием сервиса (рекомендуется, чтобы избежать конфликтов одноимённых инструментов):
        {"name": "read_file", "arguments": {"path": "/tmp/test.txt"}, "serverName": "filesystem"}
    """
    try:
        result = await manager.execute_tool(
            request.name, 
            request.arguments,
            request.serverName  # Передать необязательное имя сервиса
        )
        
        # Проверить тип результата
        if isinstance(result, dict) and result.get("result_type") == "cached_reference":
            # Вернуть ссылку на кэш
            return {
                "success": True,
                "result_type": result["result_type"],
                "cache_id": result["cache_id"],
                "cache_type": result["cache_type"],
                "total_size": result["total_size"],
                "message": result["message"]
            }
        else:
            # Вернуть прямой результат
            content = result.get("result") if isinstance(result, dict) and "result" in result else result
            return {"success": True, "result": content}
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_detail = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": error_traceback
        }
        log(f"Ошибка выполнения инструмента: {error_detail}", "error")
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/config")
async def get_config():
    """Прочитать файл конфигурации"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return {"success": True, "config": config}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось прочитать файл конфигурации: {e}")


@app.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """Обновить файл конфигурации и перезагрузить"""
    try:
        # Сохранить конфигурацию
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(request.config, f, indent=2, ensure_ascii=False)
        
        # Перезагрузить сервисы
        await manager.shutdown()
        await manager.init_all_servers(request.config)
        
        return {"success": True, "message": "Конфигурация сохранена и перезагружена"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reload")
async def reload_config():
    """Перезагрузить конфигурацию"""
    try:
        await manager.shutdown()
        config = await manager.load_config(config_path)
        await manager.init_all_servers(config)
        
        return {"success": True, "message": "Конфигурация перезагружена"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset-history")
async def reset_history():
    """Сбросить историю вызовов"""
    manager.reset_tool_call_history()
    return {"success": True, "message": "История вызовов сброшена"}


@app.post("/restart-server")
async def restart_server(request: ServerRestartRequest):
    """Перезапустить указанный сервер"""
    try:
        server_name = request.serverName
        
        # Проверить существование сервиса
        if server_name not in manager.clients and server_name not in manager.config_cache.get("mcpServers", {}):
            raise HTTPException(status_code=404, detail=f"Сервис {server_name} не существует")
        
        # Перезапустить сервис
        await manager.restart_server(server_name, request.config)
        
        return {
            "success": True,
            "message": f"Сервис {server_name} перезапущен",
            "toolCount": len(manager.clients[server_name]["tools"]) if server_name in manager.clients else 0
        }
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/shutdown-server")
async def shutdown_server(request: ServerRestartRequest):
    """Закрыть указанный сервер"""
    try:
        server_name = request.serverName
        
        # Проверить существование сервиса
        if server_name not in manager.clients:
            raise HTTPException(status_code=404, detail=f"Сервис {server_name} не существует или не запущен")
        
        # Закрыть сервис
        await manager.shutdown_server(server_name)
        
        return {
            "success": True,
            "message": f"Сервис {server_name} закрыт"
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/result")
async def get_cached_result(request: GetResultRequest):
    """Получить кэшированный результат"""
    try:
        result = manager.get_cached_result_partial(request.cache_id, request.start, request.end)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return {
            "success": True,
            "result": result["content"],
            "metadata": {
                "total_length": result["total_length"],
                "start": result["start"],
                "end": result["end"],
                "has_more": result["has_more"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/result/{cache_id}")
async def get_cached_result_simple(cache_id: str, start: int = 0, end: Optional[int] = None):
    """Простой интерфейс для получения кэшированного результата"""
    try:
        result = manager.get_cached_result_partial(cache_id, start, end)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return {
            "success": True,
            "result": result["content"],
            "metadata": {
                "total_length": result["total_length"],
                "start": result["start"],
                "end": result["end"],
                "has_more": result["has_more"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search-cache")
async def search_cache(request: SearchCacheRequest):
    """
    Найти ключевое слово в содержимом кэша
    
    Тело запроса:
        - cache_id: Cache ID
        - keyword: Ключевое слово для поиска
        - case_sensitive: Учитывать регистр (необязательно, по умолчанию false)
        - max_results: Максимальное число результатов (необязательно, по умолчанию 50)
    
    Возвращает:
        Результаты поиска с номерами строк, столбцами и фрагментами содержимого
    """
    try:
        result = manager.search_in_cache(
            request.cache_id,
            request.keyword,
            request.case_sensitive,
            request.max_results
        )
        return {"success": True, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/get-cache-context")
async def get_cache_context(request: GetCacheContextRequest):
    """
    Получить контекст указанной строки из кэша
    
    Тело запроса:
        - cache_id: Cache ID
        - line_num: Номер целевой строки (с 1)
        - context_lines: Число строк контекста (необязательно, по умолчанию 3)
    
    Возвращает:
        Целевую строку и её контекст
    """
    try:
        result = manager.get_context_around_line(
            request.cache_id,
            request.line_num,
            request.context_lines
        )
        return {"success": True, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def signal_handler(sig, frame):
    """Обработка сигнала завершения"""
    print("\nПолучен сигнал завершения, выполняется закрытие...")
    sys.exit(0)


if __name__ == "__main__":
    import argparse
    
    # Разобрать аргументы командной строки
    parser = argparse.ArgumentParser(
        description=f'MCP Bridge Server v{__version__}',
        epilog='Подробная документация: https://github.com/your-repo/mcp-bridge-server'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'MCP Bridge Server v{__version__}'
    )
    parser.add_argument(
        '--port', 
        type=int, 
        default=PORT, 
        help=f'Порт сервера (по умолчанию: {PORT})'
    )
    parser.add_argument(
        '--auto-kill-port',
        action='store_true',
        help='Автоматически завершать процесс, занимающий порт'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Путь к файлу конфигурации'
    )
    args = parser.parse_args()
    
    # Обновить порт
    PORT = args.port
    
    # Установить переменную окружения с путём к конфигурации
    if args.config:
        os.environ['MCP_CONFIG_PATH'] = args.config
    
    # Проверить порт
    print(f"MCP Bridge Server v{__version__}")
    print(f"Проверка порта {PORT}...")
    
    if not check_and_handle_port(PORT, args.auto_kill_port):
        print("\nНе удалось запустить сервер: порт недоступен")
        sys.exit(1)
    
    print(f"✓ Порт {PORT} доступен\n")
    
    # Зарегистрировать обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запустить сервер
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=PORT,
            log_level="info"
        )
    except OSError as e:
        if "address already in use" in str(e).lower():
            print(f"\n✗ Ошибка: порт {PORT} уже занят")
            print(f"   Используйте параметр --port для указания другого порта или --auto-kill-port для автоматического завершения занимающего процесса")
        else:
            print(f"\n✗ Ошибка запуска: {e}")
        sys.exit(1)