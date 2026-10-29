import asyncio
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from release_config import release_exe_name
import serve
import yuqueToMD
from version import __version__


def response_json(response):
    return json.loads(response.body.decode("utf-8"))


class ServeRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "docs"
        self.root.mkdir()
        self.previous_result_dir = serve.RESULT_DIR
        serve.RESULT_DIR = self.root

    def tearDown(self):
        serve.invalidate_search_cache(self.root)
        serve.RESULT_DIR = self.previous_result_dir
        self.temp_dir.cleanup()

    def test_sibling_prefix_is_not_inside_root(self):
        sibling = self.root.parent / "docs_backup"
        sibling.mkdir()
        (sibling / "secret.md").write_text("secret", encoding="utf-8")

        response = asyncio.run(serve.raw(path="../docs_backup/secret.md"))

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(serve.resolve_within(self.root, "../docs_backup/secret.md"))

    def test_document_root_cannot_be_deleted(self):
        response = asyncio.run(serve.delete_node({"path": "."}))

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.root.is_dir())

    def test_raw_html_is_escaped(self):
        rendered = serve.MARKDOWN_RENDERER('<img src=x onerror="alert(1)">')

        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img", rendered)

    def test_attachment_number_uses_maximum_not_count(self):
        attachments = self.root / "attachments"
        attachments.mkdir()
        (attachments / "doc_001.png").write_bytes(b"one")
        (attachments / "doc_003.png").write_bytes(b"three")

        self.assertEqual(serve.next_attachment_number(attachments, "doc"), 4)

    def test_orphan_check_considers_sibling_documents(self):
        attachments = self.root / "attachments"
        attachments.mkdir()
        (attachments / "a_001.png").write_bytes(b"a")
        (attachments / "b_001.png").write_bytes(b"b")
        (self.root / "a.md").write_text("![](./attachments/a_001.png)", encoding="utf-8")
        (self.root / "b.md").write_text("![](./attachments/b_001.png)", encoding="utf-8")

        response = asyncio.run(serve.check_orphan_images({
            "path": "a.md",
            "content": "![](./attachments/a_001.png)",
        }))

        self.assertEqual(response_json(response)["orphans"], [])

    def test_delete_images_rechecks_all_document_references(self):
        attachments = self.root / "attachments"
        attachments.mkdir()
        image = attachments / "b_001.png"
        image.write_bytes(b"b")
        (self.root / "a.md").write_text("# A", encoding="utf-8")
        (self.root / "b.md").write_text("![](./attachments/b_001.png)", encoding="utf-8")

        response = asyncio.run(serve.delete_images({
            "path": "a.md",
            "files": ["b_001.png"],
        }))

        data = response_json(response)
        self.assertEqual(data["deleted"], 0)
        self.assertEqual(data["skipped"], 1)
        self.assertTrue(image.exists())

    def test_uppercase_markdown_extension_can_be_read(self):
        (self.root / "README.MD").write_text("hello", encoding="utf-8")

        response = asyncio.run(serve.raw(path="README.MD"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_json(response)["content"], "hello")

    def test_search_cache_can_be_invalidated_after_save(self):
        document = self.root / "doc.md"
        document.write_text("alpha", encoding="utf-8")
        self.assertEqual(len(serve.search_files(self.root, "alpha")), 1)

        document.write_text("bravo", encoding="utf-8")
        self.assertEqual(len(serve.search_files(self.root, "bravo")), 0)
        serve.invalidate_search_cache(self.root)

        self.assertEqual(len(serve.search_files(self.root, "bravo")), 1)

    def test_rewritten_attachment_url_is_not_double_encoded(self):
        rendered = serve.MARKDOWN_RENDERER("![](./attachments/a%20b.png)")

        self.assertIn('/files/attachments/a%20b.png', serve.rewrite_image_paths(rendered, "."))
        self.assertNotIn("%2520", serve.rewrite_image_paths(rendered, "."))

    def test_save_rejects_external_file_change(self):
        document = self.root / "doc.md"
        document.write_text("before", encoding="utf-8")
        raw_response = asyncio.run(serve.raw(path="doc.md"))
        revision = response_json(raw_response)["revision"]
        document.write_text("outside", encoding="utf-8")

        response = asyncio.run(serve.save({
            "path": "doc.md", "content": "editor", "revision": revision,
        }))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(document.read_text(encoding="utf-8"), "outside")

    def test_large_markdown_is_not_loaded_for_preview(self):
        document = self.root / "large.md"
        document.write_text("x" * (serve.MAX_PREVIEW_BYTES + 1), encoding="utf-8")

        response = asyncio.run(serve.raw(path="large.md"))

        self.assertEqual(response.status_code, 413)

    def test_large_search_file_is_skipped(self):
        document = self.root / "large.md"
        document.write_text("needle" + "x" * serve.MAX_SEARCH_FILE_BYTES, encoding="utf-8")

        self.assertEqual(serve.search_files(self.root, "needle"), [])

    def test_tree_loads_only_one_level(self):
        nested = self.root / "第一层" / "第二层"
        nested.mkdir(parents=True)
        (nested / "doc.md").write_text("content", encoding="utf-8")

        response = asyncio.run(serve.tree(path=""))
        data = response_json(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data[0]["name"], "第一层")
        self.assertIsNone(data[0]["children"])

        child_response = asyncio.run(serve.tree(path="第一层"))
        child_data = response_json(child_response)
        self.assertEqual(child_data[0]["name"], "第二层")


class ConverterRegressionTests(unittest.TestCase):
    def test_image_download_rejects_private_hosts(self):
        with self.assertRaises(ValueError):
            yuqueToMD.fetch_image("http://127.0.0.1/image.png")

        with self.assertRaises(ValueError):
            yuqueToMD.fetch_image("http://169.254.169.254/latest/meta-data")

    def test_windows_reserved_name_with_extension_is_made_safe(self):
        value = yuqueToMD.sanitizer_file_name("CON.json")

        self.assertEqual(value.split(".", 1)[0].upper(), "CON_")

    def test_converter_attachment_number_uses_maximum(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            (directory / "doc_001.png").write_bytes(b"one")
            (directory / "doc_003.png").write_bytes(b"three")

            self.assertEqual(yuqueToMD.next_attachment_number(directory, "doc"), 4)

    def test_tar_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "bad.tar"
            output = Path(temp_dir) / "output"
            output.mkdir()
            with tarfile.open(archive, "w") as tar:
                info = tarfile.TarInfo("../escape.txt")
                payload = b"escape"
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))

            with self.assertRaises(ValueError):
                yuqueToMD.extract_tar(archive, output)
            self.assertFalse((Path(temp_dir) / "escape.txt").exists())

    def test_tar_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "link.tar"
            output = Path(temp_dir) / "output"
            output.mkdir()
            with tarfile.open(archive, "w") as tar:
                info = tarfile.TarInfo("link")
                info.type = tarfile.SYMTYPE
                info.linkname = "../outside"
                tar.addfile(info)

            with self.assertRaisesRegex(ValueError, "Unsupported archive entry"):
                yuqueToMD.extract_tar(archive, output)

    def test_regular_tar_file_is_extracted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "valid.tar"
            output = Path(temp_dir) / "output"
            output.mkdir()
            with tarfile.open(archive, "w") as tar:
                info = tarfile.TarInfo("repo/doc.json")
                payload = b'{}'
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))

            yuqueToMD.extract_tar(archive, output)

            self.assertEqual((output / "repo" / "doc.json").read_bytes(), b'{}')


class VersionMetadataTests(unittest.TestCase):
    def test_release_version_is_synchronized(self):
        project_root = Path(__file__).resolve().parents[1]
        pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8")
        version_info = (project_root / "version_info.txt").read_text(encoding="utf-8")

        self.assertEqual(serve.app.version, __version__)
        self.assertIn(f'version = "{__version__}"', pyproject)
        self.assertIn(f'StringStruct("ProductVersion", "{__version__}")', version_info)
        self.assertIn(
            f'StringStruct("OriginalFilename", "{release_exe_name()}")',
            version_info,
        )


if __name__ == "__main__":
    unittest.main()
