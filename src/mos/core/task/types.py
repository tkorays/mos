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
