# Resume/JD Precise Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automatic, explainable resume/JD matching pipeline that scores hard requirements, technical overlap, and project fit; rewrites projects in STAR form; recommends missing keywords; and exports JSON plus a Chinese summary.

**Architecture:** `tools.py` owns deterministic extraction, normalization, scoring, and conservative fallbacks; `model_client.py` owns Ollama transport and JSON parsing; `agent.py` serially orchestrates all stages; `main.py` resolves project-root input/output files and runs without pasted text. All model behavior is injectable so tests never require a live service.

**Tech Stack:** Python 3 standard library (`json`, `re`, `pathlib`, `unittest`), optional `openai` and `python-dotenv` for Ollama compatibility.

## Global Constraints

- Preserve the existing `src/agent.py`, `src/tools.py`, and `src/model_client.py` responsibilities and multi-file structure.
- Read `resume.txt` and `jd.txt` from the project root automatically; write `result.txt` there.
- Score weights are fixed at hard requirements 40, technical skills 35, and project experience 25.
- Apply total-score caps of 59, 39, and 19 for one, two, and three-or-more unmet hard requirements.
- Never invent skills, projects, years, metrics, percentages, or other facts not supported by the resume.
- Store source and output text as UTF-8 and do not log full resume/JD contents.
- Tests use `unittest.TestCase`, which runs without extra dependencies and remains collectable by `pytest`.

---

### Task 1: Deterministic JD analysis and skill normalization

**Files:**
- Modify: `src/tools.py`
- Replace: `tests/test_tools.py`

**Interfaces:**
- Produces: `normalize_text(text: str) -> str`
- Produces: `find_skills(text: str) -> list[str]`
- Produces: `analyze_jd(jd_text: str) -> dict[str, object]`
- Produces: `extract_resume_profile(resume_text: str) -> dict[str, object]`

- [ ] **Step 1: Write failing normalization and JD classification tests**

```python
import unittest
from src.tools import analyze_jd, extract_resume_profile, find_skills


class SkillAndJdTests(unittest.TestCase):
    def test_synonyms_are_normalized_and_deduplicated(self):
        text = "熟悉 PyTest、API测试、接口测试、Bug管理和功能测试"
        self.assertEqual(
            find_skills(text),
            ["pytest", "缺陷管理", "接口测试", "黑盒测试"],
        )

    def test_automation_synonyms_share_one_canonical_skill(self):
        self.assertEqual(find_skills("自动化测试、UI自动化、接口自动化"), ["自动化测试"])

    def test_jd_is_split_into_three_categories(self):
        result = analyze_jd(
            "本科及以上，计算机相关专业，3年以上经验；熟悉Python、SQL和pytest；沟通协作能力强。"
        )
        self.assertEqual(result["hard_requirements"]["education"][0]["level"], "本科")
        self.assertEqual(result["hard_requirements"]["work_years"][0]["minimum"], 3)
        self.assertIn("计算机", result["hard_requirements"]["major"][0]["families"])
        self.assertEqual(result["technical_skills"], ["Python", "SQL", "pytest"])
        self.assertIn("沟通", result["soft_qualities"])

    def test_resume_profile_extracts_verifiable_hard_facts(self):
        profile = extract_resume_profile("本科学历，软件工程专业，4年软件测试经验。")
        self.assertEqual(profile["education_level"], "本科")
        self.assertEqual(profile["work_years"], 4)
        self.assertIn("软件工程", profile["major_families"])
```

- [ ] **Step 2: Run tests and verify RED**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_tools.SkillAndJdTests -v`

Expected: FAIL because `find_skills`, `analyze_jd`, and `extract_resume_profile` do not exist in the current module.

- [ ] **Step 3: Implement canonical skill and hard-requirement extraction**

Implement these constants and functions in `src/tools.py`:

```python
SKILL_SYNONYMS = {
    "Python": ("python",),
    "SQL": ("sql", "mysql", "postgresql", "数据库查询"),
    "pytest": ("pytest", "py.test"),
    "测试用例": ("测试用例", "用例设计", "test case", "test cases"),
    "缺陷管理": ("缺陷管理", "bug管理", "bug 管理", "缺陷跟踪", "缺陷追踪"),
    "接口测试": ("接口测试", "api测试", "api 测试"),
    "黑盒测试": ("黑盒测试", "功能测试"),
    "自动化测试": ("自动化测试", "ui自动化", "ui 自动化", "接口自动化"),
}

EDUCATION_LEVELS = {"中专": 1, "高中": 1, "大专": 2, "本科": 3, "硕士": 4, "博士": 5}
MAJOR_FAMILIES = {
    "计算机": ("计算机", "计算机科学", "计算机技术"),
    "软件工程": ("软件工程", "软件开发"),
    "软件测试": ("软件测试", "测试工程"),
}
SOFT_QUALITY_SYNONYMS = {
    "沟通": ("沟通", "表达"),
    "协作": ("协作", "合作", "团队"),
    "责任心": ("责任心", "负责"),
    "学习能力": ("学习能力", "快速学习", "自学"),
    "问题分析": ("问题分析", "分析能力", "解决问题"),
}

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower().replace("：", ":"))

def find_skills(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [name for name, aliases in SKILL_SYNONYMS.items()
            if any(normalize_text(alias) in normalized for alias in aliases)]
```

Remove the current module-level `ModelClient` construction so importing deterministic tools never requires optional packages or a live model. Add `_extract_education(text)`, `_extract_work_years(text)`, `_extract_major(text)`, `_find_soft_qualities(text)`, and `_extract_project_context(text)` with the exact return fields asserted above. Education chooses the highest level mentioned; work years chooses the largest number immediately followed by `年`; major families are returned in `MAJOR_FAMILIES` insertion order; project context begins at headings matching `项目经历|项目经验|工作经历|职责` and otherwise returns an empty string. `analyze_jd` returns `hard_requirements`, `technical_skills`, and `soft_qualities`; `extract_resume_profile` returns `education_level`, `work_years`, `major_families`, `skills`, and `project_context`.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_tools.SkillAndJdTests -v`

Expected: 4 tests pass.

---

### Task 2: Weighted scoring and hard-gate caps

**Files:**
- Modify: `src/tools.py`
- Modify: `tests/test_tools.py`

**Interfaces:**
- Consumes: `analyze_jd`, `extract_resume_profile`
- Produces: `score_resume(resume_text: str, jd_analysis: dict[str, object]) -> dict[str, object]`

- [ ] **Step 1: Write failing scoring tests**

```python
from src.tools import score_resume


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.jd = analyze_jd(
            "本科及以上，计算机相关专业，3年以上经验；要求Python、SQL、pytest、接口测试。"
        )

    def test_full_hard_requirements_score_40(self):
        result = score_resume("本科，计算机专业，4年经验，Python SQL pytest 接口测试。", self.jd)
        self.assertEqual(result["scores"]["hard_requirements"], 40.0)
        self.assertEqual(result["unmet_hard_requirements"], [])

    def test_one_unmet_hard_requirement_caps_total_at_59(self):
        result = score_resume(
            "大专，计算机专业，4年经验。项目：使用Python、SQL、pytest完成接口测试。", self.jd
        )
        self.assertLessEqual(result["total_score"], 59.0)
        self.assertEqual(len(result["unmet_hard_requirements"]), 1)

    def test_two_and_three_unmet_requirements_apply_stricter_caps(self):
        two = score_resume("大专，市场营销专业，4年经验。Python SQL pytest 接口测试。", self.jd)
        three = score_resume("大专，市场营销专业，1年经验。Python SQL pytest 接口测试。", self.jd)
        self.assertLessEqual(two["total_score"], 39.0)
        self.assertLessEqual(three["total_score"], 19.0)

    def test_project_evidence_scores_higher_than_skill_list_only(self):
        listed = score_resume("本科计算机专业，4年经验。技能：Python、SQL、pytest、接口测试。", self.jd)
        evidenced = score_resume(
            "本科计算机专业，4年经验。项目经历：使用Python和pytest编写接口测试，执行SQL校验并跟踪缺陷。",
            self.jd,
        )
        self.assertGreater(evidenced["scores"]["project_experience"], listed["scores"]["project_experience"])
```

- [ ] **Step 2: Run tests and verify RED**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_tools.ScoringTests -v`

Expected: FAIL because `score_resume` is missing.

- [ ] **Step 3: Implement deterministic scoring**

Add `score_resume` with these exact rules:

```python
SCORE_WEIGHTS = {"hard_requirements": 40.0, "technical_skills": 35.0, "project_experience": 25.0}
HARD_CAPS = {1: 59.0, 2: 39.0}

def _cap_for_unmet(count: int) -> float:
    if count <= 0:
        return 100.0
    if count >= 3:
        return 19.0
    return HARD_CAPS[count]
```

Score only hard dimensions present in the JD, distribute 40 points equally across those dimensions, and create evidence-rich unmet records. Divide matched canonical JD skills by JD skills for the 35-point score. Detect project/responsibility sections by headings and sentence boundaries; compute 60% project skill coverage, 25% testing-activity evidence, and 15% soft-quality evidence for the 25-point score. Round components and total to two decimals, then apply `_cap_for_unmet`.

- [ ] **Step 4: Run all tool tests and verify GREEN**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_tools -v`

Expected: all tests pass.

---

### Task 3: Robust optional model client

**Files:**
- Modify: `src/model_client.py`
- Create: `tests/test_model_client.py`

**Interfaces:**
- Produces: `ModelClient.chat(prompt: str, temperature: float = 0.0) -> str`
- Produces: `ModelClient.chat_json(prompt: str, temperature: float = 0.0) -> dict[str, object]`
- Produces: `parse_json_object(content: str) -> dict[str, object]`

- [ ] **Step 1: Write failing JSON parsing tests**

```python
import unittest
from src.model_client import parse_json_object


class ModelJsonTests(unittest.TestCase):
    def test_parses_plain_json(self):
        self.assertEqual(parse_json_object('{"items": ["Python"]}'), {"items": ["Python"]})

    def test_parses_markdown_fenced_nested_json(self):
        content = '说明\n```json\n{"star": {"action": "测试"}, "warnings": []}\n```'
        self.assertEqual(parse_json_object(content)["star"]["action"], "测试")

    def test_rejects_non_object_json(self):
        with self.assertRaises(ValueError):
            parse_json_object('["not", "object"]')
```

- [ ] **Step 2: Run tests and verify RED**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_model_client -v`

Expected: FAIL because `parse_json_object` is missing or import fails due the existing malformed source.

- [ ] **Step 3: Implement lazy, quiet model access and decoder-based parsing**

Use `json.JSONDecoder().raw_decode` from every `{` position so nested objects are supported. Load `.env.example` without printing secrets or prompts. Import `openai` and `dotenv` inside initialization so deterministic scoring can run when optional packages are absent. `chat` returns response text; `chat_json` calls `parse_json_object`.

- [ ] **Step 4: Run model-client tests and verify GREEN**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_model_client -v`

Expected: 3 tests pass without contacting Ollama.

---

### Task 4: STAR rewriting, keyword recommendations, and fact safety

**Files:**
- Modify: `src/tools.py`
- Modify: `tests/test_tools.py`

**Interfaces:**
- Produces: `rewrite_projects_star(resume_text: str, jd_text: str, missing_skills: list[str], model_client: object | None) -> tuple[list[dict[str, str]], list[str]]`
- Produces: `build_supplemental_keywords(jd_analysis: dict[str, object], missing_skills: list[str]) -> list[dict[str, str]]`

- [ ] **Step 1: Write failing STAR and keyword tests**

```python
from src.tools import build_supplemental_keywords, rewrite_projects_star


class FakeModel:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def chat_json(self, prompt, temperature=0.0):
        if self.error:
            raise self.error
        return self.result


class RewriteTests(unittest.TestCase):
    def test_model_star_is_returned_when_fact_safe(self):
        model = FakeModel({"projects": [{
            "situation": "电商项目", "task": "负责接口质量验证",
            "action": "使用Python编写接口检查", "result": "完成核心流程验证",
            "star_text": "在电商项目中负责接口质量验证，使用Python编写接口检查，完成核心流程验证。"
        }]})
        projects, warnings = rewrite_projects_star(
            "电商项目：使用Python完成接口检查。", "要求Python和SQL", ["SQL"], model
        )
        self.assertEqual(projects[0]["situation"], "电商项目")
        self.assertEqual(warnings, [])

    def test_new_numbers_force_conservative_fallback(self):
        model = FakeModel({"projects": [{
            "situation": "项目", "task": "测试", "action": "执行测试",
            "result": "效率提升30%", "star_text": "效率提升30%"
        }]})
        projects, warnings = rewrite_projects_star("项目：执行测试。", "要求测试", [], model)
        self.assertNotIn("30", projects[0]["star_text"])
        self.assertTrue(warnings)

    def test_model_failure_uses_complete_star_fallback(self):
        projects, warnings = rewrite_projects_star(
            "项目：设计测试用例并跟踪缺陷。", "要求接口测试", ["接口测试"],
            FakeModel(error=RuntimeError("offline")),
        )
        self.assertEqual(set(projects[0]), {"situation", "task", "action", "result", "star_text"})
        self.assertTrue(warnings)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_tools.RewriteTests -v`

Expected: FAIL because STAR rewrite helpers do not exist.

- [ ] **Step 3: Implement guarded model rewrite and conservative fallback**

Prompt the model to return `{"projects": [...]}` and explicitly forbid unsupported facts and missing skills. Validate required string fields, reject digits absent from the source resume, and reject a missing canonical skill if the generated text claims it was used. On rejection or exception, split source project sentences and construct complete STAR dictionaries with neutral Situation/Task/Result wording. Return warning codes without exception details that may leak content.

Build supplemental keyword dictionaries with `keyword`, `reason`, and `suggested_section`; include missing technical skills first, then unrepresented soft qualities, with stable deduplication.

- [ ] **Step 4: Run tool tests and verify GREEN**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_tools -v`

Expected: all tool tests pass.

---

### Task 5: Serial orchestration and result export

**Files:**
- Modify: `src/agent.py`
- Replace: `tests/test_agent.py`

**Interfaces:**
- Consumes: analysis, scoring, rewrite, and keyword helpers from `src.tools`
- Produces: `ResumeAgent.run(resume: str, jd: str) -> dict[str, object]`
- Produces: `ResumeAgent.analyze(resume: str, jd: str) -> dict[str, object]`
- Produces: `format_result_document(result: dict[str, object]) -> str`
- Produces: `write_result(path: pathlib.Path, result: dict[str, object]) -> None`

- [ ] **Step 1: Write failing orchestration and export tests**

```python
import json
import tempfile
import unittest
from pathlib import Path
from src.agent import ResumeAgent, format_result_document, write_result


class OfflineModel:
    def chat_json(self, prompt, temperature=0.0):
        raise RuntimeError("offline")


class AgentTests(unittest.TestCase):
    def test_run_returns_complete_standard_result(self):
        result = ResumeAgent(model_client=OfflineModel()).run(
            "本科计算机专业，3年经验。项目：使用Python和pytest设计测试用例。",
            "本科，3年以上，要求Python、SQL、pytest、接口测试，沟通协作。",
        )
        required = {
            "total_score", "scores", "jd_analysis", "matched_skills", "missing_skills",
            "unmet_hard_requirements", "rewritten_project_experience",
            "supplemental_keywords", "warnings", "summary",
        }
        self.assertTrue(required.issubset(result))
        self.assertIn("SQL", result["missing_skills"])

    def test_document_begins_with_parseable_json_then_summary(self):
        result = ResumeAgent(model_client=OfflineModel()).run("Python项目测试", "要求Python")
        document = format_result_document(result)
        json_part, summary_part = document.split("\n\n=== 文字总结 ===\n", 1)
        self.assertEqual(json.loads(json_part)["total_score"], result["total_score"])
        self.assertEqual(summary_part, result["summary"])

    def test_write_result_uses_utf8(self):
        result = {"summary": "中文总结", "warnings": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.txt"
            write_result(path, result)
            self.assertIn("中文总结", path.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Run tests and verify RED**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_agent -v`

Expected: FAIL because the current agent lacks `run`, injection, formatting, and export functions.

- [ ] **Step 3: Implement the four-stage pipeline and atomic export**

`ResumeAgent.__init__` accepts an optional model client and falls back to constructing `ModelClient` only when needed. `run` validates strings, then calls in order: `analyze_jd`, `score_resume`, `rewrite_projects_star`, `build_supplemental_keywords`. It assembles the exact schema from the design and generates a concise Chinese summary. `analyze` remains as a compatibility alias for `run`.

`format_result_document` uses `json.dumps(result, ensure_ascii=False, indent=2)` and appends the summary marker. `write_result` writes a sibling temporary file with UTF-8 and replaces the destination atomically.

- [ ] **Step 4: Run agent tests and verify GREEN**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_agent -v`

Expected: all agent tests pass.

---

### Task 6: Automatic root-relative command entry point

**Files:**
- Modify: `src/main.py`
- Create: `tests/test_main.py`
- Modify: `README.md`

**Interfaces:**
- Produces: `project_root() -> pathlib.Path`
- Produces: `run_from_files(root: pathlib.Path | None = None, agent: ResumeAgent | None = None) -> tuple[int, dict[str, object]]`
- Produces: `main() -> int`

- [ ] **Step 1: Write failing input-path and error tests**

```python
import tempfile
import unittest
from pathlib import Path
from src.main import run_from_files


class MainTests(unittest.TestCase):
    def test_reads_inputs_and_writes_result_in_supplied_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "resume.txt").write_text("Python测试项目", encoding="utf-8")
            (root / "jd.txt").write_text("要求Python", encoding="utf-8")
            code, result = run_from_files(root=root)
            self.assertEqual(code, 0)
            self.assertTrue((root / "result.txt").exists())
            self.assertIn("total_score", result)

    def test_missing_input_returns_structured_error_and_nonzero_code(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result = run_from_files(root=Path(directory))
            self.assertNotEqual(code, 0)
            self.assertEqual(result["error"]["code"], "INPUT_FILE_MISSING")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_main -v`

Expected: FAIL because `run_from_files` does not exist and the current module imports Gradio.

- [ ] **Step 3: Replace the Gradio entry point with automatic file execution**

Set the root to `Path(__file__).resolve().parent.parent`. Read both files with UTF-8, create structured error results for missing/empty/unreadable inputs, always write `result.txt` when the root is writable, print `format_result_document`, and return 0 only for a completed analysis. Use `raise SystemExit(main())` under the module guard.

Update README usage to:

```text
1. Place resume content in resume.txt and the job description in jd.txt.
2. Run: python src/main.py
3. Read the JSON result and Chinese summary in result.txt.
```

- [ ] **Step 4: Run main tests and verify GREEN**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_main -v`

Expected: all main tests pass.

---

### Task 7: Full verification and representative end-to-end run

**Files:**
- Verify: all Python sources and tests
- Generate during verification: `resume.txt`, `jd.txt`, `result.txt`

- [ ] **Step 1: Run the complete dependency-free test suite**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v`

Expected: all tests pass with zero errors and zero failures.

- [ ] **Step 2: Compile every Python source**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests`

Expected: exit code 0 with no syntax errors.

- [ ] **Step 3: Create representative project-root input fixtures**

Create `resume.txt` containing a testing resume with a本科计算机背景、3年经验、Python/pytest/测试用例/缺陷管理 project evidence. Create `jd.txt` requiring本科、3年、计算机、Python/SQL/pytest/接口测试 and communication/collaboration. These are sample inputs, not production facts.

- [ ] **Step 4: Run the automatic pipeline**

Run: `"C:\Users\15971\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" src/main.py`

Expected: exit code 0; `result.txt` contains a JSON object followed by `=== 文字总结 ===`; JSON includes scores totaling no more than 100, matched and missing skills, STAR data, supplemental keywords, warnings, and summary.

- [ ] **Step 5: Verify result semantics with a read-only check**

Parse the text before the summary marker with `json.loads`; assert all required fields exist, `SQL` and `接口测试` are missing for the sample resume, and no unsupported numeric claim appears in rewritten project text.

- [ ] **Step 6: Review the final diff against every requirement**

Check that no full resume/JD content is logged, no unrelated file structure changed, no default fake score remains, and the existing three business files keep their responsibilities.
