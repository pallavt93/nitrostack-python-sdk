import datetime
import asyncio
from typing import Dict, List, Any, Optional
import mcp.types as types

class TaskEntry:
    def __init__(self, task_id: str, ttl: Optional[int] = None):
        self.task_id = task_id
        self.status: str = "working"
        self.status_message: str = "Task started"
        self.created_at = datetime.datetime.now(datetime.timezone.utc)
        self.last_updated_at = self.created_at
        self.ttl = ttl if ttl is not None else 300
        self.poll_interval = 5
        self.result: Any = None
        self.error: Any = None
        self.is_cancelled: bool = False
        self.done_event = asyncio.Event()

class TaskRegistry:
    _tasks: Dict[str, TaskEntry] = {}
    
    @classmethod
    def create_task(cls, task_id: str, ttl: Optional[int] = None) -> TaskEntry:
        entry = TaskEntry(task_id, ttl)
        cls._tasks[task_id] = entry
        return entry

    @classmethod
    def get_task(cls, task_id: str) -> Optional[TaskEntry]:
        return cls._tasks.get(task_id)

    @classmethod
    def list_tasks(cls) -> List[TaskEntry]:
        return list(cls._tasks.values())

    @classmethod
    def update_progress(cls, task_id: str, message: str) -> None:
        entry = cls.get_task(task_id)
        if entry:
            entry.status_message = message
            entry.last_updated_at = datetime.datetime.now(datetime.timezone.utc)

    @classmethod
    def cancel_task(cls, task_id: str) -> None:
        entry = cls.get_task(task_id)
        if entry:
            entry.is_cancelled = True
            entry.status = "cancelled"
            entry.status_message = "Task cancelled by client"
            entry.last_updated_at = datetime.datetime.now(datetime.timezone.utc)
            entry.done_event.set()

    @classmethod
    def is_task_cancelled(cls, task_id: str) -> bool:
        entry = cls.get_task(task_id)
        return entry.is_cancelled if entry else False

    @classmethod
    def complete_task(cls, task_id: str, result: Any) -> None:
        entry = cls.get_task(task_id)
        if entry:
            if not entry.is_cancelled:
                entry.status = "completed"
                entry.status_message = "Task completed successfully"
                entry.result = result
            entry.last_updated_at = datetime.datetime.now(datetime.timezone.utc)
            entry.done_event.set()

    @classmethod
    def fail_task(cls, task_id: str, error: Any) -> None:
        entry = cls.get_task(task_id)
        if entry:
            if not entry.is_cancelled:
                entry.status = "failed"
                entry.status_message = f"Task failed: {error}"
                entry.error = error
            entry.last_updated_at = datetime.datetime.now(datetime.timezone.utc)
            entry.done_event.set()
