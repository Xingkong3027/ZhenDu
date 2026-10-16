import os
import queue
import subprocess
import threading
import time


class Cancelled(Exception):
    pass


def hidden_process_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


class Runner:
    def __init__(self, log=lambda message: None):
        self.log = log
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.processes = set()

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled()

    def start(self, args):
        self.check()
        process = subprocess.Popen([str(arg) for arg in args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                   **hidden_process_options())
        with self.lock:
            self.processes.add(process)
        if self.cancelled.is_set():
            process.terminate()
        return process

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            processes = list(self.processes)
        for process in processes:
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass

    def finish(self, process):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for stream in (process.stdout, process.stderr):
            if stream:
                stream.close()
        with self.lock:
            self.processes.discard(process)

    def capture(self, args, timeout=30):
        process = self.start(args)
        deadline = time.monotonic() + timeout
        try:
            while True:
                self.check()
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Process timed out after {timeout}s")
                try:
                    stdout, stderr = process.communicate(timeout=0.15)
                    self.check()
                    if process.returncode:
                        raise RuntimeError(stderr.strip()[-4000:] or f"Exit code {process.returncode}")
                    return stdout
                except subprocess.TimeoutExpired:
                    continue
        finally:
            self.finish(process)

    def lines(self, args, timeout=None):
        process = self.start(args)
        messages = queue.Queue(maxsize=128)
        errors = []
        finished = threading.Event()
        stopped = threading.Event()
        started = time.monotonic()

        def stdout_reader():
            try:
                for line in process.stdout:
                    while not self.cancelled.is_set() and not stopped.is_set():
                        try:
                            messages.put(line.rstrip("\r\n"), timeout=0.1)
                            break
                        except queue.Full:
                            continue
            except (OSError, ValueError):
                pass
            finally:
                finished.set()

        def stderr_reader():
            try:
                for line in process.stderr:
                    text = line.rstrip()
                    errors.append(text)
                    del errors[:-40]
                    if text:
                        self.log(text)
            except (OSError, ValueError):
                pass

        stdout_thread = threading.Thread(target=stdout_reader, daemon=True)
        stderr_thread = threading.Thread(target=stderr_reader, daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        try:
            while not finished.is_set() or not messages.empty():
                self.check()
                if timeout and time.monotonic() - started > timeout:
                    raise TimeoutError("Process timed out")
                try:
                    yield messages.get(timeout=0.1)
                except queue.Empty:
                    pass
            process.wait(timeout=5)
            stderr_thread.join(timeout=2)
            self.check()
            if process.returncode:
                raise RuntimeError("\n".join(errors)[-4000:] or f"Exit code {process.returncode}")
        finally:
            stopped.set()
            self.finish(process)
            stdout_thread.join(timeout=2)
            stderr_thread.join(timeout=2)
