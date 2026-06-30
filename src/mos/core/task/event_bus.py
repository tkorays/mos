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
