import unittest

from src.tools import (
    analyze_jd,
    build_supplemental_keywords,
    enrich_jd_analysis,
    extract_resume_profile,
    find_skills,
    rewrite_projects_star,
    score_resume,
)


class SkillAndJdTests(unittest.TestCase):
    def test_synonyms_are_normalized_and_deduplicated(self):
        text = "熟悉 PyTest、API测试、接口测试、Bug管理和功能测试"
        self.assertEqual(
            find_skills(text),
            ["pytest", "缺陷管理", "接口测试", "黑盒测试"],
        )

    def test_automation_synonyms_share_one_canonical_skill(self):
        self.assertEqual(
            find_skills("自动化测试、UI自动化、接口自动化"),
            ["自动化测试"],
        )

    def test_jd_is_split_into_three_categories(self):
        result = analyze_jd(
            "本科及以上，计算机相关专业，3年以上经验；"
            "熟悉Python、SQL和pytest；沟通协作能力强。"
        )
        self.assertEqual(
            result["hard_requirements"]["education"][0]["level"],
            "本科",
        )
        self.assertEqual(
            result["hard_requirements"]["work_years"][0]["minimum"],
            3,
        )
        self.assertIn(
            "计算机",
            result["hard_requirements"]["major"][0]["families"],
        )
        self.assertEqual(
            result["technical_skills"],
            ["Python", "SQL", "pytest"],
        )
        self.assertIn("沟通", result["soft_qualities"])
        self.assertIn("协作", result["soft_qualities"])

    def test_resume_profile_extracts_verifiable_hard_facts(self):
        profile = extract_resume_profile(
            "本科学历，软件工程专业，4年软件测试经验。"
        )
        self.assertEqual(profile["education_level"], "本科")
        self.assertEqual(profile["work_years"], 4)
        self.assertIn("软件工程", profile["major_families"])

    def test_major_extraction_ignores_testing_experience_clause(self):
        result = analyze_jd("计算机相关专业，3年以上软件测试经验。")
        self.assertEqual(
            result["hard_requirements"]["major"][0]["families"],
            ["计算机"],
        )

    def test_calendar_years_are_not_treated_as_experience(self):
        profile = extract_resume_profile(
            "2020年-2023年在某公司任职，具有2年软件测试经验。"
        )
        self.assertEqual(profile["work_years"], 2)

    def test_date_only_resume_has_no_verifiable_experience_years(self):
        profile = extract_resume_profile("工作经历：2020年-2023年，测试工程师。")
        self.assertIsNone(profile["work_years"])

    def test_project_context_stops_before_following_skills_section(self):
        profile = extract_resume_profile(
            "项目经历\n质量项目：使用Python执行测试。\n技能\nSQL、pytest"
        )
        self.assertIn("Python", profile["project_context"])
        self.assertNotIn("SQL", profile["project_context"])

    def test_preferred_background_is_not_classified_as_hard_gate(self):
        result = analyze_jd(
            "本科或计算机相关专业优先；必须具备3年以上测试经验。"
        )
        self.assertEqual(result["hard_requirements"]["education"], [])
        self.assertEqual(result["hard_requirements"]["major"], [])
        self.assertEqual(
            result["hard_requirements"]["work_years"][0]["minimum"], 3
        )

    def test_threshold_wording_does_not_make_preference_mandatory(self):
        result = analyze_jd("本科及以上学历优先，3年以上经验优先，要求Python。")
        self.assertEqual(result["hard_requirements"]["education"], [])
        self.assertEqual(result["hard_requirements"]["work_years"], [])


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.jd = analyze_jd(
            "本科及以上，计算机相关专业，3年以上经验；"
            "要求Python、SQL、pytest、接口测试。"
        )

    def test_full_hard_requirements_score_40(self):
        result = score_resume(
            "本科，计算机专业，4年经验，Python SQL pytest 接口测试。",
            self.jd,
        )
        self.assertEqual(result["scores"]["hard_requirements"], 40.0)
        self.assertEqual(result["unmet_hard_requirements"], [])

    def test_one_unmet_hard_requirement_caps_total_at_59(self):
        result = score_resume(
            "大专，计算机专业，4年经验。"
            "项目经历：使用Python、SQL、pytest完成接口测试。",
            self.jd,
        )
        self.assertLessEqual(result["total_score"], 59.0)
        self.assertEqual(len(result["unmet_hard_requirements"]), 1)

    def test_two_and_three_unmet_requirements_apply_stricter_caps(self):
        two = score_resume(
            "大专，市场营销专业，4年经验。Python SQL pytest 接口测试。",
            self.jd,
        )
        three = score_resume(
            "大专，市场营销专业，1年经验。Python SQL pytest 接口测试。",
            self.jd,
        )
        self.assertLessEqual(two["total_score"], 39.0)
        self.assertLessEqual(three["total_score"], 19.0)

    def test_project_evidence_scores_higher_than_skill_list_only(self):
        listed = score_resume(
            "本科计算机专业，4年经验。技能：Python、SQL、pytest、接口测试。",
            self.jd,
        )
        evidenced = score_resume(
            "本科计算机专业，4年经验。项目经历：使用Python和pytest编写"
            "接口测试，执行SQL校验并跟踪缺陷。",
            self.jd,
        )
        self.assertGreater(
            evidenced["scores"]["project_experience"],
            listed["scores"]["project_experience"],
        )

    def test_missing_resume_hard_fact_is_not_assumed_satisfied(self):
        result = score_resume("技能：Python SQL pytest 接口测试。", self.jd)
        self.assertEqual(len(result["unmet_hard_requirements"]), 3)
        self.assertLessEqual(result["total_score"], 19.0)

    def test_jd_without_hard_or_technical_requirements_has_stable_defaults(self):
        analysis = analyze_jd("负责质量保障，具备良好沟通能力。")
        result = score_resume("项目经历：负责质量保障和问题分析。", analysis)
        self.assertEqual(result["scores"]["hard_requirements"], 40.0)
        self.assertEqual(result["scores"]["technical_skills"], 35.0)


class FakeModel:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def chat_json(self, prompt, temperature=0.0):
        if self.error:
            raise self.error
        return self.result


class RewriteTests(unittest.TestCase):
    def test_model_can_add_complex_hard_requirement_with_source_evidence(self):
        jd_text = "候选人须具备学士学位，并熟悉Python。"
        model = FakeModel(
            {
                "hard_requirements": [
                    {
                        "category": "education",
                        "level": "本科",
                        "evidence": "须具备学士学位",
                    }
                ]
            }
        )
        analysis, warnings = enrich_jd_analysis(
            jd_text, analyze_jd(jd_text), model
        )
        self.assertEqual(
            analysis["hard_requirements"]["education"][0]["level"],
            "本科",
        )
        self.assertEqual(warnings, [])

    def test_model_requirement_without_exact_source_evidence_is_ignored(self):
        jd_text = "熟悉Python。"
        model = FakeModel(
            {
                "hard_requirements": [
                    {
                        "category": "education",
                        "level": "本科",
                        "evidence": "本科及以上",
                    }
                ]
            }
        )
        analysis, warnings = enrich_jd_analysis(
            jd_text, analyze_jd(jd_text), model
        )
        self.assertEqual(analysis["hard_requirements"]["education"], [])
        self.assertIn("UNVERIFIED_MODEL_JD_ITEM_IGNORED", warnings)

    def test_model_evidence_must_semantically_support_proposed_value(self):
        jd_text = "岗位重视沟通能力。"
        model = FakeModel(
            {
                "hard_requirements": [
                    {
                        "category": "work_years",
                        "minimum": 99,
                        "evidence": "沟通能力",
                    }
                ],
                "technical_skills": [
                    {"name": "SQL", "evidence": "沟通能力"}
                ],
            }
        )
        analysis, warnings = enrich_jd_analysis(
            jd_text, analyze_jd(jd_text), model
        )
        self.assertEqual(analysis["hard_requirements"]["work_years"], [])
        self.assertNotIn("SQL", analysis["technical_skills"])
        self.assertIn("UNVERIFIED_MODEL_JD_ITEM_IGNORED", warnings)

    def test_model_cannot_restore_preference_as_hard_requirement(self):
        jd_text = "本科优先，学历不限，要求Python。"
        model = FakeModel(
            {
                "hard_requirements": [
                    {
                        "category": "education",
                        "level": "本科",
                        "evidence": "本科优先",
                    }
                ]
            }
        )
        analysis, warnings = enrich_jd_analysis(
            jd_text, analyze_jd(jd_text), model
        )
        self.assertEqual(analysis["hard_requirements"]["education"], [])
        self.assertIn("UNVERIFIED_MODEL_JD_ITEM_IGNORED", warnings)

    def test_model_star_is_returned_when_fact_safe(self):
        model = FakeModel(
            {
                "projects": [
                    {
                        "situation": "电商项目",
                        "task": "负责接口质量验证",
                        "action": "使用Python完成接口检查",
                        "result": "完成核心流程验证",
                        "star_text": (
                            "在电商项目中负责接口质量验证，使用Python完成接口检查，"
                            "完成核心流程验证。"
                        ),
                    }
                ]
            }
        )
        projects, warnings = rewrite_projects_star(
            "电商项目：负责接口质量验证，使用Python完成接口检查，"
            "完成核心流程验证。",
            "要求Python和SQL",
            ["SQL"],
            model,
        )
        self.assertEqual(projects[0]["situation"], "电商项目")
        self.assertEqual(warnings, [])

    def test_new_numbers_force_conservative_fallback(self):
        model = FakeModel(
            {
                "projects": [
                    {
                        "situation": "项目",
                        "task": "测试",
                        "action": "执行测试",
                        "result": "效率提升30%",
                        "star_text": "效率提升30%",
                    }
                ]
            }
        )
        projects, warnings = rewrite_projects_star(
            "项目：执行测试。", "要求测试", [], model
        )
        self.assertNotIn("30", projects[0]["star_text"])
        self.assertTrue(warnings)

    def test_invented_non_vocabulary_tool_forces_fallback(self):
        model = FakeModel(
            {
                "projects": [
                    {
                        "situation": "电商项目",
                        "task": "负责质量验证",
                        "action": "使用Docker搭建测试环境",
                        "result": "保障稳定交付",
                        "star_text": "在电商项目中使用Docker保障稳定交付。",
                    }
                ]
            }
        )
        projects, warnings = rewrite_projects_star(
            "电商项目：负责质量验证。", "要求Python", ["Python"], model
        )
        self.assertNotIn("Docker", projects[0]["star_text"])
        self.assertIn("UNSAFE_MODEL_OUTPUT_STAR_FALLBACK", warnings)

    def test_skill_section_fact_cannot_be_reassigned_to_project_action(self):
        model = FakeModel(
            {
                "projects": [
                    {
                        "situation": "电商项目",
                        "task": "负责接口验证",
                        "action": "使用Docker搭建环境",
                        "result": "完成接口验证",
                        "star_text": "电商项目中使用Docker完成接口验证。",
                    }
                ]
            }
        )
        resume = (
            "技能\n使用Docker搭建环境\n"
            "项目经历\n电商项目：负责接口验证，完成接口验证。"
        )
        projects, warnings = rewrite_projects_star(
            resume, "要求接口测试", ["接口测试"], model
        )
        self.assertNotIn("Docker", projects[0]["star_text"])
        self.assertIn("UNSAFE_MODEL_OUTPUT_STAR_FALLBACK", warnings)

    def test_facts_from_two_named_projects_cannot_be_combined(self):
        model = FakeModel(
            {
                "projects": [
                    {
                        "situation": "电商平台",
                        "task": "负责功能验证",
                        "action": "执行SQL数据校验",
                        "result": "完成支付验证",
                        "star_text": "电商平台中执行SQL数据校验。",
                    }
                ]
            }
        )
        resume = (
            "项目经历\n"
            "电商平台：负责功能验证。\n"
            "支付系统：执行SQL数据校验，完成支付验证。"
        )
        projects, warnings = rewrite_projects_star(
            resume, "要求SQL", [], model
        )
        self.assertNotIn("电商平台中执行SQL", projects[0]["star_text"])
        self.assertIn("UNSAFE_MODEL_OUTPUT_STAR_FALLBACK", warnings)

    def test_fallback_does_not_assert_unstated_testing_or_completion(self):
        projects, _ = rewrite_projects_star(
            "项目经历\n内容平台项目：整理需求文档。",
            "要求Python",
            ["Python"],
            None,
        )
        text = projects[0]["star_text"]
        self.assertNotIn("完成相关测试与质量工作", text)
        self.assertNotIn("完成原简历所述项目工作", text)

    def test_model_failure_uses_complete_star_fallback(self):
        projects, warnings = rewrite_projects_star(
            "项目：设计测试用例并跟踪缺陷。",
            "要求接口测试",
            ["接口测试"],
            FakeModel(error=RuntimeError("offline")),
        )
        self.assertEqual(
            set(projects[0]),
            {"situation", "task", "action", "result", "star_text"},
        )
        self.assertTrue(warnings)

    def test_fallback_star_uses_project_name_instead_of_section_heading(self):
        projects, _ = rewrite_projects_star(
            "项目经历\n电商平台项目：设计测试用例并跟踪缺陷。",
            "要求测试用例",
            [],
            None,
        )
        self.assertEqual(projects[0]["situation"], "电商平台项目")

    def test_supplemental_keywords_put_missing_technical_skills_first(self):
        jd_analysis = analyze_jd("要求Python和SQL，具备沟通能力。")
        items = build_supplemental_keywords(jd_analysis, ["SQL"])
        self.assertEqual(items[0]["keyword"], "SQL")
        self.assertEqual(
            set(items[0]),
            {"keyword", "reason", "suggested_section"},
        )

    def test_supplemental_keywords_exclude_soft_qualities_already_evidenced(self):
        jd_analysis = analyze_jd("要求Python，重视沟通协作和责任心。")
        items = build_supplemental_keywords(
            jd_analysis,
            [],
            resume_text="项目经历：主动沟通并与团队协作。",
        )
        keywords = [item["keyword"] for item in items]
        self.assertNotIn("沟通", keywords)
        self.assertNotIn("协作", keywords)
        self.assertIn("责任心", keywords)


if __name__ == "__main__":
    unittest.main()
