"""任务注册表"""

from typing import Dict, List, Optional
from mos.core.task.types import TaskDefinition, TaskTriggerType


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
