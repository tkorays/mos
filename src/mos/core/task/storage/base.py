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
