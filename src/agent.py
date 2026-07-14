"""Serial orchestration for resume/JD matching and optimization."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.model_client import ModelClient
from src.tools import (
    analyze_jd,
    build_supplemental_keywords,
    enrich_jd_analysis,
    rewrite_projects_star,
    score_resume,
)


logger = logging.getLogger(__name__)
_DEFAULT_MODEL = object()


def _join_or_none(items: list[str]) -> str:
    return "、".join(items) if items else "无"


def _build_summary(result: dict[str, Any]) -> str:
    scores = result["scores"]
    unmet = result["unmet_hard_requirements"]
    unmet_text = (
        "；".join(item["requirement"] for item in unmet) if unmet else "无"
    )
    return (
        f"总分：{result['total_score']}分。"
        f"分项得分：硬性条件 {scores['hard_requirements']}分，"
        f"技术技能 {scores['technical_skills']}分，"
        f"项目经历 {scores['project_experience']}分。"
        f"已匹配技能：{_join_or_none(result['matched_skills'])}。"
        f"缺失技能：{_join_or_none(result['missing_skills'])}。"
        f"不满足的硬性条件：{unmet_text}。"
        "STAR 项目改写仅使用简历已有事实；缺失技能应在具备真实经验后再补充。"
    )


def format_result_document(result: dict[str, Any]) -> str:
    """Return standard JSON followed by a human-readable Chinese summary."""

    json_text = json.dumps(result, ensure_ascii=False, indent=2)
    return f"{json_text}\n\n=== 文字总结 ===\n{result.get('summary', '')}"


def write_result(path: Path, result: dict[str, Any]) -> None:
    """Atomically write a UTF-8 result document."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f"{destination.name}.tmp")
    try:
        temporary.write_text(format_result_document(result), encoding="utf-8")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


class ResumeAgent:
    def __init__(self, model_client: object = _DEFAULT_MODEL) -> None:
        self._initial_warnings: list[str] = []
        if model_client is _DEFAULT_MODEL:
            try:
                self.model_client = ModelClient()
            except (TypeError, ValueError):
                self.model_client = None
                self._initial_warnings.append("MODEL_CONFIGURATION_ERROR")
        else:
            self.model_client = model_client

    def run(self, resume: str, jd: str) -> dict[str, Any]:
        """Run analysis, STAR rewrite, and keyword generation in sequence."""

        if not isinstance(resume, str) or not resume.strip():
            return {
                "error": {
                    "code": "EMPTY_INPUT",
                    "message": "简历内容不能为空",
                },
                "warnings": [],
                "summary": "分析未执行：简历内容为空。",
            }
        if not isinstance(jd, str) or not jd.strip():
            return {
                "error": {
                    "code": "EMPTY_INPUT",
                    "message": "JD 内容不能为空",
                },
                "warnings": [],
                "summary": "分析未执行：JD 内容为空。",
            }

        logger.info(
            "开始简历匹配分析：resume_length=%s jd_length=%s",
            len(resume),
            len(jd),
        )

        base_jd_analysis = analyze_jd(jd)
        jd_analysis, jd_warnings = enrich_jd_analysis(
            jd, base_jd_analysis, self.model_client
        )
        scoring = score_resume(resume, jd_analysis)
        rewritten, rewrite_warnings = rewrite_projects_star(
            resume,
            jd,
            scoring["missing_skills"],
            self.model_client,
        )
        supplemental = build_supplemental_keywords(
            jd_analysis, scoring["missing_skills"], resume_text=resume
        )

        result: dict[str, Any] = {
            "total_score": scoring["total_score"],
            "scores": scoring["scores"],
            "jd_analysis": jd_analysis,
            "matched_skills": scoring["matched_skills"],
            "missing_skills": scoring["missing_skills"],
            "unmet_hard_requirements": scoring[
                "unmet_hard_requirements"
            ],
            "rewritten_project_experience": rewritten,
            "supplemental_keywords": supplemental,
            "warnings": self._initial_warnings + jd_warnings + rewrite_warnings,
            "summary": "",
        }
        result["summary"] = _build_summary(result)
        logger.info(
            "简历匹配分析完成：total_score=%s warnings=%s",
            result["total_score"],
            len(result["warnings"]),
        )
        return result

    def analyze(self, resume: str, jd: str) -> dict[str, Any]:
        """Compatibility alias retained for existing callers."""

        return self.run(resume, jd)
