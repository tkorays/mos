# 后台任务管理实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 MOS 框架实现后台任务管理功能，支持插件注册定时、间隔、事件驱动任务，并提供 CLI + 守护进程两种运行模式。

**Architecture:** 基于 APScheduler 实现调度，使用 multiprocessing 实现守护进程管理，提供可插拔的存储后端接口（默认文件系统）。插件通过 register_tasks() 函数注册任务。

**Tech Stack:** Python 3.13+, APScheduler, multiprocessing, Click CLI, loguru, dataclass

---

## 前置准备

### Task 0: 环境准备

**Files:**
- Modify: `pyproject.toml`

**Step 1: 添加 APScheduler 依赖**

打开 `pyproject.toml`，在 `dependencies` 中添加：

```toml
dependencies = [
    "apscheduler>=3.10.0",
    # 其他现有依赖...
]
```

**Step 2: 安装依赖**

运行：
```bash
uv sync
```

预期：成功安装 APScheduler。

**Step 3: 验证安装**

运行：
```bash
uv run python -c "import apscheduler; print(apscheduler.__version__)"
```

预期：输出 APScheduler 版本号。

---

## 第一阶段：核心数据结构

### Task 1: 任务定义类型

**Files:**
- Create: `src/mos/core/task/__init__.py`
- Create: `src/mos/core/task/types.py`
- Create: `test/test_task_types.py`

**Step 1: 创建模块目录结构**

创建目录：
```bash
mkdir -p src/mos/core/task/storage
mkdir -p test
```

**Step 2: 写类型定义文件**

创建 `src/mos/core/task/types.py`：

```python
"""任务类型定义"""

from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any
from enum import Enum


class TaskTriggerType(Enum):
    """任务触发类型"""
    CRON = "cron"
    INTERVAL = "interval"
    EVENT = "event"


@dataclass
class TaskDefinition:
    """任务定义"""
    name: str
    func: Callable
    trigger_type: TaskTriggerType
    trigger_config: Dict[str, Any]
    description: str = ""
    enabled: bool = True
    max_retries: int = 0
    timeout: Optional[int] = None
```

**Step 3: 写测试文件**

创建 `test/test_task_types.py`：

```python
"""任务类型测试"""

import unittest
from mos.core.task.types import TaskDefinition, TaskTriggerType


class TestTaskTypes(unittest.TestCase):

    def test_task_trigger_type_enum(self):
        """测试触发类型枚举"""
        assert TaskTriggerType.CRON.value == "cron"
        assert TaskTriggerType.INTERVAL.value == "interval"
        assert TaskTriggerType.EVENT.value == "event"

    def test_task_definition_creation(self):
        """测试任务定义创建"""
        def dummy_func():
            pass

        task = TaskDefinition(
            name="test.task",
            func=dummy_func,
            trigger_type=TaskTriggerType.CRON,
            trigger_config={"cron": "0 9 * * 1-5"},
            description="测试任务",
        )

        assert task.name == "test.task"
        assert task.trigger_type == TaskTriggerType.CRON
        assert task.enabled is True

    def test_task_definition_with_interval(self):
        """测试间隔任务定义"""
        def dummy_func():
            pass

        task = TaskDefinition(
            name="test.interval",
            func=dummy_func,
            trigger_type=TaskTriggerType.INTERVAL,
            trigger_config={"minutes": 5},
        )

        assert task.trigger_type == TaskTriggerType.INTERVAL
        assert task.trigger_config["minutes"] == 5


if __name__ == "__main__":
    unittest.main()
```

**Step 4: 运行测试验证**

运行：
```bash
uv run pytest test/test_task_types.py -v
```

预期：3 个测试全部通过。

**Step 5: 创建模块入口**

创建 `src/mos/core/task/__init__.py`：

```python
"""任务管理模块"""

from mos.core.task.types import TaskDefinition, TaskTriggerType

__all__ = ["TaskDefinition", "TaskTriggerType"]
```

**Step 6: 提交代码**

```bash
git add src/mos/core/task/__init__.py src/mos/core/task/types.py test/test_task_types.py
git commit -m "feat(task): add task type definitions"
```

---

### Task 2: 任务注册表

**Files:**
- Create: `src/mos/core/task/registry.py`
- Create: `test/test_task_registry.py`

**Step 1: 写测试文件**

创建 `test/test_task_registry.py`：

```python
"""任务注册表测试"""

import unittest
from mos.core.task.registry import TaskRegistry
from mos.core.task.types import TaskDefinition, TaskTriggerType


class TestTaskRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = TaskRegistry()

    def test_register_task(self):
        """测试注册任务"""
        task = TaskDefinition(
            name="test.task",
            func=lambda: None,
            trigger_type=TaskTriggerType.CRON,
            trigger_config={"cron": "0 9 * * *"},
        )

        self.registry.register(task)
        assert self.registry.get("test.task") == task

    def test_register_duplicate_task(self):
        """测试重复注册任务"""
        task1 = TaskDefinition(
            name="test.task",
            func=lambda: None,
            trigger_type=TaskTriggerType.CRON,
            trigger_config={"cron": "0 9 * * *"},
        )

        self.registry.register(task1)

        task2 = TaskDefinition(
            name="test.task",
            func=lambda: None,
            trigger_type=TaskTriggerType.INTERVAL,
            trigger_config={"minutes": 5},
        )

        with self.assertRaises(ValueError):
            self.registry.register(task2)

    def test_unregister_task(self):
        """测试取消注册任务"""
        task = TaskDefinition(
            name="test.task",
            func=lambda: None,
            trigger_type=TaskTriggerType.CRON,
            trigger_config={"cron": "0 9 * * *"},
        )

        self.registry.register(task)
        removed = self.registry.unregister("test.task")

        assert removed == task
        assert self.registry.get("test.task") is None

    def test_list_all_tasks(self):
        """测试列出所有任务"""
        task1 = TaskDefinition(
            name="test.task1",
            func=lambda: None,
            trigger_type=TaskTriggerType.CRON,
            trigger_config={"cron": "0 9 * * *"},
        )
        task2 = TaskDefinition(
            name="test.task2",
            func=lambda: None,
            trigger_type=TaskTriggerType.INTERVAL,
            trigger_config={"minutes": 5},
        )

        self.registry.register(task1)
        self.registry.register(task2)

        tasks = self.registry.list_all()
        assert len(tasks) == 2
        assert task1 in tasks
        assert task2 in tasks


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 运行测试验证失败**

运行：
```bash
uv run pytest test/test_task_registry.py -v
```

预期：失败，TaskRegistry 未定义。

**Step 3: 实现注册表**

创建 `src/mos/core/task/registry.py`：

```python
"""任务注册表"""

from typing import Dict, List, Optional
from mos.core.task.types import TaskDefinition


class TaskRegistry:
    """任务注册表，管理所有已注册的任务"""

    def __init__(self):
        self._tasks: Dict[str, TaskDefinition] = {}

    def register(self, task: TaskDefinition) -> None:
        """注册任务

        Args:
            task: 任务定义

        Raises:
            ValueError: 如果任务名称已存在
        """
        if task.name in self._tasks:
            raise ValueError(f"Task '{task.name}' already registered")
        self._tasks[task.name] = task

    def unregister(self, name: str) -> Optional[TaskDefinition]:
        """取消注册任务

        Args:
            name: 任务名称

        Returns:
            取消注册的任务定义，如果不存在则返回 None
        """
        return self._tasks.pop(name, None)

    def get(self, name: str) -> Optional[TaskDefinition]:
        """获取任务定义

        Args:
            name: 任务名称

        Returns:
            任务定义，如果不存在则返回 None
        """
        return self._tasks.get(name)

    def list_all(self) -> List[TaskDefinition]:
        """列出所有任务

        Returns:
            所有已注册任务的列表
        """
        return list(self._tasks.values())

    def list_by_trigger_type(self, trigger_type: TaskTriggerType) -> List[TaskDefinition]:
        """按触发类型列出任务

        Args:
            trigger_type: 触发类型

        Returns:
            符合触发类型的任务列表
        """
        return [t for t in self._tasks.values() if t.trigger_type == trigger_type]
```

**Step 4: 运行测试验证通过**

运行：
```bash
uv run pytest test/test_task_registry.py -v
```

预期：5 个测试全部通过。

**Step 5: 更新模块入口**

修改 `src/mos/core/task/__init__.py`：

```python
"""任务管理模块"""

from mos.core.task.types import TaskDefinition, TaskTriggerType
from mos.core.task.registry import TaskRegistry

__all__ = ["TaskDefinition", "TaskTriggerType", "TaskRegistry"]
```

**Step 6: 提交代码**

```bash
git add src/mos/core/task/registry.py test/test_task_registry.py src/mos/core/task/__init__.py
git commit -m "feat(task): add task registry"
```

---

## 第二阶段：存储后端

### Task 3: 存储后端抽象接口

**Files:**
- Create: `src/mos/core/task/storage/__init__.py`
- Create: `src/mos/core/task/storage/base.py`
- Create: `test/test_storage_base.py`

**Step 1: 写存储接口测试**

创建 `test/test_storage_base.py`：

```python
"""存储后端接口测试"""

import unittest
from datetime import datetime
from mos.core.task.storage.base import StorageBackend, TaskRecord, TaskExecutionLog


class TestStorageTypes(unittest.TestCase):

    def test_task_record_creation(self):
        """测试任务记录创建"""
        record = TaskRecord(
            name="test.task",
            trigger_type="cron",
            trigger_config={"cron": "0 9 * * *"},
            description="测试任务",
            enabled=True,
            max_retries=0,
            timeout=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert record.name == "test.task"
        assert record.trigger_type == "cron"

    def test_execution_log_creation(self):
        """测试执行日志创建"""
        log = TaskExecutionLog(
            id="log-123",
            task_name="test.task",
            started_at=datetime.now(),
            finished_at=None,
            status="running",
            error=None,
            duration=None,
        )

        assert log.task_name == "test.task"
        assert log.status == "running"


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 实现存储抽象类**

创建 `src/mos/core/task/storage/base.py`：

```python
"""存储后端抽象接口"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TaskRecord:
    """任务记录"""
    name: str
    trigger_type: str
    trigger_config: Dict[str, Any]
    description: str
    enabled: bool
    max_retries: int
    timeout: Optional[int]
    created_at: datetime
    updated_at: datetime


@dataclass
class TaskExecutionLog:
    """任务执行日志"""
    id: str
    task_name: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    error: Optional[str]
    duration: Optional[float]


class StorageBackend(ABC):
    """存储后端抽象接口"""

    @abstractmethod
    def save_task(self, task: TaskRecord) -> None:
        """保存任务定义"""
        pass

    @abstractmethod
    def load_task(self, name: str) -> Optional[TaskRecord]:
        """加载任务定义"""
        pass

    @abstractmethod
    def load_all_tasks(self) -> List[TaskRecord]:
        """加载所有任务"""
        pass

    @abstractmethod
    def delete_task(self, name: str) -> None:
        """删除任务"""
        pass

    @abstractmethod
    def save_execution_log(self, log: TaskExecutionLog) -> None:
        """保存执行日志"""
        pass

    @abstractmethod
    def load_execution_logs(
        self,
        task_name: Optional[str] = None,
        limit: int = 100
    ) -> List[TaskExecutionLog]:
        """加载执行日志"""
        pass

    @abstractmethod
    def save_daemon_status(self, status: Dict[str, Any]) -> None:
        """保存守护进程状态"""
        pass

    @abstractmethod
    def load_daemon_status(self) -> Optional[Dict[str, Any]]:
        """加载守护进程状态"""
        pass
```

**Step 3: 运行测试**

运行：
```bash
uv run pytest test/test_storage_base.py -v
```

预期：2 个测试通过。

**Step 4: 创建存储模块入口**

创建 `src/mos/core/task/storage/__init__.py`：

```python
"""存储后端模块"""

from mos.core.task.storage.base import StorageBackend, TaskRecord, TaskExecutionLog

__all__ = ["StorageBackend", "TaskRecord", "TaskExecutionLog"]
```

**Step 5: 提交代码**

```bash
git add src/mos/core/task/storage/ test/test_storage_base.py
git commit -m "feat(task): add storage backend abstract interface"
```

---

### Task 4: 文件系统存储后端

**Files:**
- Create: `src/mos/core/task/storage/file.py`
- Create: `test/test_storage_file.py`

**Step 1: 写文件存储测试**

创建 `test/test_storage_file.py`：

```python
"""文件存储后端测试"""

import unittest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from mos.core.task.storage.file import FileBackend
from mos.core.task.storage.base import TaskRecord, TaskExecutionLog


class TestFileBackend(unittest.TestCase):

    def setUp(self):
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.backend = FileBackend(Path(self.temp_dir))

    def tearDown(self):
        # 清理临时目录
        shutil.rmtree(self.temp_dir)

    def test_save_and_load_task(self):
        """测试保存和加载任务"""
        record = TaskRecord(
            name="test.task",
            trigger_type="cron",
            trigger_config={"cron": "0 9 * * *"},
            description="测试任务",
            enabled=True,
            max_retries=0,
            timeout=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.backend.save_task(record)
        loaded = self.backend.load_task("test.task")

        assert loaded is not None
        assert loaded.name == record.name
        assert loaded.trigger_type == record.trigger_type

    def test_load_all_tasks(self):
        """测试加载所有任务"""
        record1 = TaskRecord(
            name="test.task1",
            trigger_type="cron",
            trigger_config={"cron": "0 9 * * *"},
            description="测试任务1",
            enabled=True,
            max_retries=0,
            timeout=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        record2 = TaskRecord(
            name="test.task2",
            trigger_type="interval",
            trigger_config={"minutes": 5},
            description="测试任务2",
            enabled=True,
            max_retries=0,
            timeout=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.backend.save_task(record1)
        self.backend.save_task(record2)

        tasks = self.backend.load_all_tasks()
        assert len(tasks) == 2

    def test_delete_task(self):
        """测试删除任务"""
        record = TaskRecord(
            name="test.task",
            trigger_type="cron",
            trigger_config={"cron": "0 9 * * *"},
            description="测试任务",
            enabled=True,
            max_retries=0,
            timeout=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.backend.save_task(record)
        self.backend.delete_task("test.task")

        loaded = self.backend.load_task("test.task")
        assert loaded is None

    def test_save_and_load_execution_log(self):
        """测试保存和加载执行日志"""
        log = TaskExecutionLog(
            id="log-123",
            task_name="test.task",
            started_at=datetime.now(),
            finished_at=datetime.now(),
            status="success",
            error=None,
            duration=1.5,
        )

        self.backend.save_execution_log(log)
        logs = self.backend.load_execution_logs(task_name="test.task")

        assert len(logs) >= 1
        assert logs[0].task_name == "test.task"

    def test_daemon_status(self):
        """测试守护进程状态"""
        status = {"running": True, "pid": 12345}

        self.backend.save_daemon_status(status)
        loaded = self.backend.load_daemon_status()

        assert loaded is not None
        assert loaded["running"] is True
        assert loaded["pid"] == 12345


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 运行测试验证失败**

运行：
```bash
uv run pytest test/test_storage_file.py -v
```

预期：失败，FileBackend 未定义。

**Step 3: 实现文件存储后端**

创建 `src/mos/core/task/storage/file.py`（完整实现见设计文档第 5.2 节）。

**Step 4: 运行测试验证通过**

运行：
```bash
uv run pytest test/test_storage_file.py -v
```

预期：6 个测试全部通过。

**Step 5: 更新存储模块入口**

修改 `src/mos/core/task/storage/__init__.py`：

```python
"""存储后端模块"""

from mos.core.task.storage.base import StorageBackend, TaskRecord, TaskExecutionLog
from mos.core.task.storage.file import FileBackend

__all__ = ["StorageBackend", "TaskRecord", "TaskExecutionLog", "FileBackend"]
```

**Step 6: 提交代码**

```bash
git add src/mos/core/task/storage/file.py test/test_storage_file.py src/mos/core/task/storage/__init__.py
git commit -m "feat(task): add file storage backend"
```

---

## 第三阶段：核心组件实现

### Task 5: 事件总线

**Files:**
- Create: `src/mos/core/task/event_bus.py`
- Create: `test/test_event_bus.py`

**Step 1: 写事件总线测试**

创建 `test/test_event_bus.py`：

```python
"""事件总线测试"""

import unittest
from mos.core.task.event_bus import EventBus
from mos.core.task.registry import TaskRegistry
from mos.core.task.types import TaskDefinition, TaskTriggerType


class TestEventBus(unittest.TestCase):

    def setUp(self):
        self.registry = TaskRegistry()
        self.event_bus = EventBus()
        self.event_bus.set_registry(self.registry)
        self.executed_tasks = []

    def _create_task_func(self, task_name):
        def func(event_data=None):
            self.executed_tasks.append((task_name, event_data))
        return func

    def test_subscribe_and_publish(self):
        """测试订阅和发布事件"""
        task = TaskDefinition(
            name="test.task",
            func=self._create_task_func("test.task"),
            trigger_type=TaskTriggerType.EVENT,
            trigger_config={"event_type": "test_event"},
        )

        self.registry.register(task)
        self.event_bus.subscribe("test_event", "test.task")

        self.event_bus.publish("test_event", {"data": "test"})

        assert len(self.executed_tasks) == 1
        assert self.executed_tasks[0] == ("test.task", {"data": "test"})

    def test_unsubscribe(self):
        """测试取消订阅"""
        task = TaskDefinition(
            name="test.task",
            func=self._create_task_func("test.task"),
            trigger_type=TaskTriggerType.EVENT,
            trigger_config={"event_type": "test_event"},
        )

        self.registry.register(task)
        self.event_bus.subscribe("test_event", "test.task")
        self.event_bus.unsubscribe("test_event", "test.task")

        self.event_bus.publish("test_event", {"data": "test"})

        assert len(self.executed_tasks) == 0

    def test_disabled_task_not_executed(self):
        """测试禁用的任务不会执行"""
        task = TaskDefinition(
            name="test.task",
            func=self._create_task_func("test.task"),
            trigger_type=TaskTriggerType.EVENT,
            trigger_config={"event_type": "test_event"},
            enabled=False,
        )

        self.registry.register(task)
        self.event_bus.subscribe("test_event", "test.task")

        self.event_bus.publish("test_event", {"data": "test"})

        assert len(self.executed_tasks) == 0


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 实现事件总线**

创建 `src/mos/core/task/event_bus.py`：

```python
"""事件总线"""

from typing import Dict, Set, Any, Optional
from collections import defaultdict
from mos.core.task.registry import TaskRegistry


class EventBus:
    """事件总线，实现事件驱动任务"""

    def __init__(self):
        self._subscribers: Dict[str, Set[str]] = defaultdict(set)
        self._registry: Optional[TaskRegistry] = None

    def set_registry(self, registry: TaskRegistry):
        """设置任务注册表

        Args:
            registry: 任务注册表
        """
        self._registry = registry

    def subscribe(self, event_type: str, task_name: str):
        """订阅事件

        Args:
            event_type: 事件类型
            task_name: 任务名称
        """
        self._subscribers[event_type].add(task_name)

    def unsubscribe(self, event_type: str, task_name: str):
        """取消订阅

        Args:
            event_type: 事件类型
            task_name: 任务名称
        """
        self._subscribers[event_type].discard(task_name)

    def publish(self, event_type: str, data: Any = None):
        """发布事件，触发订阅的任务

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if self._registry is None:
            return

        task_names = self._subscribers.get(event_type, set())
        for task_name in task_names:
            task = self._registry.get(task_name)
            if task and task.enabled:
                self._execute_task(task, data)

    def _execute_task(self, task, event_data: Any):
        """执行事件驱动的任务

        Args:
            task: 任务定义
            event_data: 事件数据
        """
        try:
            task.func(event_data)
        except Exception as e:
            # 记录错误日志
            from mos.core.logging import get_logger
            logger = get_logger("event_bus")
            logger.error(f"Task '{task.name}' execution failed: {e}")
```

**Step 3: 运行测试**

运行：
```bash
uv run pytest test/test_event_bus.py -v
```

预期：3 个测试通过。

**Step 4: 更新模块入口**

修改 `src/mos/core/task/__init__.py`：

```python
"""任务管理模块"""

from mos.core.task.types import TaskDefinition, TaskTriggerType
from mos.core.task.registry import TaskRegistry
from mos.core.task.event_bus import EventBus

__all__ = [
    "TaskDefinition",
    "TaskTriggerType",
    "TaskRegistry",
    "EventBus",
]
```

**Step 5: 提交代码**

```bash
git add src/mos/core/task/event_bus.py test/test_event_bus.py src/mos/core/task/__init__.py
git commit -m "feat(task): add event bus"
```

---

### Task 6: 进程管理器

**Files:**
- Create: `src/mos/core/task/process_manager.py`
- Create: `test/test_process_manager.py`

**Step 1: 写进程管理器测试**

创建 `test/test_process_manager.py`：

```python
"""进程管理器测试"""

import unittest
import time
import tempfile
import shutil
from pathlib import Path
from mos.core.task.process_manager import ProcessManager


class TestProcessManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.pid_file = Path(self.temp_dir) / "daemon.pid"
        self.log_file = Path(self.temp_dir) / "daemon.log"
        self.manager = ProcessManager(self.pid_file, self.log_file)

    def tearDown(self):
        if self.manager.is_running():
            self.manager.stop()
        shutil.rmtree(self.temp_dir)

    def _simple_target(self):
        """简单的目标函数"""
        time.sleep(2)

    def test_start_and_stop(self):
        """测试启动和停止"""
        self.manager.start(self._simple_target)

        assert self.manager.is_running()
        assert self.pid_file.exists()

        self.manager.stop()

        assert not self.manager.is_running()

    def test_get_status(self):
        """测试获取状态"""
        self.manager.start(self._simple_target)

        status = self.manager.get_status()

        assert status["running"] is True
        assert status["pid"] is not None

        self.manager.stop()

    def test_double_start_error(self):
        """测试重复启动报错"""
        self.manager.start(self._simple_target)

        with self.assertRaises(RuntimeError):
            self.manager.start(self._simple_target)

        self.manager.stop()


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 实现进程管理器**

创建 `src/mos/core/task/process_manager.py`（完整实现见设计文档第 3.5 节）。

**Step 3: 运行测试**

运行：
```bash
uv run pytest test/test_process_manager.py -v
```

预期：3 个测试通过（注意：进程测试可能需要较长时间）。

**Step 4: 提交代码**

```bash
git add src/mos/core/task/process_manager.py test/test_process_manager.py
git commit -m "feat(task): add process manager"
```

---

### Task 7: 调度器（Scheduler）

**Files:**
- Create: `src/mos/core/task/scheduler.py`
- Create: `test/test_scheduler.py`

**Step 1: 写调度器测试**

创建 `test/test_scheduler.py`：

```python
"""调度器测试"""

import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from mos.core.task.scheduler import Scheduler
from mos.core.task.storage.file import FileBackend
from mos.core.task.types import TaskDefinition, TaskTriggerType


class TestScheduler(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = FileBackend(Path(self.temp_dir))
        self.scheduler = Scheduler(self.storage)
        self.executed_count = 0

    def tearDown(self):
        if self.scheduler.is_running():
            self.scheduler.stop()
        shutil.rmtree(self.temp_dir)

    def _increment_func(self):
        """增加计数"""
        self.executed_count += 1

    def test_start_and_stop(self):
        """测试启动和停止"""
        self.scheduler.start()

        assert self.scheduler.is_running()

        self.scheduler.stop()

        assert not self.scheduler.is_running()

    def test_add_interval_task(self):
        """测试添加间隔任务"""
        task = TaskDefinition(
            name="test.interval",
            func=self._increment_func,
            trigger_type=TaskTriggerType.INTERVAL,
            trigger_config={"seconds": 1},
        )

        self.scheduler.start()
        self.scheduler.add_task(task)

        # 验证任务已注册
        loaded = self.storage.load_task("test.interval")
        assert loaded is not None
        assert loaded.name == "test.interval"

        self.scheduler.stop()


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 实现调度器**

创建 `src/mos/core/task/scheduler.py`：

```python
"""任务调度器"""

from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from mos.core.task.types import TaskDefinition, TaskTriggerType
from mos.core.task.storage.base import StorageBackend, TaskRecord
from datetime import datetime


class Scheduler:
    """基于 APScheduler 的任务调度器"""

    def __init__(self, storage_backend: StorageBackend):
        self._scheduler = BackgroundScheduler()
        self._storage = storage_backend
        self._running = False

    def start(self):
        """启动调度器"""
        if not self._running:
            self._load_tasks_from_storage()
            self._scheduler.start()
            self._running = True

    def stop(self):
        """停止调度器"""
        if self._running:
            self._scheduler.shutdown(wait=True)
            self._running = False

    def is_running(self) -> bool:
        """检查调度器是否运行"""
        return self._running

    def add_task(self, task: TaskDefinition):
        """添加任务

        Args:
            task: 任务定义
        """
        if task.trigger_type in (TaskTriggerType.CRON, TaskTriggerType.INTERVAL):
            self._schedule_task(task)

        # 保存到存储
        record = TaskRecord(
            name=task.name,
            trigger_type=task.trigger_type.value,
            trigger_config=task.trigger_config,
            description=task.description,
            enabled=task.enabled,
            max_retries=task.max_retries,
            timeout=task.timeout,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self._storage.save_task(record)

    def remove_task(self, name: str):
        """移除任务

        Args:
            name: 任务名称
        """
        try:
            self._scheduler.remove_job(name)
        except Exception:
            pass  # 任务可能不存在

        self._storage.delete_task(name)

    def _schedule_task(self, task: TaskDefinition):
        """调度单个任务

        Args:
            task: 任务定义
        """
        if task.trigger_type == TaskTriggerType.CRON:
            trigger = CronTrigger.from_crontab(task.trigger_config["cron"])
        elif task.trigger_type == TaskTriggerType.INTERVAL:
            trigger = IntervalTrigger(**task.trigger_config)
        else:
            return

        self._scheduler.add_job(
            task.func,
            trigger,
            id=task.name,
            max_instances=1,
        )

    def _load_tasks_from_storage(self):
        """从存储加载任务"""
        records = self._storage.load_all_tasks()
        for record in records:
            # 注意：这里只加载任务定义，不执行
            # 实际的任务函数需要在插件注册时重新绑定
            pass
```

**Step 3: 运行测试**

运行：
```bash
uv run pytest test/test_scheduler.py -v
```

预期：2 个测试通过。

**Step 4: 提交代码**

```bash
git add src/mos/core/task/scheduler.py test/test_scheduler.py
git commit -m "feat(task): add scheduler based on APScheduler"
```

---

### Task 8: 统一任务管理器（TaskManager）

**Files:**
- Create: `src/mos/core/task/manager.py`
- Create: `test/test_task_manager.py`

**Step 1: 写任务管理器测试**

创建 `test/test_task_manager.py`：

```python
"""任务管理器测试"""

import unittest
import tempfile
import shutil
from pathlib import Path
from mos.core.task.manager import TaskManager, get_task_manager
from mos.core.task.types import TaskDefinition, TaskTriggerType


class TestTaskManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_task_manager_creation(self):
        """测试任务管理器创建"""
        manager = TaskManager(Path(self.temp_dir))

        assert manager.registry is not None
        assert manager.scheduler is not None
        assert manager.event_bus is not None

    def test_add_task(self):
        """测试添加任务"""
        manager = TaskManager(Path(self.temp_dir))

        task = TaskDefinition(
            name="test.task",
            func=lambda: None,
            trigger_type=TaskTriggerType.INTERVAL,
            trigger_config={"seconds": 60},
        )

        manager.add_task(task)

        loaded = manager.registry.get("test.task")
        assert loaded == task

    def test_global_task_manager(self):
        """测试全局任务管理器"""
        manager = get_task_manager()

        assert manager is not None


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 实现任务管理器**

创建 `src/mos/core/task/manager.py`：

```python
"""统一任务管理器"""

from pathlib import Path
from typing import Optional
from mos.core.task.registry import TaskRegistry
from mos.core.task.scheduler import Scheduler
from mos.core.task.event_bus import EventBus
from mos.core.task.process_manager import ProcessManager
from mos.core.task.storage.file import FileBackend
from mos.core.task.types import TaskDefinition


class TaskManager:
    """统一任务管理器，整合所有任务管理组件"""

    def __init__(self, storage_dir: Optional[Path] = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".mos" / "tasks"

        storage_dir.mkdir(parents=True, exist_ok=True)

        self.storage = FileBackend(storage_dir)
        self.registry = TaskRegistry()
        self.scheduler = Scheduler(self.storage)
        self.event_bus = EventBus()
        self.process_manager = ProcessManager(
            storage_dir / "daemon.pid",
            storage_dir / "daemon.log"
        )

        self.event_bus.set_registry(self.registry)

    def add_task(self, task: TaskDefinition):
        """添加任务

        Args:
            task: 任务定义
        """
        self.registry.register(task)
        self.scheduler.add_task(task)

    def remove_task(self, name: str):
        """移除任务

        Args:
            name: 任务名称
        """
        self.registry.unregister(name)
        self.scheduler.remove_task(name)

    def start_foreground(self):
        """前台启动"""
        self.scheduler.start()

    def stop_foreground(self):
        """停止前台运行"""
        self.scheduler.stop()

    def start_daemon(self):
        """守护进程模式启动"""
        self.process_manager.start(self._daemon_target)

    def stop_daemon(self):
        """停止守护进程"""
        self.process_manager.stop()

    def restart_daemon(self):
        """重启守护进程"""
        self.process_manager.restart(self._daemon_target)

    def get_status(self) -> dict:
        """获取任务管理器状态"""
        daemon_status = self.process_manager.get_status()
        return {
            "running": daemon_status["running"],
            "pid": daemon_status["pid"],
            "uptime": daemon_status.get("uptime", 0),
            "task_count": len(self.registry.list_all()),
        }

    def list_tasks(self) -> list:
        """列出所有任务"""
        return self.registry.list_all()

    def enable_task(self, name: str):
        """启用任务"""
        task = self.registry.get(name)
        if task:
            task.enabled = True

    def disable_task(self, name: str):
        """禁用任务"""
        task = self.registry.get(name)
        if task:
            task.enabled = False

    def run_task_now(self, name: str) -> dict:
        """立即执行任务"""
        task = self.registry.get(name)
        if not task:
            return {"success": False, "error": "Task not found"}

        try:
            task.func()
            return {"success": True, "duration": 0}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _daemon_target(self):
        """守护进程目标函数"""
        self.scheduler.start()
        # 保持运行
        import time
        while True:
            time.sleep(60)


# 全局任务管理器实例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取全局任务管理器"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
```

**Step 3: 运行测试**

运行：
```bash
uv run pytest test/test_task_manager.py -v
```

预期：3 个测试通过。

**Step 4: 更新模块入口**

修改 `src/mos/core/task/__init__.py`：

```python
"""任务管理模块"""

from mos.core.task.types import TaskDefinition, TaskTriggerType
from mos.core.task.registry import TaskRegistry
from mos.core.task.event_bus import EventBus
from mos.core.task.manager import TaskManager, get_task_manager

__all__ = [
    "TaskDefinition",
    "TaskTriggerType",
    "TaskRegistry",
    "EventBus",
    "TaskManager",
    "get_task_manager",
]
```

**Step 5: 提交代码**

```bash
git add src/mos/core/task/manager.py test/test_task_manager.py src/mos/core/task/__init__.py
git commit -m "feat(task): add unified task manager"
```

---

## 第四阶段：插件集成

### Task 9: 扩展 PluginDefinition

**Files:**
- Modify: `src/mos/core/plugin.py`
- Create: `test/test_plugin_task_integration.py`

**Step 1: 写插件集成测试**

创建 `test/test_plugin_task_integration.py`：

```python
"""插件任务集成测试"""

import unittest
from mos.core.plugin import PluginDefinition
from mos.core.task.types import TaskDefinition, TaskTriggerType
from mos.core.task.registry import TaskRegistry
from mos.core.task.event_bus import EventBus


class TestPluginTaskIntegration(unittest.TestCase):

    def setUp(self):
        self.registry = TaskRegistry()
        self.event_bus = EventBus()

    def test_plugin_with_register_tasks(self):
        """测试带任务注册的插件"""
        def dummy_register_tasks(registry, event_bus):
            task = TaskDefinition(
                name="plugin.task",
                func=lambda: None,
                trigger_type=TaskTriggerType.INTERVAL,
                trigger_config={"minutes": 5},
            )
            registry.register(task)

        import click
        plugin_def = PluginDefinition(
            name="test_plugin",
            command=click.Group(),
            register_tasks=dummy_register_tasks,
        )

        # 模拟插件加载时调用 register_tasks
        if plugin_def.register_tasks:
            plugin_def.register_tasks(self.registry, self.event_bus)

        assert self.registry.get("plugin.task") is not None


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 修改 PluginDefinition**

修改 `src/mos/core/plugin.py`，在 `PluginDefinition` 类中添加字段：

```python
@dataclass
class PluginDefinition:
    """插件定义"""
    name: str
    command: click.Group
    version: Optional[str] = None
    get_config: Optional[Callable] = None
    init: Optional[Callable] = None
    register_mcp: Optional[Callable] = None
    register_tasks: Optional[Callable] = None  # 新增
```

**Step 3: 运行测试**

运行：
```bash
uv run pytest test/test_plugin_task_integration.py -v
```

预期：测试通过。

**Step 4: 提交代码**

```bash
git add src/mos/core/plugin.py test/test_plugin_task_integration.py
git commit -m "feat(plugin): add register_tasks field to PluginDefinition"
```

---

## 第五阶段：CLI 命令

### Task 10: CLI 任务命令

**Files:**
- Create: `src/mos/cli/task.py`
- Modify: `src/mos/cli/mos.py`

**Step 1: 创建 CLI 命令文件**

创建 `src/mos/cli/task.py`（完整实现见设计文档第 4 节）。

**Step 2: 注册命令**

修改 `src/mos/cli/mos.py`，添加：

```python
from mos.cli.task import task

cli.add_command(task)
```

**Step 3: 测试 CLI 命令**

运行：
```bash
uv run mos task --help
```

预期：显示任务命令帮助信息。

```bash
uv run mos task list
```

预期：显示任务列表（可能为空）。

**Step 4: 提交代码**

```bash
git add src/mos/cli/task.py src/mos/cli/mos.py
git commit -m "feat(cli): add task management commands"
```

---

## 第六阶段：集成测试

### Task 11: 插件加载流程集成

**Files:**
- Modify: `src/mos/cli/mos.py`
- Create: `test/test_integration.py`

**Step 1: 写集成测试**

创建 `test/test_integration.py`：

```python
"""集成测试"""

import unittest
from mos.core.plugin import PluginDefinition, load_entry_point_plugins
from mos.core.task import get_task_manager


class TestIntegration(unittest.TestCase):

    def test_task_manager_singleton(self):
        """测试任务管理器单例"""
        manager1 = get_task_manager()
        manager2 = get_task_manager()

        assert manager1 == manager2


if __name__ == "__main__":
    unittest.main()
```

**Step 2: 运行测试**

运行：
```bash
uv run pytest test/test_integration.py -v
```

预期：测试通过。

**Step 3: 提交代码**

```bash
git add test/test_integration.py
git commit -m "feat(task): add integration tests"
```

---

## 第七阶段：文档和示例

### Task 12: 更新文档

**Files:**
- Modify: `README.md`

**Step 1: 添加任务管理功能说明**

在 `README.md` 中添加后台任务管理章节。

**Step 2: 提交文档**

```bash
git add README.md
git commit -m "docs: add background task management documentation"
```

---

## 完成验证

### 最终测试

运行所有测试：
```bash
uv run pytest test/ -v
```

预期：所有测试通过。

### CLI 功能验证

```bash
# 查看帮助
uv run mos task --help

# 列出任务
uv run mos task list

# 启动（前台）
uv run mos task start

# 查看状态
uv run mos task status
```

---

## 总结

本实施计划共 12 个任务，遵循 TDD 原则，每个任务包含：
1. 编写测试
2. 实现功能
3. 验证测试
4. 提交代码

预计实现时间：4-6 小时。

**关键里程碑：**
- Task 1-4: 核心数据结构和存储（基础）
- Task 5-8: 核心组件（事件、进程、调度、管理器）
- Task 9: 插件集成
- Task 10: CLI 命令
- Task 11-12: 集成测试和文档
