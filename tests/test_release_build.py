import tempfile
import unittest
from pathlib import Path

from release_config import release_artifact_stem, release_exe_name
from scripts.build_release import is_managed_exe_name, remove_old_artifacts


class ReleaseBuildTests(unittest.TestCase):
    def test_release_artifact_name_contains_version(self):
        self.assertRegex(release_artifact_stem(), r"^MWJDocs-v\d+\.\d+\.\d+$")
        self.assertEqual(release_exe_name(), f"{release_artifact_stem()}.exe")

    def test_cleanup_only_recognizes_managed_executables(self):
        self.assertTrue(is_managed_exe_name("MWJDocs.exe"))
        self.assertTrue(is_managed_exe_name("MWJDocs-v1.5.0.exe"))
        self.assertFalse(is_managed_exe_name("MWJDocs-v1.5.exe"))
        self.assertFalse(is_managed_exe_name("unrelated.exe"))
        self.assertFalse(is_managed_exe_name("MWJDocs-v1.5.0.exe.bak"))

    def test_cleanup_keeps_current_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            current = directory / "MWJDocs-v1.5.0.exe"
            legacy = directory / "MWJDocs.exe"
            old = directory / "MWJDocs-v1.4.0.exe"
            unrelated = directory / "helper.exe"
            for path in (current, legacy, old, unrelated):
                path.write_bytes(b"test")

            removed = remove_old_artifacts(directory, current.name)

            self.assertEqual({path.name for path in removed}, {legacy.name, old.name})
            self.assertTrue(current.exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
