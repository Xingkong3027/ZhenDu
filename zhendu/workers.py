from dataclasses import dataclass
import queue
import threading

from PySide6.QtCore import QObject, QRunnable, QThread, Signal

from .config import JobConfig
from .engine import Engine
from .language import UserError, t
from .process import Cancelled, Runner


class ProbeSignals(QObject):
    ready = Signal(str, object)
    failed = Signal(str, str)


class ProbeTask(QRunnable):
    def __init__(self, path, cache):
        super().__init__()
        self.path, self.cache = path, cache
        self.signals = ProbeSignals()
        self.runner = Runner()

    def run(self):
        try:
            self.signals.ready.emit(self.path, self.cache.get(self.path, self.runner))
        except Cancelled:
            pass
        except Exception as error:
            self.signals.failed.emit(self.path, error.localized() if isinstance(error, UserError) else str(error))


@dataclass
class Task:
    identifier: str
    source: str
    config: JobConfig
    output_root: str = ""
    task_subfolders: bool = False
    history_root: str = ""


class TaskWorker(QThread):
    started_task = Signal(str, str)
    progress = Signal(str, object)
    completed = Signal(str, object)
    failed = Signal(str, str, bool)
    log = Signal(str)

    def __init__(self, tasks, cache, parent=None):
        super().__init__(parent)
        self.tasks, self.cache = tasks, cache
        self.stop_event = threading.Event()
        self.engine = None

    def cancel(self):
        self.stop_event.set()
        if self.engine:
            self.engine.cancel()

    def run(self):
        while not self.stop_event.is_set():
            try:
                task = self.tasks.get(timeout=0.25)
            except queue.Empty:
                return
            try:
                self.started_task.emit(task.identifier, task.source)
                self.engine = Engine(self.cache, progress=lambda value: self.progress.emit(task.identifier, value), log=self.log.emit)
                if self.stop_event.is_set():
                    self.engine.cancel()
                result = self.engine.process(task.source, task.config, task.output_root or None,
                                             task_subfolders=task.task_subfolders, history_root=task.history_root or None)
                self.completed.emit(task.identifier, result)
            except Cancelled:
                self.failed.emit(task.identifier, t("已取消", "Cancelled"), True)
            except Exception as error:
                self.failed.emit(task.identifier, error.localized() if isinstance(error, UserError) else str(error), False)
            finally:
                self.engine = None
                self.tasks.task_done()
