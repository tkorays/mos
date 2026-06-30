# MOS 后台任务管理设计方案

**文档版本**: 1.0
**设计日期**: 2026-06-30
**作者**: MOS Team

---

## 1. 概述

本设计文档描述 MOS 框架的后台任务管理功能，允许各个插件注册后台任务，支持定时调度、间隔执行和事件驱动的任务模式。

### 1.1 需求背景

MOS 作为插件化框架，需要支持以下场景的后台任务：

- **数据采集任务**: 定期从外部 API 获取数据（行情数据、新闻、财报等）
- **定时执行策略**: 定时运行量化策略、监控任务
- **长时间计算任务**: 后台运行的耗时计算（回测、模型训练）
- **消息推送服务**: 持续运行的消息监听和推送（Telegram bot、微信消息）

### 1.2 设计目标

- 支持多种任务触发方式：Cron 表达式、时间间隔、事件驱动
- 支持两种运行模式：CLI 前台运行（开发调试）+ 独立守护进程（生产环境）
- 提供可插拔的存储后端：默认文件系统，后续可扩展至 SQLite/DuckDB
- 与现有 MOS 插件系统无缝集成
- 简洁的接口设计，便于插件开发者使用

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      插件层                              │
│  mos_quant / mos_agent / mos_cls_telegram ...          │
│  describe_plugin() -> register_tasks()                 │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    核心层                                │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ TaskRegistry │  │  Scheduler   │  │  EventBus   │ │
│  │ (任务注册表) │  │ (APScheduler)│  │ (事件总线)  │ │
│  └──────────────┘  └──────────────┘  └─────────────┘ │
│  ┌──────────────┐  ┌──────────────┐                   │
│  │ProcessManager│  │ TaskRunner  │                   │
│  │(进程管理器)  │  │ (任务执行器) │                   │
│  └──────────────┘  └──────────────┘                   │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                    存储层                                │
│  StorageBackend (接口)                                 │
│  ├── FileBackend (默认)                                │
│  ├── SQLiteBackend                                     │
│  └── DuckDBBackend (后续扩展)                          │
└─────────────────────────────────────────────────────────┘
```

### 2.1 核心组件职责

| 组件 | 职责 |
|------|------|
| TaskRegistry | 任务注册表，管理任务定义（名称、调度规则、处理函数） |
| Scheduler | 调度器，基于 APScheduler 实现 cron/interval 调度 |
| EventBus | 事件总线，实现事件驱动任务 |
| ProcessManager | 守护进程管理器，负责启动/停止/监控进程 |
| TaskRunner | 任务执行器，实际执行任务函数并记录日志 |

---

## 3. 核心组件设计

### 3.1 任务定义（TaskDefinition）

```python
from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any
from enum import Enum

class TaskTriggerType(Enum):
    """任务触发类型"""
    CRON = "cron"           # Cron 表达式
    INTERVAL = "interval"   # 间隔执行
    EVENT = "event"         # 事件驱动

@dataclass
class TaskDefinition:
    """任务定义"""
    name: str                          # 任务唯一标识
    func: Callable                     # 任务执行函数
    trigger_type: TaskTriggerType      # 触发类型
    trigger_config: Dict[str, Any]     # 触发配置
    description: str = ""              # 任务描述
    enabled: bool = True               # 是否启用
    max_retries: int = 0               # 最大重试次数
    timeout: Optional[int] = None      # 超时时间（秒）
```

**触发配置示例：**

- Cron: `{"cron": "0 9 * * 1-5"}` （工作日 9 点）
- Interval: `{"seconds": 300}` 或 `{"minutes": 5}` （每 5 分钟）
- Event: `{"event_type": "price_update"}` （价格更新事件）

### 3.2 任务注册表（TaskRegistry）

```python
class TaskRegistry:
    """任务注册表，管理所有已注册的任务"""

    def __init__(self):
        self._tasks: Dict[str, TaskDefinition] = {}

    def register(self, task: TaskDefinition) -> None:
        """注册任务"""
        if task.name in self._tasks:
            raise ValueError(f"Task '{task.name}' already registered")
        self._tasks[task.name] = task

    def unregister(self, name: str) -> Optional[TaskDefinition]:
        """取消注册任务"""
        return self._tasks.pop(name, None)

    def get(self, name: str) -> Optional[TaskDefinition]:
        """获取任务定义"""
        return self._tasks.get(name)

    def list_all(self) -> List[TaskDefinition]:
        """列出所有任务"""
        return list(self._tasks.values())
```

### 3.3 调度器（Scheduler）

基于 APScheduler 实现，支持 Cron 和 Interval 触发：

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

class Scheduler:
    """基于 APScheduler 的任务调度器"""

    def __init__(self, storage_backend: StorageBackend):
        self._scheduler = BackgroundScheduler()
        self._registry = TaskRegistry()
        self._storage = storage_backend

    def start(self):
        """启动调度器"""
        self._load_tasks_from_storage()
        self._scheduler.start()

    def add_task(self, task: TaskDefinition):
        """添加任务"""
        self._registry.register(task)
        self._schedule_task(task)
        self._storage.save_task(task)
```

### 3.4 事件总线（EventBus）

实现事件驱动任务：

```python
class EventBus:
    """事件总线，实现事件驱动任务"""

    def __init__(self):
        self._subscribers: Dict[str, Set[str]] = defaultdict(set)
        self._registry: TaskRegistry = None

    def subscribe(self, event_type: str, task_name: str):
        """订阅事件"""
        self._subscribers[event_type].add(task_name)

    def publish(self, event_type: str, data: Any = None):
        """发布事件，触发订阅的任务"""
        task_names = self._subscribers.get(event_type, set())
        for task_name in task_names:
            task = self._registry.get(task_name)
            if task and task.enabled:
                self._execute_task(task, data)
```

### 3.5 进程管理器（ProcessManager）

使用 Python 标准库 `multiprocessing` 实现守护进程管理：

```python
import multiprocessing
import threading

class ProcessManager:
    """守护进程管理器"""

    def __init__(self, pid_file: Path, log_file: Path):
        self.pid_file = pid_file
        self.log_file = log_file
        self._process: Optional[multiprocessing.Process] = None
        self._watcher: Optional[threading.Thread] = None

    def start(self, target: Callable, args=()):
        """启动守护进程"""
        self._process = multiprocessing.Process(
            target=self._run_with_logging,
            args=(target, args),
            name="mos-daemon"
        )
        self._process.start()
        self._save_pid()
        self._start_watcher()  # 监控线程，异常退出自动重启

    def stop(self):
        """停止守护进程"""
        self._process.terminate()
        self._process.join(timeout=10)
        if self._process.is_alive():
            self._process.kill()

    def is_running(self) -> bool:
        """检查守护进程是否在运行"""
        return self._process and self._process.is_alive()
```

**特性：**
- 跨平台支持（Windows/Linux/Mac）
- 自动监控进程状态
- 异常退出自动重启
- 集成 MOS 日志系统

---

## 4. 插件集成方式

### 4.1 扩展 PluginDefinition

在现有 `PluginDefinition` 中添加 `register_tasks` 字段：

```python
@dataclass
class PluginDefinition:
    name: str
    command: click.Group
    version: Optional[str] = None
    get_config: Optional[Callable] = None
    init: Optional[Callable] = None
    register_mcp: Optional[Callable] = None
    register_tasks: Optional[Callable] = None  # 新增
```

### 4.2 插件注册任务示例

```python
# mos_quant/__init__.py

def describe_plugin() -> PluginDefinition:
    return PluginDefinition(
        name="quant",
        command=quant_cli,
        get_config=get_quant_config,
        register_tasks=register_quant_tasks,
    )

def register_quant_tasks(registry: TaskRegistry, event_bus: EventBus):
    """注册 quant 插件的后台任务"""

    # Cron 任务：每天 9 点更新股票列表
    registry.register(TaskDefinition(
        name="quant.update_stock_list",
        func=update_stock_list,
        trigger_type=TaskTriggerType.CRON,
        trigger_config={"cron": "0 9 * * 1-5"},
        description="更新股票列表",
    ))

    # Interval 任务：每 5 分钟检查价格
    registry.register(TaskDefinition(
        name="quant.check_price_changes",
        func=check_price_changes,
        trigger_type=TaskTriggerType.INTERVAL,
        trigger_config={"minutes": 5},
        description="检查价格变动",
    ))

    # Event 任务：响应新数据事件
    registry.register(TaskDefinition(
        name="quant.on_new_bar",
        func=on_new_bar,
        trigger_type=TaskTriggerType.EVENT,
        trigger_config={"event_type": "bar_update"},
        description="处理新 Bar 数据",
    ))
    event_bus.subscribe("bar_update", "quant.on_new_bar")
```

---

## 5. CLI 命令设计

### 5.1 命令结构

```bash
mos task <command> [options]
```

### 5.2 子命令列表

| 命令 | 功能 | 参数 |
|------|------|------|
| `start` | 启动调度器 | `--daemon` 以守护进程模式运行 |
| `stop` | 停止守护进程 | 无 |
| `restart` | 重启守护进程 | 无 |
| `status` | 查看调度器状态 | 无 |
| `list` | 列出所有任务 | 无 |
| `enable <task>` | 启用指定任务 | 任务名称 |
| `disable <task>` | 禁用指定任务 | 任务名称 |
| `run <task>` | 立即执行任务 | 任务名称（用于测试） |
| `logs [task]` | 查看任务日志 | `-n` 显示最后 N 条 |

### 5.3 使用示例

```bash
# 前台运行（开发调试）
mos task start

# 守护进程模式（生产环境）
mos task start --daemon

# 查看状态
mos task status

# 列出任务
mos task list

# 测试任务
mos task run quant.update_stock_list

# 查看日志
mos task logs quant.update_stock_list -n 50

# 停止守护进程
mos task stop
```

---

## 6. 存储后端接口

### 6.1 抽象接口

```python
class StorageBackend(ABC):
    """存储后端抽象接口"""

    @abstractmethod
    def save_task(self, task: TaskRecord) -> None:
        """保存任务定义"""

    @abstractmethod
    def load_task(self, name: str) -> Optional[TaskRecord]:
        """加载任务定义"""

    @abstractmethod
    def load_all_tasks(self) -> List[TaskRecord]:
        """加载所有任务"""

    @abstractmethod
    def delete_task(self, name: str) -> None:
        """删除任务"""

    @abstractmethod
    def save_execution_log(self, log: TaskExecutionLog) -> None:
        """保存执行日志"""

    @abstractmethod
    def load_execution_logs(
        self,
        task_name: Optional[str] = None,
        limit: int = 100
    ) -> List[TaskExecutionLog]:
        """加载执行日志"""

    @abstractmethod
    def save_daemon_status(self, status: Dict[str, Any]) -> None:
        """保存守护进程状态"""

    @abstractmethod
    def load_daemon_status(self) -> Optional[Dict[str, Any]]:
        """加载守护进程状态"""
```

### 6.2 默认实现：FileBackend

- **任务定义**: 存储在 `~/.mos/tasks/tasks.json`
- **执行日志**: 存储在 `~/.mos/tasks/logs/{task_name}.jsonl`
- **守护进程状态**: 存储在 `~/.mos/tasks/daemon_status.json`

### 6.3 可扩展实现

- SQLiteBackend
- DuckDBBackend
- PostgreSQLBackend（复用 MOS 配置）

---

## 7. 文件结构

新增模块位于 `src/mos/core/task/`：

```
src/mos/core/task/
├── __init__.py              # 模块入口，导出 TaskManager
├── types.py                 # TaskDefinition, TaskTriggerType 等
├── registry.py              # TaskRegistry
├── scheduler.py             # Scheduler (APScheduler)
├── event_bus.py             # EventBus
├── process_manager.py       # ProcessManager
├── task_runner.py           # TaskRunner
├── manager.py               # TaskManager (统一管理器)
└── storage/
    ├── __init__.py          # 导出 StorageBackend
    ├── base.py              # StorageBackend 抽象类
    ├── file.py              # FileBackend 实现
    └── duckdb.py            # DuckDBBackend (后续)
```

CLI 命令位于 `src/mos/cli/task.py`。

---

## 8. 技术选型

| 功能 | 技术方案 | 理由 |
|------|----------|------|
| 调度引擎 | APScheduler | 成熟稳定，支持 Cron/Interval |
| 进程管理 | multiprocessing | 标准库，跨平台支持 |
| 事件驱动 | 自研 EventBus | 简单灵活，便于定制 |
| 存储接口 | 抽象接口 + FileBackend | 可插拔，默认无依赖 |

---

## 9. 未来扩展

- 支持 Windows Service / systemd 部署
- 支持任务依赖链（Task A → Task B）
- 支持任务优先级
- 提供 Web UI 监控界面（集成 Grafana）
- 支持分布式任务调度（多节点）

---

## 10. 总结

本设计方案提供了一套完整的后台任务管理功能：

1. **灵活的触发方式**: Cron、Interval、Event 三种模式满足各类场景
2. **两种运行模式**: 前台运行便于开发，守护进程适合生产
3. **插件化集成**: 与现有 MOS 插件系统无缝衔接
4. **可扩展存储**: 简洁的接口设计，便于后续扩展 DuckDB 等后端
5. **零依赖启动**: 默认使用文件系统，无需额外服务

设计遵循 MOS 的简洁原则，接口设计简单明了，便于插件开发者快速上手。
