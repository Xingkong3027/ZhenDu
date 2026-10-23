from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from zhendu.config import JobConfig, Store
from zhendu.language import UserError
from zhendu.source_settings import DEFAULT_SYNC, SourceSettings, config_from_draft, draft_from_config


class SourceSettingsTests(unittest.TestCase):
    def setUp(self):
        self.model = SourceSettings(draft_from_config(JobConfig()), DEFAULT_SYNC)
        self.model.add("a")
        self.model.add("b")

    def test_default_compression_shared_trim_split_independent(self):
        values = self.model.get("a")
        values.update(quality=29, clip=True, clip_start="2", clip_end="8", split=True, split_count=4)
        self.model.update("a", values)
        other = self.model.get("b")
        self.assertEqual(other["quality"], 29)
        self.assertFalse(other["clip"])
        self.assertFalse(other["split"])
        self.assertTrue(self.model.get("a")["clip"])

    def test_enable_sync_copies_current_and_disable_preserves_values(self):
        values = self.model.get("a")
        values.update(split=True, split_mode="size", split_size_mb=42)
        self.model.update("a", values)
        self.model.set_sync("split", True, values)
        self.assertEqual(self.model.get("b")["split_size_mb"], 42)
        self.model.set_sync("split", False, values)
        values["split_size_mb"] = 100
        self.model.update("a", values)
        self.assertEqual(self.model.get("b")["split_size_mb"], 42)

    def test_unsynced_new_source_does_not_inherit_previous_trim_or_split(self):
        values = self.model.get("a")
        values.update(quality=33, clip=True, clip_start="12", clip_end="15", split=True)
        self.model.update("a", values)
        self.model.add("c")
        self.assertEqual(self.model.get("c")["quality"], 33)
        self.assertFalse(self.model.get("c")["clip"])
        self.assertFalse(self.model.get("c")["split"])

    def test_unfinished_text_is_preserved_and_only_active_fields_validate(self):
        values = self.model.get("a")
        values.update(clip_start="unfinished", split_duration="unfinished")
        self.model.update("a", values)
        config_from_draft(self.model.get("a"))
        values.update(split=True, split_mode="count")
        config_from_draft(values)
        values["split_mode"] = "duration"
        with self.assertRaises(UserError):
            config_from_draft(values)
        self.assertEqual(self.model.get("a")["clip_start"], "unfinished")
        values.update(compress=False, advanced=True, width=1919, split=False)
        self.assertEqual(config_from_draft(values).width, 0)

    def test_blank_end_uses_each_videos_own_duration_and_snapshots_are_independent(self):
        values = self.model.get("a")
        values.update(clip=True, clip_start="1", clip_end="")
        self.model.set_sync("clip", True, values)
        short = config_from_draft(self.model.get("b"))
        long = config_from_draft(self.model.get("a"))
        self.assertEqual(short.bounds(4), (1, 4))
        self.assertEqual(long.bounds(18), (1, 18))
        captured = asdict(long)
        values["quality"] = 40
        self.model.update("a", values)
        self.assertEqual(asdict(long), captured)

    def test_sync_settings_migration_and_invalid_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root)
            self.assertEqual(store.data["sync_settings"], DEFAULT_SYNC)
            store.data["sync_settings"] = {"compression": False, "clip": "false", "split": True}
            store.save()
            restored = Store(root)
            self.assertEqual(restored.data["sync_settings"], {"compression": False, "clip": False, "split": True})


if __name__ == "__main__":
    unittest.main()
