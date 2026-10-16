from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zhendu.config import JobConfig, Store, atomic_json, parse_time
from zhendu.engine import encoding_args
from zhendu.language import UserError, system_language
from zhendu.media import MediaInfo
from zhendu.process import Runner
from zhendu.shell import APP_ID, CLASSES, MENU_KEY, OWNER_KEY, ShellIntegration


class MemoryRegistry:
    def __init__(self):
        self.values = {}

    def set(self, path, name, value):
        self.values[(path, name)] = str(value)

    def get(self, path, name):
        return self.values.get((path, name))

    def delete_tree(self, path):
        self.values = {key: value for key, value in self.values.items() if not (key[0] == path or key[0].startswith(path + "\\"))}


class CoreTests(unittest.TestCase):
    def test_language_rules(self):
        for language_id in (0x0804, 0x0404, 0x0C04, 0x1004, 0x1404):
            self.assertEqual(system_language(language_id), "zh_CN")
        for language_id in (0x0409, 0x0411, 0x0407):
            self.assertEqual(system_language(language_id), "en")

    def test_times_and_validation(self):
        self.assertEqual(parse_time("01:02:03.125"), 3723.125)
        self.assertEqual(parse_time("90.5"), 90.5)
        for invalid in ("nan", "inf", "-1", "00:61:00", "1:70", "bad"):
            with self.assertRaises(ValueError):
                parse_time(invalid)
        with self.assertRaises(UserError):
            JobConfig(compress=True, width=1919).validate()
        with self.assertRaises(UserError):
            JobConfig(clip=True, clip_start=10, clip_end=9).validate()

    def test_copy_mode_cannot_encode_video_from_stale_controls(self):
        config = JobConfig(width=1920, fps=30, color_range="full", audio_mode="encode")
        config.validate()
        self.assertEqual((config.width, config.fps, config.color_range), (0, 0, "source"))
        info = MediaInfo("input.mp4", 20, 100, 640, 360, 30, 0, "h264")
        args = encoding_args(config, info, ".mp4")
        self.assertEqual(args[args.index("-c:v") + 1], "copy")
        self.assertEqual(args[args.index("-c:a") + 1], "aac")

    def test_presets_roundtrip_without_old_ab(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            preset = store.save_preset("测试 · Upload", JobConfig(compress=True, clip=True, clip_start=12, clip_end=18, split=True), include_task=True)
            self.assertNotIn("clip_start", preset["settings"])
            self.assertTrue(preset["settings"]["split"])
            again = Store(directory)
            self.assertEqual(again.get_preset(preset["id"])["name"], "测试 · Upload")
            self.assertEqual(again.get_preset(preset["id"])["settings"]["codec"], "h264")

    def test_atomic_save_preserves_previous_data_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            atomic_json(path, {"value": 1})
            with patch("zhendu.config.os.replace", side_effect=OSError("interrupted")):
                with self.assertRaises(OSError):
                    atomic_json(path, {"value": 2})
            self.assertEqual(json.loads(path.read_text())["value"], 1)
            self.assertEqual(len(list(Path(directory).glob("*.tmp"))), 0)

    def test_menu_updates_ownership_and_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            registry = MemoryRegistry()
            registry.set(CLASSES + "OtherApp", "", "keep")
            first = ShellIntegration(store, registry, Path(directory) / "version1")
            second = ShellIntegration(store, registry, Path(directory) / "version2")
            with patch.object(ShellIntegration, "notify"):
                first.register()
                first.register()
                self.assertTrue(first.owns_menu())
                commands = [value for (key, name), value in registry.values.items() if key.endswith("\\command")]
                self.assertTrue(any('--preset builtin-everyday --run "%1"' in value for value in commands))
                self.assertFalse(any("cmd.exe" in value for value in commands))
                second.register()
                with self.assertRaises(UserError):
                    first.unregister()
                self.assertTrue(second.owns_menu())
                second.unregister()
            self.assertFalse(second.owner())
            self.assertEqual(registry.get(CLASSES + "OtherApp", ""), "keep")
            self.assertFalse(any(MENU_KEY in path or APP_ID in path for path, _ in registry.values))

    def test_probe_timeout_reaps_process(self):
        import sys
        runner = Runner()
        with self.assertRaises(TimeoutError):
            runner.capture([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.25)
        self.assertFalse(runner.processes)

    def test_future_settings_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            original = '{"schema_version": 99, "future": true}'
            path.write_text(original, encoding="utf-8")
            with self.assertRaises(UserError):
                Store(directory)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_windows_processes_have_no_console(self):
        import sys
        if os.name != "nt":
            self.skipTest("Windows only")
        output = Runner().capture([sys.executable, "-c", "import ctypes; print(ctypes.windll.kernel32.GetConsoleWindow())"])
        self.assertEqual(output.strip(), "0")


if __name__ == "__main__":
    unittest.main()
