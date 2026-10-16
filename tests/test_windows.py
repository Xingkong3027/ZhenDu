"""Real Windows registry checks in an isolated namespace, never Explorer's keys."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from zhendu.config import JobConfig, Store
from zhendu.language import UserError
from zhendu.shell import CLASSES, MENU_KEY, OWNER_KEY, Registry, ShellIntegration


class IsolatedRegistry:
    def __init__(self):
        self.registry = Registry()
        self.root = "Software\\ZhenDu\\IntegrationTests\\" + uuid.uuid4().hex

    def set(self, path, name, value):
        self.registry.set(self.root + "\\" + path, name, value)

    def get(self, path, name):
        return self.registry.get(self.root + "\\" + path, name)

    def delete_tree(self, path):
        self.registry.delete_tree(self.root + "\\" + path)

    def close(self):
        self.registry.delete_tree(self.root)


@unittest.skipUnless(os.name == "nt", "Windows only")
class WindowsTests(unittest.TestCase):
    def test_real_registry_presets_version_ownership_and_removal(self):
        registry = IsolatedRegistry()
        try:
            with tempfile.TemporaryDirectory() as directory, patch.object(ShellIntegration, "notify"):
                store = Store(directory)
                first = ShellIntegration(store, registry, Path(directory) / "first")
                second = ShellIntegration(store, registry, Path(directory) / "second")
                first.register()
                first.register()
                preset = store.save_preset("自定义右键压缩 · Custom", JobConfig(compress=True))
                first.refresh_if_owned()
                key = CLASSES + MENU_KEY + "\\shell\\004-" + preset["id"]
                self.assertEqual(registry.get(key, "MUIVerb"), preset["name"])
                command = registry.get(key + "\\command", "")
                self.assertIn('--preset ' + preset["id"] + ' --run "%1"', command)
                self.assertIn("pythonw.exe", command)
                store.data["presets"] = [item for item in store.presets if item["id"] != preset["id"]]
                first.refresh_if_owned()
                self.assertIsNone(registry.get(key, "MUIVerb"))
                second.register()
                self.assertFalse(first.owns_menu())
                with self.assertRaises(UserError):
                    first.unregister()
                second.unregister()
                self.assertIsNone(registry.get(OWNER_KEY, "Instance"))
                self.assertIsNone(registry.get(CLASSES + MENU_KEY + "\\shell\\000-open\\command", ""))
        finally:
            registry.close()


if __name__ == "__main__":
    unittest.main()
