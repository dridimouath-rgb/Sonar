# backend/log_capture.py
import logging
import queue

_log_queue: "queue.Queue[str]" = queue.Queue(maxsize=2000)


class QueueLogHandler(logging.Handler):
    """Routes every log record into a shared queue consumed by the SSE endpoint."""

    def __init__(self):
        super().__init__()
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record):
        try:
            msg = self.format(record)
            try:
                _log_queue.put_nowait(msg)
            except queue.Full:
                try:
                    _log_queue.get_nowait()   # drop oldest
                except queue.Empty:
                    pass
                try:
                    _log_queue.put_nowait(msg)
                except queue.Full:
                    pass
        except Exception:
            pass


def install_log_handler():
    """Attach the handler to root + spotdl loggers exactly once."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for h in root.handlers:
        if isinstance(h, QueueLogHandler):
            return

    handler = QueueLogHandler()
    handler.setLevel(logging.INFO)
    root.addHandler(handler)

    # spotdl often uses its own loggers; force them to propagate at INFO
    for name in ("spotdl", "spotdl.download", "spotdl.providers"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)
        lg.propagate = True


def get_log_queue() -> "queue.Queue[str]":
    return _log_queue