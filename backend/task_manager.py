import threading, uuid, logging
from queue import Queue
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class DownloadTask:
    def __init__(self, task_id, track_ids):
        self.id = task_id
        self.track_ids = track_ids
        self.status = "pending"
        self.current_track: Optional[str] = None
        self.completed = 0
        self.failed = 0
        self.total = len(track_ids)
        self.errors = []
        self.created_at = datetime.utcnow().isoformat()
        self.event_queue: Queue = Queue()
        self._cancel = threading.Event()

    def emit(self, event):
        event["task_id"] = self.id
        self.event_queue.put(event)

    def cancel(self):
        self._cancel.set()
        self.status = "cancelled"
        self.emit({"type": "cancelled"})

    @property
    def is_cancelled(self):
        return self._cancel.is_set()

    def to_dict(self):
        pct = (self.completed + self.failed) / self.total * 100 if self.total else 0
        return {
            "id": self.id, "status": self.status,
            "current_track": self.current_track,
            "completed": self.completed, "failed": self.failed,
            "total": self.total, "percentage": round(pct, 2),
            "errors": self.errors[-5:], "created_at": self.created_at,
        }
    current_track = None
    current_track = None

class TaskManager:
    def __init__(self):
        self._tasks: Dict[str, DownloadTask] = {}
        self._lock = threading.Lock()

    def create(self, track_ids):
        tid = uuid.uuid4().hex[:12]
        t = DownloadTask(tid, track_ids)
        with self._lock:
            self._tasks[tid] = t
        return t

    def get(self, tid):
        return self._tasks.get(tid)

    def list(self):
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

manager = TaskManager()
