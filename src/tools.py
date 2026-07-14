"""Deterministic resume/JD analysis tools.

The scoring path deliberately does not import or initialize the language model.
This keeps scores reproducible and lets the application degrade cleanly when
Ollama is unavailable.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from typing import Any


SKILL_SYNONYMS: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "SQL": ("sql", "mysql", "postgresql", "数据库查询"),
    "pytest": ("pytest", "py.test"),
    "测试用例": ("测试用例", "用例设计", "test case", "test cases"),
    "缺陷管理": (
        "缺陷管理",
        "bug管理",
        "bug 管理",
        "缺陷跟踪",
        "缺陷追踪",
        "bug跟踪",
    ),
    "接口测试": ("接口测试", "api测试", "api 测试"),
    "黑盒测试": ("黑盒测试", "功能测试"),
    "自动化测试": (
        "自动化测试",
        "ui自动化",
        "ui 自动化",
        "接口自动化",
    ),
}

EDUCATION_LEVELS: dict[str, int] = {
    "中专": 1,
    "高中": 1,
    "大专": 2,
    "本科": 3,
    "硕士": 4,
    "博士": 5,
}

EDUCATION_ALIASES: dict[str, tuple[str, ...]] = {
    "中专": ("中专",),
    "高中": ("高中",),
    "大专": ("大专", "专科"),
    "本科": ("本科", "学士"),
    "硕士": ("硕士", "研究生"),
    "博士": ("博士",),
}

MAJOR_FAMILIES: dict[str, tuple[str, ...]] = {
    "计算机": ("计算机", "计算机科学", "计算机技术"),
    "软件工程": ("软件工程", "软件开发"),
    "软件测试": ("软件测试", "测试工程"),
}

SOFT_QUALITY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "沟通": ("沟通", "表达"),
    "协作": ("协作", "合作", "团队"),
    "责任心": ("责任心", "负责"),
    "学习能力": ("学习能力", "快速学习", "自学"),
    "问题分析": ("问题分析", "分析能力", "解决问题"),
}

SCORE_WEIGHTS = {
    "hard_requirements": 40.0,
    "technical_skills": 35.0,
    "project_experience": 25.0,
}

HARD_CAPS = {1: 59.0, 2: 39.0}

_TECH_MAJOR_FAMILIES = frozenset(MAJOR_FAMILIES)
_PROJECT_HEADING = re.compile(
    r"(?:项目经历|项目经验|项目\s*[:：]|工作经历|工作经验|职责\s*[:：])",
    re.IGNORECASE,
)
_NON_PROJECT_SECTION_HEADING = re.compile(
    r"(?m)^\s*(?:专业技能|技能|教育经历|教育背景|自我评价|个人总结|"
    r"证书|资格证书|基本信息)\s*(?::|：)?.*$",
    re.IGNORECASE,
)
_TEST_ACTIVITY_TERMS = (
    "测试",
    "用例",
    "缺陷",
    "接口",
    "自动化",
    "验证",
    "校验",
    "pytest",
)


def normalize_text(text: str) -> str:
    """Normalize text for case-insensitive, full-width-insensitive matching."""

    normalized = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"\s+", "", normalized)


def _contains_alias(text: str, aliases: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(alias) in normalized for alias in aliases)


def find_skills(text: str) -> list[str]:
    """Return canonical skill names once, in vocabulary order."""

    return [
        canonical
        for canonical, aliases in SKILL_SYNONYMS.items()
        if _contains_alias(text, aliases)
    ]


def _extract_education(text: str) -> list[dict[str, Any]]:
    mentioned = [
        level
        for level, aliases in EDUCATION_ALIASES.items()
        if _contains_alias(text, aliases)
    ]
    if not mentioned:
        return []
    level = max(mentioned, key=EDUCATION_LEVELS.__getitem__)
    return [
        {
            "level": level,
            "rank": EDUCATION_LEVELS[level],
            "evidence": next(
                alias
                for alias in EDUCATION_ALIASES[level]
                if normalize_text(alias) in normalize_text(text)
            ),
        }
    ]


def _extract_work_years(text: str) -> list[dict[str, Any]]:
    matches = list(
        re.finditer(
            r"(?<!\d)(\d+(?:\.\d+)?)\s*年"
            r"(?:(?:及以上|以上|左右)|(?:(?:软件测试|测试|相关|工作)\s*)?经验)",
            text or "",
        )
    )
    matches = [
        match
        for match in matches
        if not 1900 <= float(match.group(1)) <= 2099
    ]
    if not matches:
        return []
    selected = max(matches, key=lambda match: float(match.group(1)))
    number = float(selected.group(1))
    minimum: int | float = int(number) if number.is_integer() else number
    return [{"minimum": minimum, "evidence": selected.group(0)}]


def _extract_major(text: str) -> list[dict[str, Any]]:
    clauses = [
        clause.strip()
        for clause in re.split(r"[，。；;\n]+", text or "")
        if "专业" in clause
    ]
    major_context = "；".join(clauses)
    families = [
        family
        for family, aliases in MAJOR_FAMILIES.items()
        if _contains_alias(major_context, aliases)
    ]
    if not families:
        return []
    return [
        {
            "families": families,
            "evidence": clauses[0] if clauses else "、".join(families),
        }
    ]


def _find_soft_qualities(text: str) -> list[str]:
    return [
        canonical
        for canonical, aliases in SOFT_QUALITY_SYNONYMS.items()
        if _contains_alias(text, aliases)
    ]


def _extract_project_context(text: str) -> str:
    match = _PROJECT_HEADING.search(text or "")
    if not match:
        return ""
    source = text or ""
    start = source.rfind("\n", 0, match.start()) + 1
    remainder = source[match.end() :]
    next_section = _NON_PROJECT_SECTION_HEADING.search(remainder)
    end = match.end() + next_section.start() if next_section else len(source)
    return source[start:end].strip()


def _project_blocks(resume_text: str) -> list[str]:
    context = _extract_project_context(resume_text)
    if not context:
        return []
    project_starts = list(
        re.finditer(
            r"(?m)^\s*(?!(?:项目经历|项目经验|工作经历|工作经验|职责)\s*[:：])"
            r"[^\n:：]{2,50}\s*[:：]",
            context,
        )
    )
    if not project_starts:
        return [context]
    return [
        context[
            match.start() : (
                project_starts[index + 1].start()
                if index + 1 < len(project_starts)
                else len(context)
            )
        ].strip()
        for index, match in enumerate(project_starts)
    ]


def _hard_requirement_text(jd_text: str) -> str:
    segments = [
        segment.strip()
        for segment in re.split(r"[，,。；;\n]+", jd_text or "")
        if segment.strip()
    ]
    hard_markers = ("必须", "须", "最低", "硬性")
    preference_markers = ("优先", "加分", "更佳")
    accepted = []
    for segment in segments:
        if "不限" in segment:
            continue
        is_preference = any(marker in segment for marker in preference_markers)
        is_explicit_hard = any(marker in segment for marker in hard_markers)
        if is_preference and not is_explicit_hard:
            continue
        accepted.append(segment)
    return "；".join(accepted)


def analyze_jd(jd_text: str) -> dict[str, Any]:
    """Split a JD into hard gates, canonical skills, and soft qualities."""

    hard_text = _hard_requirement_text(jd_text)
    return {
        "hard_requirements": {
            "education": _extract_education(hard_text),
            "work_years": _extract_work_years(hard_text),
            "major": _extract_major(hard_text),
        },
        "technical_skills": find_skills(jd_text),
        "soft_qualities": _find_soft_qualities(jd_text),
    }


def enrich_jd_analysis(
    jd_text: str,
    base_analysis: dict[str, Any],
    model_client: object | None,
) -> tuple[dict[str, Any], list[str]]:
    """Accept model-supplemented JD items only with exact source evidence."""

    analysis = copy.deepcopy(base_analysis)
    if model_client is None:
        return analysis, []

    prompt = f"""请补充抽取规则可能漏掉的 JD 要求，只输出 JSON。
每一项 evidence 必须逐字复制自 JD 原文；不得推测或扩写。
允许的 JSON 结构：
{{
  "hard_requirements": [
    {{"category": "education", "level": "本科", "evidence": "原文"}},
    {{"category": "work_years", "minimum": 3, "evidence": "原文"}},
    {{"category": "major", "families": ["计算机"], "evidence": "原文"}}
  ],
  "technical_skills": [{{"name": "接口测试", "evidence": "原文"}}],
  "soft_qualities": [{{"name": "沟通", "evidence": "原文"}}]
}}
JD 原文：
{jd_text}
"""
    try:
        response = model_client.chat_json(prompt, temperature=0.0)
    except Exception:
        return analysis, ["MODEL_ERROR_JD_RULE_FALLBACK"]

    if not isinstance(response, dict):
        return analysis, ["INVALID_MODEL_JD_RULE_FALLBACK"]

    ignored = False

    def verified(item: Any) -> bool:
        nonlocal ignored
        evidence = item.get("evidence") if isinstance(item, dict) else None
        valid = (
            isinstance(evidence, str)
            and bool(evidence.strip())
            and evidence.strip() in jd_text
        )
        if not valid:
            ignored = True
        return valid

    hard = response.get("hard_requirements", [])
    if isinstance(hard, list):
        for item in hard:
            if not verified(item):
                continue
            category = item.get("category")
            evidence = item["evidence"].strip()
            target = analysis["hard_requirements"].get(category)
            if target is None or target:
                continue
            hard_evidence = _hard_requirement_text(evidence)
            if not hard_evidence:
                ignored = True
                continue
            if category == "education" and item.get("level") in EDUCATION_LEVELS:
                level = item["level"]
                extracted = _extract_education(hard_evidence)
                if not extracted or extracted[0]["level"] != level:
                    ignored = True
                    continue
                target.append(
                    {
                        "level": level,
                        "rank": EDUCATION_LEVELS[level],
                        "evidence": evidence,
                    }
                )
            elif category == "work_years":
                minimum = item.get("minimum")
                extracted = _extract_work_years(hard_evidence)
                if (
                    isinstance(minimum, (int, float))
                    and minimum > 0
                    and extracted
                    and float(extracted[0]["minimum"]) == float(minimum)
                ):
                    target.append({"minimum": minimum, "evidence": evidence})
                else:
                    ignored = True
            elif category == "major":
                families = item.get("families")
                if isinstance(families, list):
                    valid_families = [
                        family for family in families if family in MAJOR_FAMILIES
                    ]
                    extracted = _extract_major(hard_evidence)
                    extracted_families = (
                        extracted[0]["families"] if extracted else []
                    )
                    if valid_families and set(valid_families).issubset(
                        extracted_families
                    ):
                        target.append(
                            {"families": valid_families, "evidence": evidence}
                        )
                    else:
                        ignored = True

    technical = response.get("technical_skills", [])
    if isinstance(technical, list):
        for item in technical:
            if not verified(item):
                continue
            name = item.get("name")
            if (
                name in SKILL_SYNONYMS
                and name in find_skills(item["evidence"])
                and name not in analysis["technical_skills"]
            ):
                analysis["technical_skills"].append(name)
            elif name not in analysis["technical_skills"]:
                ignored = True

    soft = response.get("soft_qualities", [])
    if isinstance(soft, list):
        for item in soft:
            if not verified(item):
                continue
            name = item.get("name")
            if (
                name in SOFT_QUALITY_SYNONYMS
                and name in _find_soft_qualities(item["evidence"])
                and name not in analysis["soft_qualities"]
            ):
                analysis["soft_qualities"].append(name)
            elif name not in analysis["soft_qualities"]:
                ignored = True

    warnings = ["UNVERIFIED_MODEL_JD_ITEM_IGNORED"] if ignored else []
    return analysis, warnings


def extract_resume_profile(resume_text: str) -> dict[str, Any]:
    education = _extract_education(resume_text)
    work_years = _extract_work_years(resume_text)
    major = _extract_major(resume_text)
    return {
        "education_level": education[0]["level"] if education else None,
        "education_rank": education[0]["rank"] if education else None,
        "work_years": work_years[0]["minimum"] if work_years else None,
        "major_families": major[0]["families"] if major else [],
        "skills": find_skills(resume_text),
        "soft_qualities": _find_soft_qualities(resume_text),
        "project_context": _extract_project_context(resume_text),
    }


def _cap_for_unmet(count: int) -> float:
    if count <= 0:
        return 100.0
    if count >= 3:
        return 19.0
    return HARD_CAPS[count]


def _major_satisfied(actual: list[str], required: list[str]) -> bool:
    if set(actual) & set(required):
        return True
    return bool(set(actual) & _TECH_MAJOR_FAMILIES) and bool(
        set(required) & _TECH_MAJOR_FAMILIES
    )


def _score_hard_requirements(
    profile: dict[str, Any],
    requirements: dict[str, list[dict[str, Any]]],
) -> tuple[float, list[dict[str, str]]]:
    active_dimensions = [name for name, values in requirements.items() if values]
    if not active_dimensions:
        return SCORE_WEIGHTS["hard_requirements"], []

    passed = 0
    unmet: list[dict[str, str]] = []
    for dimension in active_dimensions:
        requirement = requirements[dimension][0]
        satisfied = False
        evidence = "未提供可验证信息"

        if dimension == "education":
            actual_rank = profile["education_rank"]
            satisfied = actual_rank is not None and actual_rank >= requirement["rank"]
            evidence = profile["education_level"] or evidence
            required_text = f"{requirement['level']}及以上"
        elif dimension == "work_years":
            actual_years = profile["work_years"]
            satisfied = (
                actual_years is not None
                and float(actual_years) >= float(requirement["minimum"])
            )
            evidence = f"{actual_years}年" if actual_years is not None else evidence
            required_text = f"{requirement['minimum']}年以上经验"
        else:
            actual_majors = profile["major_families"]
            required_majors = requirement["families"]
            satisfied = _major_satisfied(actual_majors, required_majors)
            evidence = "、".join(actual_majors) or evidence
            required_text = f"{'、'.join(required_majors)}相关专业"

        if satisfied:
            passed += 1
        else:
            unmet.append(
                {
                    "category": dimension,
                    "requirement": required_text,
                    "resume_evidence": evidence,
                    "reason": "简历信息未达到或无法验证该硬性条件",
                }
            )

    score = SCORE_WEIGHTS["hard_requirements"] * passed / len(active_dimensions)
    return round(score, 2), unmet


def _score_project_experience(
    profile: dict[str, Any], jd_analysis: dict[str, Any]
) -> float:
    context = profile["project_context"]
    if not context:
        return 0.0

    jd_skills = jd_analysis["technical_skills"]
    context_skills = find_skills(context)
    skill_coverage = (
        len(set(jd_skills) & set(context_skills)) / len(jd_skills)
        if jd_skills
        else 1.0
    )

    normalized_context = normalize_text(context)
    activity_hits = sum(
        1 for term in _TEST_ACTIVITY_TERMS if normalize_text(term) in normalized_context
    )
    activity_coverage = min(activity_hits / 4.0, 1.0)

    jd_soft = jd_analysis["soft_qualities"]
    context_soft = _find_soft_qualities(context)
    soft_coverage = (
        len(set(jd_soft) & set(context_soft)) / len(jd_soft) if jd_soft else 1.0
    )

    score = SCORE_WEIGHTS["project_experience"] * (
        0.60 * skill_coverage
        + 0.25 * activity_coverage
        + 0.15 * soft_coverage
    )
    return round(score, 2)


def score_resume(resume_text: str, jd_analysis: dict[str, Any]) -> dict[str, Any]:
    """Calculate explainable component scores and apply hard-gate caps."""

    profile = extract_resume_profile(resume_text)
    hard_score, unmet = _score_hard_requirements(
        profile, jd_analysis["hard_requirements"]
    )

    jd_skills = jd_analysis["technical_skills"]
    resume_skills = profile["skills"]
    matched = [skill for skill in jd_skills if skill in resume_skills]
    missing = [skill for skill in jd_skills if skill not in resume_skills]
    technical_score = (
        SCORE_WEIGHTS["technical_skills"] * len(matched) / len(jd_skills)
        if jd_skills
        else SCORE_WEIGHTS["technical_skills"]
    )
    technical_score = round(technical_score, 2)
    project_score = _score_project_experience(profile, jd_analysis)
    raw_total = round(hard_score + technical_score + project_score, 2)
    total = round(min(raw_total, _cap_for_unmet(len(unmet)), 100.0), 2)

    return {
        "total_score": total,
        "scores": {
            "hard_requirements": hard_score,
            "technical_skills": technical_score,
            "project_experience": project_score,
        },
        "matched_skills": matched,
        "missing_skills": missing,
        "unmet_hard_requirements": unmet,
    }


def _fallback_star(resume_text: str) -> list[dict[str, str]]:
    context = _extract_project_context(resume_text) or (resume_text or "").strip()
    context_without_heading = re.sub(
        r"^(?:项目经历|项目经验|工作经历|工作经验|职责)\s*[:：]?\s*",
        "",
        context,
        count=1,
    )
    if context_without_heading:
        context = context_without_heading
    context = context or "简历未提供明确项目经历"
    clauses = [part.strip() for part in re.split(r"[。；;\n]+", context) if part.strip()]
    source = clauses[0] if clauses else context
    source_parts = re.split(r"[:：]", source, maxsplit=1)
    situation = source_parts[0].strip() or source
    task = source_parts[1].strip() if len(source_parts) == 2 else source
    action = context
    result_candidates = [
        clause
        for clause in clauses
        if any(
            marker in clause
            for marker in ("完成", "提升", "降低", "上线", "交付", "验证", "关闭")
        )
    ]
    result = (
        result_candidates[-1]
        if result_candidates
        else "简历原文未提供可验证结果，建议补充真实成果"
    )
    return [
        {
            "situation": situation,
            "task": task,
            "action": action,
            "result": result,
            "star_text": (
                f"S（情境）：{situation}；T（任务）：{task}；"
                f"A（行动）：{action}；R（结果）：{result}。"
            ),
        }
    ]


def _model_projects_are_safe(
    projects: Any, resume_text: str, missing_skills: list[str]
) -> bool:
    if not isinstance(projects, list) or not projects:
        return False
    grounded_fields = ("situation", "task", "action", "result")
    for project in projects:
        if not isinstance(project, dict):
            return False
        if any(
            not isinstance(project.get(field), str) or not project[field].strip()
            for field in grounded_fields
        ):
            return False

    normalized_blocks = [normalize_text(block) for block in _project_blocks(resume_text)]
    if not normalized_blocks:
        return False
    for project in projects:
        normalized_fields = [
            normalize_text(project[field]) for field in grounded_fields
        ]
        if not any(
            all(field in block for field in normalized_fields)
            for block in normalized_blocks
        ):
            return False

    generated = "\n".join(
        project[field] for project in projects for field in grounded_fields
    )
    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", resume_text or ""))
    generated_numbers = set(re.findall(r"\d+(?:\.\d+)?", generated))
    if generated_numbers - source_numbers:
        return False
    generated_skills = set(find_skills(generated))
    if generated_skills & set(missing_skills):
        return False
    return True


def rewrite_projects_star(
    resume_text: str,
    jd_text: str,
    missing_skills: list[str],
    model_client: object | None,
) -> tuple[list[dict[str, str]], list[str]]:
    """Rewrite project evidence in STAR form without inventing resume facts."""

    if model_client is None:
        return _fallback_star(resume_text), ["MODEL_UNAVAILABLE_STAR_FALLBACK"]

    prompt = f"""你是严谨的中文简历编辑器。请依据简历已有事实改写项目经历。
严格使用 STAR 的 situation、task、action、result、star_text 五个字段。
situation、task、action、result 必须逐字摘录简历原文中的短语或句子；
程序会根据这四个有据可查的字段重新组合 star_text。
不得虚构技能、项目、年限、数字、比例或成果；缺失技能不得写成已经使用。
只输出 JSON：{{"projects": [{{"situation": "", "task": "", "action": "", "result": "", "star_text": ""}}]}}

简历原文：
{resume_text}

JD 全部条款：
{jd_text}

缺失技能（只能作为差距，不得写成已掌握）：{json.dumps(missing_skills, ensure_ascii=False)}
"""
    try:
        response = model_client.chat_json(prompt, temperature=0.2)
        projects = response.get("projects") if isinstance(response, dict) else None
        if _model_projects_are_safe(projects, resume_text, missing_skills):
            grounded_projects = []
            for project in projects:
                item = {
                    field: project[field].strip()
                    for field in ("situation", "task", "action", "result")
                }
                item["star_text"] = (
                    f"S（情境）：{item['situation']}；T（任务）：{item['task']}；"
                    f"A（行动）：{item['action']}；R（结果）：{item['result']}。"
                )
                grounded_projects.append(item)
            return grounded_projects, []
        return _fallback_star(resume_text), ["UNSAFE_MODEL_OUTPUT_STAR_FALLBACK"]
    except Exception:
        return _fallback_star(resume_text), ["MODEL_ERROR_STAR_FALLBACK"]


def build_supplemental_keywords(
    jd_analysis: dict[str, Any],
    missing_skills: list[str],
    resume_text: str = "",
) -> list[dict[str, str]]:
    """Build a stable list of technical and soft-quality terms to supplement."""

    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for skill in missing_skills:
        if skill in seen:
            continue
        items.append(
            {
                "keyword": skill,
                "reason": "JD 要求但简历未检出该技术能力",
                "suggested_section": "技能清单；仅在有真实经验时补充到项目经历",
            }
        )
        seen.add(skill)
    represented_soft = set(_find_soft_qualities(resume_text))
    for quality in jd_analysis.get("soft_qualities", []):
        if quality in represented_soft:
            continue
        if quality in seen:
            continue
        items.append(
            {
                "keyword": quality,
                "reason": "JD 强调的软素质，建议用真实项目行为体现",
                "suggested_section": "项目经历或自我评价",
            }
        )
        seen.add(quality)
    return items


def resume_jd_matcher(
    resume_text: str, jd_text: str, score_top: int = 3
) -> dict[str, Any]:
    """Backward-compatible deterministic matcher used by older callers."""

    del score_top
    analysis = analyze_jd(jd_text)
    result = score_resume(resume_text, analysis)
    return {
        "match_score": result["total_score"],
        "match_keywords": result["matched_skills"],
        "missing_skills": result["missing_skills"],
        "suggest": [
            item["reason"]
            for item in build_supplemental_keywords(
                analysis, result["missing_skills"]
            )
        ],
    }
