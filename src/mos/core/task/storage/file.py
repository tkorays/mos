"""文件系统存储后端"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from mos.core.task.storage.base import StorageBackend, TaskRecord, TaskExecutionLog


class FileBackend(StorageBackend):
    """文件系统存储后端"""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.tasks_file = storage_dir / "tasks.json"
        self.logs_dir = storage_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        self.daemon_status_file = storage_dir / "daemon_status.json"

    def save_task(self, task: TaskRecord) -> None:
        """保存任务定义"""
        tasks = self._load_tasks_dict()

        task_dict = {
            "name": task.name,
            "trigger_type": task.trigger_type,
            "trigger_config": task.trigger_config,
            "description": task.description,
            "enabled": task.enabled,
            "max_retries": task.max_retries,
            "timeout": task.timeout,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }

        tasks[task.name] = task_dict

        with open(self.tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

    def load_task(self, name: str) -> Optional[TaskRecord]:
        """加载任务定义"""
        tasks = self._load_tasks_dict()

        if name not in tasks:
            return None

        task_dict = tasks[name]
        return TaskRecord(
            name=task_dict["name"],
            trigger_type=task_dict["trigger_type"],
            trigger_config=task_dict["trigger_config"],
            description=task_dict["description"],
            enabled=task_dict["enabled"],
            max_retries=task_dict["max_retries"],
            timeout=task_dict["timeout"],
            created_at=datetime.fromisoformat(task_dict["created_at"]),
            updated_at=datetime.fromisoformat(task_dict["updated_at"]),
        )

    def load_all_tasks(self) -> List[TaskRecord]:
        """加载所有任务"""
        tasks = self._load_tasks_dict()
        records = []

        for name in tasks:
            record = self.load_task(name)
            if record:
                records.append(record)

        return records

    def delete_task(self, name: str) -> None:
        """删除任务"""
        tasks = self._load_tasks_dict()

        if name in tasks:
            del tasks[name]

            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)

    def save_execution_log(self, log: TaskExecutionLog) -> None:
        """保存执行日志"""
        log_file = self.logs_dir / f"{log.task_name}.jsonl"

        log_dict = {
            "id": log.id,
            "task_name": log.task_name,
            "started_at": log.started_at.isoformat(),
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
            "status": log.status,
            "error": log.error,
            "duration": log.duration,
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_dict, ensure_ascii=False) + "\n")

    def load_execution_logs(
        self,
        task_name: Optional[str] = None,
        limit: int = 100
    ) -> List[TaskExecutionLog]:
        """加载执行日志"""
        logs = []

        if task_name:
            log_file = self.logs_dir / f"{task_name}.jsonl"
            if log_file.exists():
                logs.extend(self._read_jsonl_file(log_file, limit))
        else:
            # 加载所有日志文件
            for log_file in self.logs_dir.glob("*.jsonl"):
                logs.extend(self._read_jsonl_file(log_file, limit))

        # 按时间倒序排序
        logs.sort(key=lambda x: x.started_at, reverse=True)

        return logs[:limit]

    def save_daemon_status(self, status: Dict[str, Any]) -> None:
        """保存守护进程状态"""
        status_dict = status.copy()
        status_dict["updated_at"] = datetime.now().isoformat()

        with open(self.daemon_status_file, "w", encoding="utf-8") as f:
            json.dump(status_dict, f, ensure_ascii=False, indent=2)

    def load_daemon_status(self) -> Optional[Dict[str, Any]]:
        """加载守护进程状态"""
        if not self.daemon_status_file.exists():
            return None

        with open(self.daemon_status_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_tasks_dict(self) -> Dict[str, Any]:
        """加载任务字典"""
        if not self.tasks_file.exists():
            return {}

        with open(self.tasks_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _read_jsonl_file(self, file_path: Path, limit: int) -> List[TaskExecutionLog]:
        """读取 JSONL 文件"""
        logs = []

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # 读取最后 limit 行
        recent_lines = lines[-limit:] if len(lines) > limit else lines

        for line in recent_lines:
            if not line.strip():
                continue

            log_dict = json.loads(line)
            logs.append(TaskExecutionLog(
                id=log_dict["id"],
                task_name=log_dict["task_name"],
                started_at=datetime.fromisoformat(log_dict["started_at"]),
                finished_at=datetime.fromisoformat(log_dict["finished_at"]) if log_dict["finished_at"] else None,
                status=log_dict["status"],
                error=log_dict["error"],
                duration=log_dict["duration"],
            ))

        return logs
