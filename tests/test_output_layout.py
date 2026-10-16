"""Real output layout, name collision and failed-publication regressions."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zhendu.config import JobConfig, Store
from zhendu.engine import Engine, publish_file
from zhendu.paths import media_binary
from zhendu.process import Cancelled, Runner


class OutputLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_root = tempfile.TemporaryDirectory()
        cls.sample = Path(cls.media_root.name) / "sample.mp4"
        Runner().capture([media_binary("ffmpeg.exe"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=12",
                          "-t", "4", "-c:v", "libx264", "-preset", "ultrafast", "-g", "12", str(cls.sample)])

    @classmethod
    def tearDownClass(cls):
        cls.media_root.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "video.mp4"
        self.source.write_bytes(self.sample.read_bytes())
        self.original = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.history = self.root / "settings" / "tasks"

    def process(self, config=None, output=None, **kwargs):
        result = Engine().process(self.source, config or JobConfig(), output, history_root=self.history, **kwargs)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.original)
        for path in result.outputs:
            Runner().capture([media_binary("ffmpeg.exe"), "-v", "error", "-i", path, "-f", "null", "-"])
        return result

    def test_default_next_to_source_without_output_folder(self):
        result = self.process()
        self.assertEqual(Path(result.directory), self.root)
        self.assertEqual([Path(path).name for path in result.outputs], ["video_ZhenDu.mp4"])
        self.assertFalse((self.root / "帧渡输出").exists())
        self.assertEqual({p.name for p in self.root.iterdir()}, {"video.mp4", "video_ZhenDu.mp4", "settings"})
        self.assertTrue(Path(result.manifest).is_relative_to(self.history))

    def test_selected_folder_contains_only_videos_and_never_overwrites(self):
        target = self.root / "selected"
        target.mkdir()
        protected = target / "video_ZhenDu.mp4"
        protected.write_bytes(b"keep existing file")
        first = self.process(output=target)
        second = self.process(output=target)
        self.assertEqual(protected.read_bytes(), b"keep existing file")
        self.assertEqual(Path(first.outputs[0]).name, "video_ZhenDu_2.mp4")
        self.assertEqual(Path(second.outputs[0]).name, "video_ZhenDu_3.mp4")
        self.assertTrue(all(path.is_file() and path.suffix == ".mp4" for path in target.iterdir()))

    def test_split_outputs_directly_in_selected_folder(self):
        target = self.root / "split"
        result = self.process(JobConfig(split=True, split_count=2), target)
        self.assertEqual(len(result.outputs), 2)
        self.assertEqual({Path(p).parent for p in result.outputs}, {target})
        self.assertEqual(len(list(target.iterdir())), 2)

    def test_enabled_mode_preserves_original_layout_and_manifest(self):
        result = self.process(task_subfolders=True)
        directory = Path(result.directory)
        self.assertEqual(directory.parent, self.root / "帧渡输出")
        self.assertEqual(Path(result.manifest), directory / "task.json")
        self.assertEqual({p.name for p in directory.iterdir()}, {"video.mp4", "task.json"})

    def test_cancelled_job_leaves_no_output_folder_or_partial_video(self):
        target = self.root / "cancelled"
        with patch.object(Engine, "single_or_timed", side_effect=Cancelled()):
            with self.assertRaises(Cancelled):
                self.process(output=target)
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(len(list(self.history.glob("*.failed.json"))), 1)

    def test_partial_publish_failure_removes_only_this_jobs_outputs(self):
        target = self.root / "failure"
        target.mkdir()
        protected = target / "existing.mp4"
        protected.write_bytes(b"keep me")
        calls = []

        def failing_publish(*args):
            calls.append(args)
            if len(calls) == 2:
                raise OSError("simulated destination failure")
            return publish_file(*args)

        with patch("zhendu.engine.publish_file", side_effect=failing_publish):
            with self.assertRaises(OSError):
                self.process(JobConfig(split=True, split_count=2), target)
        self.assertEqual(list(target.iterdir()), [protected])
        self.assertEqual(protected.read_bytes(), b"keep me")

    def test_settings_default_migrate_and_persist(self):
        settings = self.root / "config"
        store = Store(settings)
        self.assertIs(store.data["task_subfolders"], False)
        store.save()
        old = json.loads(store.path.read_text(encoding="utf-8"))
        old.pop("task_subfolders")
        store.path.write_text(json.dumps(old), encoding="utf-8")
        self.assertIs(Store(settings).data["task_subfolders"], False)
        store.data["task_subfolders"] = True
        store.save()
        self.assertIs(Store(settings).data["task_subfolders"], True)

    def test_unwritable_history_does_not_discard_completed_video(self):
        with patch("zhendu.engine.atomic_json", side_effect=PermissionError("history unavailable")):
            result = self.process()
        self.assertTrue(Path(result.outputs[0]).is_file())
