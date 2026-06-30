"""存储后端模块"""

from mos.core.task.storage.base import StorageBackend, TaskRecord, TaskExecutionLog
from mos.core.task.storage.file import FileBackend

__all__ = ["StorageBackend", "TaskRecord", "TaskExecutionLog", "FileBackend"]
