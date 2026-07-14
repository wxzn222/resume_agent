# Local Web Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local Gradio interface that automatically loads root-level resume/JD files, supports temporary editing and explicit saving, runs the existing Agent, displays every result category, and preserves the current command-line workflow.

**Architecture:** A new `src/web.py` owns only local-web file callbacks, view formatting, Gradio construction, and launch configuration. It calls the existing `ResumeAgent` and `write_result` instead of duplicating business rules; Gradio is imported lazily so `src/main.py` and pure callback tests remain usable without the optional UI package.

**Tech Stack:** Python 3.11, standard library (`pathlib`, `json`, `unittest`), Gradio Blocks 5.x/6.x, existing Agent modules.

## Global Constraints

- Preserve `python src/main.py` and its automatic `resume.txt`/`jd.txt`/`result.txt` behavior.
- Add `python src/web.py` as a separate local-only entry point.
- Web analysis must not overwrite `resume.txt` or `jd.txt`.
- Only the explicit save callback may write input files, using UTF-8 temporary files and replacement.
- Every successful web analysis must update root-level `result.txt` through the existing writer.
- Bind only to `127.0.0.1:7860` with `share=False`.
- Do not duplicate or change scoring, synonym, hard-cap, or STAR fact-safety logic.
- Do not log full resume or JD content.
- Keep Gradio imports out of module import time.

---

### Task 1: File lifecycle callbacks

**Files:**
- Create: `src/web.py`
- Create: `tests/test_web.py`

**Interfaces:**
- Produces: `project_root() -> pathlib.Path`
- Produces: `load_inputs(root: pathlib.Path | None = None) -> tuple[str, str, str]`
- Produces: `save_inputs(resume: str, jd: str, root: pathlib.Path | None = None) -> str`

- [ ] **Step 1: Write failing file callback tests**

```python
import tempfile
import unittest
from pathlib import Path

from src.web import load_inputs, project_root, save_inputs


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

    def test_save_inputs_writes_both_files_as_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status = save_inputs("新简历", "新JD", root)
            self.assertEqual((root / "resume.txt").read_text(encoding="utf-8"), "新简历")
            self.assertEqual((root / "jd.txt").read_text(encoding="utf-8"), "新JD")
            self.assertIn("保存成功", status)

    def test_empty_save_does_not_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "resume.txt").write_text("原简历", encoding="utf-8")
            (root / "jd.txt").write_text("原JD", encoding="utf-8")
            status = save_inputs("", "新JD", root)
            self.assertEqual((root / "resume.txt").read_text(encoding="utf-8"), "原简历")
            self.assertEqual((root / "jd.txt").read_text(encoding="utf-8"), "原JD")
            self.assertIn("不能为空", status)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web.WebFileTests -v`

Expected: FAIL because `src.web` does not exist.

- [ ] **Step 3: Implement root-relative load and explicit atomic save**

Create `src/web.py` with direct-script path bootstrapping matching `src/main.py`. `load_inputs` reads each expected UTF-8 file independently and returns editable content plus a Markdown status. `save_inputs` rejects either blank input before opening any file, writes `resume.txt.tmp` and `jd.txt.tmp`, then replaces destinations; it cleans leftover temporary files in `finally` and returns a clear success/error status without logging content.

- [ ] **Step 4: Run file callback tests and verify GREEN**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web.WebFileTests -v`

Expected: all file callback tests pass.

---

### Task 2: Analysis callback and complete result views

**Files:**
- Modify: `src/web.py`
- Modify: `tests/test_web.py`

**Interfaces:**
- Consumes: `ResumeAgent.run`, `write_result`
- Produces: `render_result(result: dict[str, object]) -> tuple[str, str, str, str, dict[str, object], str]`
- Produces: `analyze_inputs(resume: str, jd: str, root: pathlib.Path | None = None, agent: object | None = None) -> tuple[str, str, str, str, str, dict[str, object], str]`

- [ ] **Step 1: Write failing analysis and rendering tests**

```python
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
            "rewritten_project_experience": [{
                "situation": "支付项目", "task": "接口验证",
                "action": "执行接口验证", "result": "完成验证",
                "star_text": "支付项目中执行接口验证。",
            }],
            "supplemental_keywords": [{
                "keyword": "SQL", "reason": "JD要求但未检出",
                "suggested_section": "技能清单",
            }],
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
            self.assertEqual((root / "resume.txt").read_text(encoding="utf-8"), "磁盘简历")
            self.assertEqual((root / "jd.txt").read_text(encoding="utf-8"), "磁盘JD")
            self.assertTrue((root / "result.txt").exists())
            self.assertIn("分析完成", outputs[0])

    def test_rendered_views_include_every_result_category(self):
        score, matching, star, keywords, full_json, summary = render_result(self.result)
        self.assertIn("71.5", score)
        self.assertIn("Python", matching)
        self.assertIn("SQL", matching)
        self.assertIn("支付项目", star)
        self.assertIn("技能清单", keywords)
        self.assertEqual(full_json, self.result)
        self.assertEqual(summary, "总分71.5分。")

    def test_empty_page_input_does_not_call_agent_or_write_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agent = FakeAgent(self.result)
            outputs = analyze_inputs("", "页面JD", root, agent)
            self.assertEqual(agent.calls, [])
            self.assertFalse((root / "result.txt").exists())
            self.assertIn("不能为空", outputs[0])

    def test_agent_error_is_rendered_without_fake_score(self):
        error = {"error": {"code": "EMPTY_INPUT", "message": "输入无效"}, "warnings": [], "summary": "分析失败"}
        with tempfile.TemporaryDirectory() as directory:
            outputs = analyze_inputs("简历", "JD", Path(directory), FakeAgent(error))
        self.assertIn("输入无效", outputs[0])
        self.assertNotIn("总分：0", outputs[1])
```

- [ ] **Step 2: Run tests and verify RED**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web.WebAnalysisTests -v`

Expected: FAIL because analysis and rendering interfaces are missing.

- [ ] **Step 3: Implement safe view formatting and analysis orchestration**

`render_result` builds Markdown with escaped user/model text, returns the original JSON dictionary, and uses safe defaults for missing fields. `analyze_inputs` validates before constructing the default Agent, calls it once, handles structured Agent errors, writes successful results with `write_result`, preserves views when export fails, includes warning codes in status, and returns exactly seven outputs in this order: status, score, matching, STAR, keywords, JSON, summary.

- [ ] **Step 4: Run web analysis tests and verify GREEN**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web.WebAnalysisTests -v`

Expected: all analysis and rendering tests pass.

---

### Task 3: Gradio Blocks page and local-only launch

**Files:**
- Modify: `src/web.py`
- Modify: `tests/test_web.py`
- Modify: `environment.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `load_inputs`, `save_inputs`, `analyze_inputs`
- Produces: `build_demo(root: pathlib.Path | None = None, agent: object | None = None) -> object`
- Produces: `main() -> None`

- [ ] **Step 1: Write failing lazy-import and launch-configuration tests**

```python
import builtins
from unittest.mock import patch


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
        demo = type("Demo", (), {"launch": unittest.mock.Mock()})()
        with patch("src.web.build_demo", return_value=demo):
            launch_web()
        demo.launch.assert_called_once_with(
            server_name="127.0.0.1",
            server_port=7860,
            share=False,
        )
```

- [ ] **Step 2: Run UI tests and verify RED**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web.WebUiTests -v`

Expected: FAIL because `build_demo` and `launch_web` are missing.

- [ ] **Step 3: Build the approved page**

Inside `build_demo`, lazily import Gradio and raise `RuntimeError("缺少 gradio，请先安装项目依赖")` on import failure. Build one `gr.Blocks(title=..., css=...)` page with editable resume/JD textboxes, status Markdown, reload/save/analyze buttons, and five tabs. Wire `demo.load` and reload to `load_inputs`; wire save to `save_inputs`; wire analyze to the seven analysis outputs. Use closures for optional root and injected Agent. Queue analyses with a concurrency limit of one.

Add `launch_web()` that calls `build_demo().launch(server_name="127.0.0.1", server_port=7860, share=False)`, and call it under the module guard.

Add `gradio>=5,<7` to `environment.yml`. Update README with both commands, the local URL, automatic load behavior, non-overwriting analysis behavior, and the explicit save button.

- [ ] **Step 4: Run UI tests and all web tests**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web -v`

Expected: all web tests pass without requiring Gradio for pure callback tests.

---

### Task 4: Full regression and local web smoke verification

**Files:**
- Verify: `src/*.py`, `tests/*.py`, `README.md`, `environment.yml`

- [ ] **Step 1: Run all automated tests**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v`

Expected: all existing and new tests pass with zero failures and zero errors.

- [ ] **Step 2: Compile all Python sources**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests test_model.py`

Expected: exit code 0.

- [ ] **Step 3: Re-run the command-line pipeline**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" src/main.py`

Expected: exit code 0 and a parseable root-level `result.txt` with the text-summary marker.

- [ ] **Step 4: Verify Gradio availability and page construction**

If Gradio is installed, import `src.web`, call `build_demo()`, and confirm it returns a Blocks-like object without launching a public service. If Gradio is not installed in the bundled test runtime, confirm the documented RuntimeError and validate that `environment.yml` contains `gradio>=5,<7`; do not weaken command-line verification.

- [ ] **Step 5: Start the local service when the dependency is available**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" src/web.py`

Expected: a local service at `http://127.0.0.1:7860`, with no share URL. Stop the verification service after confirming startup unless the user asks to keep it running.

- [ ] **Step 6: Review final diff**

Confirm `src/main.py` is behaviorally unchanged, no business rules moved into `src/web.py`, no full resume/JD logging was added, analysis does not write input files, and all user-visible result categories are represented.
