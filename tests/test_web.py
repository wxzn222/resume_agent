import builtins
import gc
import importlib.util
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import Mock, patch

from src.web import (
    analyze_inputs,
    build_demo,
    launch_web,
    load_inputs,
    project_root,
    render_result,
    save_inputs,
)


class WebFileTests(unittest.TestCase):
    def test_project_root_is_repository_root(self):
        self.assertEqual(project_root(), Path(__file__).resolve().parents[1])

    def test_load_inputs_reads_utf8_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "resume.txt").write_text("中文简历", encoding="utf-8")
            (root / "jd.txt").write_text("测试岗位", encoding="utf-8")
            resume, jd, status = load_inputs(root)
        self.assertEqual(resume, "中文简历")
        self.assertEqual(jd, "测试岗位")
        self.assertIn("已加载", status)

    def test_load_inputs_reports_missing_file_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            resume, jd, status = load_inputs(Path(directory))
        self.assertEqual((resume, jd), ("", ""))
        self.assertIn("resume.txt", status)
        self.assertIn("jd.txt", status)

    def test_load_inputs_keeps_readable_file_when_other_file_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "resume.txt").write_text("可读简历", encoding="utf-8")
            (root / "jd.txt").write_bytes(b"\xff\xfe")
            resume, jd, status = load_inputs(root)
        self.assertEqual(resume, "可读简历")
        self.assertEqual(jd, "")
        self.assertIn("jd.txt", status)
        self.assertIn("读取失败", status)

    def test_save_inputs_writes_both_files_as_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = save_inputs("新简历", "新JD", root)
            self.assertEqual(
                (root / "resume.txt").read_text(encoding="utf-8"),
                "新简历",
            )
            self.assertEqual(
                (root / "jd.txt").read_text(encoding="utf-8"),
                "新JD",
            )
            self.assertIn("保存成功", status)
            self.assertFalse((root / "resume.txt.tmp").exists())
            self.assertFalse((root / "jd.txt.tmp").exists())

    def test_empty_save_does_not_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "resume.txt").write_text("原简历", encoding="utf-8")
            (root / "jd.txt").write_text("原JD", encoding="utf-8")
            status = save_inputs("", "新JD", root)
            self.assertEqual(
                (root / "resume.txt").read_text(encoding="utf-8"),
                "原简历",
            )
            self.assertEqual(
                (root / "jd.txt").read_text(encoding="utf-8"),
                "原JD",
            )
            self.assertIn("不能为空", status)

    def test_save_rolls_back_both_files_when_second_replace_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume_path = root / "resume.txt"
            jd_path = root / "jd.txt"
            resume_path.write_text("原简历", encoding="utf-8")
            jd_path.write_text("原JD", encoding="utf-8")
            real_replace = Path.replace

            def fail_for_jd_temporary(source, target):
                if source.name.startswith(".jd.txt.") and source.name.endswith(
                    ".tmp"
                ):
                    raise OSError("simulated second replace failure")
                return real_replace(source, target)

            with patch.object(Path, "replace", autospec=True) as replace:
                replace.side_effect = fail_for_jd_temporary
                status = save_inputs("新简历", "新JD", root)

            self.assertEqual(resume_path.read_text(encoding="utf-8"), "原简历")
            self.assertEqual(jd_path.read_text(encoding="utf-8"), "原JD")
            self.assertIn("保存失败", status)
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                ["jd.txt", "resume.txt"],
            )


class FakeAgent:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, resume, jd):
        self.calls.append((resume, jd))
        return self.result


class WebAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.result = {
            "total_score": 71.5,
            "scores": {
                "hard_requirements": 40.0,
                "technical_skills": 20.0,
                "project_experience": 11.5,
            },
            "matched_skills": ["Python", "pytest"],
            "missing_skills": ["SQL"],
            "unmet_hard_requirements": [],
            "rewritten_project_experience": [
                {
                    "situation": "支付项目",
                    "task": "接口验证",
                    "action": "执行接口验证",
                    "result": "完成验证",
                    "star_text": "支付项目中执行接口验证。",
                }
            ],
            "supplemental_keywords": [
                {
                    "keyword": "SQL",
                    "reason": "JD要求但未检出",
                    "suggested_section": "技能清单",
                }
            ],
            "warnings": [],
            "summary": "总分71.5分。",
        }

    def test_analysis_uses_page_text_without_overwriting_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "resume.txt").write_text("磁盘简历", encoding="utf-8")
            (root / "jd.txt").write_text("磁盘JD", encoding="utf-8")
            agent = FakeAgent(self.result)
            outputs = analyze_inputs("页面简历", "页面JD", root, agent)
            self.assertEqual(agent.calls, [("页面简历", "页面JD")])
            self.assertEqual(
                (root / "resume.txt").read_text(encoding="utf-8"),
                "磁盘简历",
            )
            self.assertEqual(
                (root / "jd.txt").read_text(encoding="utf-8"),
                "磁盘JD",
            )
            self.assertTrue((root / "result.txt").exists())
            self.assertIn("分析完成", outputs[0])

    def test_rendered_views_include_every_result_category(self):
        score, matching, star, keywords, full_json, summary = render_result(
            self.result
        )
        self.assertIn("71.5", score)
        self.assertIn("Python", matching)
        self.assertIn("SQL", matching)
        self.assertIn("支付项目", star)
        self.assertIn("技能清单", keywords)
        self.assertEqual(full_json, self.result)
        self.assertEqual(summary, "总分71.5分。")

    def test_rendering_escapes_model_text_before_markdown(self):
        self.result["rewritten_project_experience"][0]["situation"] = (
            "<script>alert(1)</script>"
        )
        _, _, star, _, _, _ = render_result(self.result)
        self.assertNotIn("<script>", star)
        self.assertIn("&lt;script&gt;", star)

    def test_rendering_neutralizes_markdown_links_images_and_blocks(self):
        self.result["rewritten_project_experience"][0]["situation"] = (
            "# 伪标题\n"
            "![跟踪图](https://example.com/tracker.png)\n"
            "[误导链接](https://example.com)\n"
            "> 伪引用\n"
            "|伪|表格|"
        )
        _, _, star, _, _, _ = render_result(self.result)
        self.assertNotIn("![跟踪图](", star)
        self.assertNotIn("[误导链接](", star)
        self.assertNotIn("\n# 伪标题", star)
        self.assertNotIn("\n> 伪引用", star)
        self.assertNotIn("\n|伪|表格|", star)
        self.assertIn("<br>", star)

    def test_empty_page_input_does_not_call_agent_or_write_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agent = FakeAgent(self.result)
            outputs = analyze_inputs("", "页面JD", root, agent)
            self.assertEqual(agent.calls, [])
            self.assertFalse((root / "result.txt").exists())
            self.assertIn("不能为空", outputs[0])

    def test_agent_error_is_rendered_without_fake_score(self):
        error = {
            "error": {"code": "EMPTY_INPUT", "message": "输入无效"},
            "warnings": [],
            "summary": "分析失败",
        }
        with tempfile.TemporaryDirectory() as directory:
            outputs = analyze_inputs(
                "简历", "JD", Path(directory), FakeAgent(error)
            )
        self.assertIn("输入无效", outputs[0])
        self.assertNotIn("总分：0", outputs[1])


class WebUiTests(unittest.TestCase):
    def test_missing_gradio_has_clear_install_message(self):
        real_import = builtins.__import__

        def reject_gradio(name, *args, **kwargs):
            if name == "gradio":
                raise ImportError("missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=reject_gradio):
            with self.assertRaisesRegex(RuntimeError, "gradio"):
                build_demo()

    def test_launch_is_local_and_never_shared(self):
        demo = type("Demo", (), {"launch": Mock()})()
        with patch("src.web.build_demo", return_value=demo):
            launch_web()
        demo.launch.assert_called_once()
        launch_options = demo.launch.call_args.kwargs
        self.assertEqual(launch_options["server_name"], "127.0.0.1")
        self.assertEqual(launch_options["server_port"], 7860)
        self.assertIs(launch_options["share"], False)
        self.assertIn("primary-action", launch_options["css"])

    @unittest.skipUnless(
        importlib.util.find_spec("gradio"),
        "Gradio is not installed in this test environment",
    )
    def test_build_demo_with_installed_gradio_exposes_all_page_actions(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            with tempfile.TemporaryDirectory() as directory:
                demo = build_demo(Path(directory))
            config = demo.get_config_file()
            visible_text = {
                component.get("props", {}).get("label")
                or component.get("props", {}).get("value")
                for component in config["components"]
            }
            for expected in (
                "开始精准分析",
                "重新加载文件",
                "保存到文件",
                "评分总览",
                "匹配分析",
                "STAR 改写",
                "增补关键词",
                "完整结果",
            ):
                self.assertIn(expected, visible_text)
            self.assertEqual(len(config["dependencies"]), 4)
            demo.close()
            del demo
            gc.collect()


if __name__ == "__main__":
    unittest.main()
