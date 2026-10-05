"""Check the deployed artifact and subdirectory URLs without installing packages."""
import ast
import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from build_pages import ROOT, build


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for name in ("href", "src"):
            value = values.get(name, "")
            if value and not value.startswith(("#", "data:", "http:", "https:")):
                self.references.append(value)


class PagesTests(unittest.TestCase):
    def test_project_site_artifact_and_dependencies(self):
        original_config = (ROOT / "space.config.json").read_bytes()
        original_notebook = (ROOT / "colab/Pi3X_SPACE.ipynb").read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "site"
            config = build(output, "student/pi3x-space", "https://student.github.io/pi3x-space", "main")
            self.assertEqual(config["viewerUrl"], "https://student.github.io/pi3x-space/")
            self.assertEqual(json.loads((output / "space.config.json").read_text()), config)
            for private in (".git", ".github", "scripts", "start.py", "colab/backend.py", "preview-mobile.png"):
                self.assertFalse((output / private).exists(), private)
            parser = AssetParser()
            parser.feed((output / "index.html").read_text())
            references = [("index.html", value) for value in parser.references]
            # Check module imports, lazy imports and notebook/config fetches, including vendor dependencies.
            for script in output.rglob("*.js"):
                source = script.read_text()
                relative = re.findall(r"(?:from\s*|import\s*\(|new URL\s*\()\s*['\"](\.[^'\"]+)['\"]", source)
                if script.name == "gradio-client.js":
                    # Gradio's Node-only WebSocket shim is unreachable in target browsers,
                    # which provide window.WebSocket. It is not a website dependency.
                    self.assertIn('typeof window&&"WebSocket"in window', source)
                    relative = [value for value in relative if value != "./wrapper-CviSselG.js"]
                references.extend((script.relative_to(output).as_posix(), value) for value in relative)
            self.assertGreater(len(references), 10)
            prefix = urlsplit(config["viewerUrl"]).path
            for source, reference in references:
                target = urlsplit(urljoin(urljoin(config["viewerUrl"], source), reference)).path
                self.assertTrue(target.startswith(prefix), target)
                self.assertTrue((output / target[len(prefix):]).exists(), reference)
            self.assertTrue((output / "vendor/three.module.js").is_file())
            notebook = json.loads((output / "colab/Pi3X_SPACE.ipynb").read_text())
            for cell in notebook["cells"]:
                if cell["cell_type"] == "code":
                    ast.parse("".join(cell["source"]))
        self.assertEqual((ROOT / "space.config.json").read_bytes(), original_config)
        self.assertEqual((ROOT / "colab/Pi3X_SPACE.ipynb").read_bytes(), original_notebook)

    def test_account_site_and_custom_domain(self):
        with tempfile.TemporaryDirectory() as folder:
            for index, url in enumerate(("https://student.github.io/", "https://space.example/class/")):
                config = build(Path(folder) / str(index), "student/student.github.io", url, "main")
                self.assertEqual(config["viewerUrl"], url)
                self.assertEqual(config["githubRepository"], "student/student.github.io")

    def test_invalid_configuration_fails_before_export(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "site"
            for options in ({"repository": "https://github.com/student/project"},
                            {"viewer_url": "javascript:alert(1)"},
                            {"viewer_url": "https://user:password@space.example/"},
                            {"viewer_url": "https://space.example/?colab=temporary"},
                            {"ref": ""}):
                with self.assertRaises(ValueError):
                    build(output, **options)
                self.assertFalse(output.exists())
            with self.assertRaises(ValueError):
                build(ROOT)


if __name__ == "__main__":
    unittest.main()
