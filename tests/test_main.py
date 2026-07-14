import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from src.agent import ResumeAgent
from src.main import project_root, run_from_files


class MainTests(unittest.TestCase):
    def test_project_root_is_parent_of_src(self):
        self.assertEqual(project_root(), Path(__file__).resolve().parents[1])

    def test_reads_inputs_and_writes_result_in_supplied_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "resume.txt").write_text(
                "项目经历：使用Python执行测试。", encoding="utf-8"
            )
            (root / "jd.txt").write_text("要求Python", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code, result = run_from_files(
                    root=root, agent=ResumeAgent(model_client=None)
                )
            self.assertEqual(code, 0)
            self.assertTrue((root / "result.txt").exists())
            self.assertIn("total_score", result)
            self.assertIn(
                "=== 文字总结 ===",
                (root / "result.txt").read_text(encoding="utf-8"),
            )

    def test_missing_input_returns_structured_error_and_nonzero_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                code, result = run_from_files(root=root)
            self.assertNotEqual(code, 0)
            self.assertEqual(result["error"]["code"], "INPUT_FILE_MISSING")
            self.assertTrue((root / "result.txt").exists())

    def test_empty_input_returns_structured_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "resume.txt").write_text("  ", encoding="utf-8")
            (root / "jd.txt").write_text("要求Python", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code, result = run_from_files(root=root)
            self.assertNotEqual(code, 0)
            self.assertEqual(result["error"]["code"], "INPUT_FILE_EMPTY")


if __name__ == "__main__":
    unittest.main()
