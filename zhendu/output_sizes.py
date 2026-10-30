"""Measure logical video outputs without counting analysis or remux duplicates."""
import os
import time


def format_size(size):
    value = max(0, int(size))
    if value < 1024:
        return f"{value} B"
    amount = float(value)
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        amount /= 1024
        if amount < 1024 or unit == "TiB":
            return f"{amount:.2f} {unit}"


class OutputSizes:
    def __init__(self, directory, extension):
        self.directory = directory
        self.extension = extension
        self.current_part = None
        self.encoding = False
        self._sampled = 0.0
        self._cached = {"output_size": 0, "part_sizes": {}}

    def part(self, name, encoding):
        self.current_part, self.encoding = name, encoding
        self._sampled = 0.0

    def snapshot(self, force=False):
        now = time.monotonic()
        if not force and now - self._sampled < 0.4:
            return self._cached
        parts, temporary = {}, None
        try:
            with os.scandir(self.directory) as entries:
                for entry in entries:
                    if not entry.name.endswith(self.extension):
                        continue
                    try:
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        size = entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
                    if entry.name == ".encoding" + self.extension:
                        temporary = size
                    elif not entry.name.startswith("."):
                        parts[entry.name] = size
        except OSError:
            # A transient directory read failure must not stop video processing.
            return self._cached
        if self.current_part and temporary is not None:
            parts[self.current_part] = temporary if self.encoding else max(temporary, parts.get(self.current_part, 0))
        self._cached = {"output_size": sum(parts.values()), "part_sizes": parts}
        self._sampled = now
        return self._cached
