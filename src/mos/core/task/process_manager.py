"""进程管理器"""

import threading
from pathlib import Path
from typing import Callable, Optional, Dict, Any


class ProcessManager:
    """守护进程管理器（使用线程模拟）"""

    def __init__(self, pid_file: Path, log_file: Path):
        self.pid_file = pid_file
        self.log_file = log_file
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self, target: Callable, args=()):
        """启动守护进程

        Args:
            target: 目标函数
            args: 函数参数

        Raises:
            RuntimeError: 如果进程已运行
        """
        if self.is_running():
            raise RuntimeError("Daemon process is already running")

        self._running = True
        self._thread = threading.Thread(
            target=self._run_with_logging,
            args=(target, args),
            name="mos-daemon",
            daemon=True
        )
        self._thread.start()
        self._save_pid()

    def stop(self):
        """停止守护进程"""
        self._running = False

        if self._thread and self._thread.is_alive():
            # 等待线程结束（最多等待10秒）
            self._thread.join(timeout=10)

        self._thread = None

        if self.pid_file.exists():
            self.pid_file.unlink()

    def restart(self, target: Callable, args=()):
        """重启守护进程

        Args:
            target: 目标函数
            args: 函数参数
        """
        self.stop()
        self.start(target, args)

    def is_running(self) -> bool:
        """检查守护进程是否在运行"""
        return self._running

    def get_status(self) -> Dict[str, Any]:
        """获取守护进程状态

        Returns:
            状态字典，包含 running、pid、uptime 等
        """
        running = self.is_running()
        pid = None

        if running and self._thread:
            # 线程没有 pid，使用主进程 pid
            import os
            pid = os.getpid()

        return {
            "running": running,
            "pid": pid,
            "uptime": 0,  # TODO: 计算实际运行时间
        }

    def _run_with_logging(self, target: Callable, args):
        """运行目标函数并记录日志

        Args:
            target: 目标函数
            args: 函数参数
        """
        try:
            target(*args)
        except Exception as e:
            # 记录错误日志
            from mos.core.logging import get_logger
            logger = get_logger("process_manager")
            logger.error(f"Daemon process error: {e}")

    def _save_pid(self):
        """保存 PID 到文件"""
        if self._thread:
            import os
            with open(self.pid_file, "w") as f:
                f.write(str(os.getpid()))
