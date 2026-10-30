from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from zhendu.output_sizes import OutputSizes, format_size
from zhendu.process import Runner


class SizeTests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(1024), "1.00 KiB")
        self.assertEqual(format_size(1024**2 * 2), "2.00 MiB")

    def test_only_video_outputs_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, size in {"part1.mp4": 20, "part2.mp4": 30, ".selected_range.mp4": 90,
                               ".encoding.mp4": 70, "analysis.log": 400}.items():
                (root / name).write_bytes(b"x" * size)
            (root / "folder.mp4").mkdir()
            tracker = OutputSizes(root, ".mp4")
            self.assertEqual(tracker.snapshot()["part_sizes"], {"part1.mp4": 20, "part2.mp4": 30})
            self.assertEqual(tracker.snapshot()["output_size"], 50)

    def test_remux_and_retry_are_not_counted_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "part1.mp4").write_bytes(b"x" * 20)
            (root / "part2.mp4").write_bytes(b"x" * 100)
            (root / ".encoding.mp4").write_bytes(b"x" * 80)
            tracker = OutputSizes(root, ".mp4")
            tracker.part("part2.mp4", encoding=False)
            self.assertEqual(tracker.snapshot()["output_size"], 120)
            tracker.part("part2.mp4", encoding=True)
            self.assertEqual(tracker.snapshot()["part_sizes"]["part2.mp4"], 80)
            self.assertEqual(tracker.snapshot()["output_size"], 100)

    def test_throttle_force_and_read_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "part.mp4"
            target.write_bytes(b"a")
            tracker = OutputSizes(directory, ".mp4")
            self.assertEqual(tracker.snapshot()["output_size"], 1)
            target.write_bytes(b"abc")
            self.assertEqual(tracker.snapshot()["output_size"], 1)
            self.assertEqual(tracker.snapshot(force=True)["output_size"], 3)
            with patch("zhendu.output_sizes.os.scandir", side_effect=PermissionError):
                self.assertEqual(tracker.snapshot(force=True)["output_size"], 3)

    def test_silent_process_still_ticks(self):
        ticks = []
        runner = Runner()
        self.assertEqual(list(runner.lines([sys.executable, "-c", "import time; time.sleep(1.3)"],
                                           tick=lambda: ticks.append(time.monotonic()))), [])
        self.assertGreaterEqual(len(ticks), 3)
        self.assertFalse(runner.processes)


if __name__ == "__main__":
    unittest.main()
