"""Validate the Space upload package and host boundary without ML installs."""
import ast
import tempfile
import unittest
import zipfile
from pathlib import Path

from build_space import ROOT, build_space
from set_backend import normalize_endpoint


class SpacePackageTests(unittest.TestCase):
    def test_upload_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder, archive = build_space(Path(temporary) / "space")
            expected = {"app.py", "backend.py", "requirements.txt", "README.md"}
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()), expected)
                for name in expected:
                    self.assertEqual(bundle.read(name), (folder / name).read_bytes())
            self.assertEqual((folder / "backend.py").read_bytes(), (ROOT / "colab/backend.py").read_bytes())
            app = ast.parse((folder / "app.py").read_text())
            # spaces must load before backend imports torch, enabling CUDA emulation.
            imports = [node for node in app.body if isinstance(node, (ast.Import, ast.ImportFrom))]
            self.assertEqual(imports[0].names[0].name, "spaces")
            gpu_function = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == "reconstruct")
            self.assertEqual([argument.arg for argument in gpu_function.args.args], ["images", "quality", "progress"])
            self.assertEqual(len(gpu_function.decorator_list), 1)
            for name in ("app.py", "backend.py"):
                compile((folder / name).read_text(), name, "exec")

    def test_cannot_overwrite_source(self):
        for output in (ROOT, ROOT.parent, ROOT / "colab", ROOT / "hosting/huggingface"):
            with self.assertRaises(ValueError):
                build_space(output)

    def test_gpu_host_allowlist(self):
        for value in ("https://abc.gradio.live/", "https://leekh951-pi3x-vibe.hf.space/"):
            self.assertEqual(normalize_endpoint(value), value[:-1])
        for value in ("http://test.hf.space", "https://test.hf.space.evil.example",
                      "https://user:secret@test.hf.space", "https://test.hf.space:8443",
                      "https://nested.test.hf.space", "https://example.com"):
            with self.assertRaises(ValueError):
                normalize_endpoint(value)

    def test_small_jobs_do_not_reserve_full_gpu_budget(self):
        app = ast.parse((ROOT / "hosting/huggingface/app.py").read_text())
        duration = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == "gpu_duration")
        namespace = {}
        exec(compile(ast.Module(body=[duration], type_ignores=[]), "gpu_duration", "exec"), namespace)
        estimate = namespace["gpu_duration"]
        self.assertEqual(estimate(["photo"] * 3, "fast"), 45)
        self.assertLess(estimate(["photo"] * 3, "detail"), 120)
        self.assertLessEqual(estimate(["photo"] * 8, "detail"), 90)


if __name__ == "__main__":
    unittest.main()
