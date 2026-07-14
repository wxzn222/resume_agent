import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.agent import ResumeAgent, format_result_document, write_result


class OfflineModel:
    def chat_json(self, prompt, temperature=0.0):
        raise RuntimeError("offline")


class EvidenceModel:
    def __init__(self):
        self.prompts = []

    def chat_json(self, prompt, temperature=0.0):
        self.prompts.append(prompt)
        if "补充抽取规则可能漏掉的 JD 要求" in prompt:
            return {
                "hard_requirements": [
                    {
                        "category": "education",
                        "level": "本科",
                        "evidence": "须具备学士学位",
                    }
                ]
            }
        return {
            "projects": [
                {
                    "situation": "质量项目",
                    "task": "执行测试",
                    "action": "使用Python执行测试",
                    "result": "完成测试",
                    "star_text": "质量项目中使用Python执行测试并完成测试。",
                }
            ]
        }


class AgentTests(unittest.TestCase):
    def test_complex_jd_enrichment_runs_before_scoring_and_star_rewrite(self):
        model = EvidenceModel()
        result = ResumeAgent(model_client=model).run(
            "本科学历。项目经历：质量项目中使用Python执行测试。",
            "候选人须具备学士学位，并熟悉Python。",
        )
        self.assertEqual(
            result["jd_analysis"]["hard_requirements"]["education"][0][
                "level"
            ],
            "本科",
        )
        self.assertEqual(len(model.prompts), 2)
        self.assertIn("补充抽取", model.prompts[0])
        self.assertIn("STAR", model.prompts[1])

    def test_run_returns_complete_standard_result(self):
        result = ResumeAgent(model_client=OfflineModel()).run(
            "本科计算机专业，3年经验。项目经历：使用Python和pytest设计测试用例。",
            "本科，3年以上，计算机相关专业；要求Python、SQL、pytest、"
            "接口测试，重视沟通协作。",
        )
        required = {
            "total_score",
            "scores",
            "jd_analysis",
            "matched_skills",
            "missing_skills",
            "unmet_hard_requirements",
            "rewritten_project_experience",
            "supplemental_keywords",
            "warnings",
            "summary",
        }
        self.assertTrue(required.issubset(result))
        self.assertIn("SQL", result["missing_skills"])
        self.assertIn("接口测试", result["missing_skills"])
        self.assertTrue(result["rewritten_project_experience"])

    def test_analyze_is_compatibility_alias_for_run(self):
        agent = ResumeAgent(model_client=None)
        result = agent.analyze("项目经历：Python测试。", "要求Python")
        self.assertIn("total_score", result)

    def test_empty_input_returns_structured_error(self):
        result = ResumeAgent(model_client=None).run("", "要求Python")
        self.assertEqual(result["error"]["code"], "EMPTY_INPUT")

    def test_invalid_model_timeout_does_not_block_rule_scoring(self):
        with patch.dict(os.environ, {"MODEL_TIMEOUT_SECONDS": "invalid"}):
            agent = ResumeAgent()
            result = agent.run("项目经历：Python测试。", "要求Python")
        self.assertIn("total_score", result)
        self.assertIn("MODEL_CONFIGURATION_ERROR", result["warnings"])

    def test_document_begins_with_parseable_json_then_summary(self):
        result = ResumeAgent(model_client=OfflineModel()).run(
            "Python项目测试", "要求Python"
        )
        document = format_result_document(result)
        json_part, summary_part = document.split(
            "\n\n=== 文字总结 ===\n", 1
        )
        self.assertEqual(
            json.loads(json_part)["total_score"], result["total_score"]
        )
        self.assertEqual(summary_part, result["summary"])

    def test_write_result_uses_utf8(self):
        result = {"summary": "中文总结", "warnings": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.txt"
            write_result(path, result)
            self.assertIn("中文总结", path.read_text(encoding="utf-8"))
            self.assertFalse((path.parent / "result.txt.tmp").exists())


if __name__ == "__main__":
    unittest.main()
