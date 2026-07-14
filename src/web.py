"""Local web callbacks for the resume/JD matching Agent."""

from __future__ import annotations

import html
import re
import sys
import uuid
from pathlib import Path
from typing import Any


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import ResumeAgent, write_result


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_root(root: Path | None) -> Path:
    return Path(root).resolve() if root is not None else project_root()


def load_inputs(root: Path | None = None) -> tuple[str, str, str]:
    """Load editable UTF-8 inputs independently from the selected root."""

    base = _resolve_root(root)
    values: dict[str, str] = {"resume.txt": "", "jd.txt": ""}
    issues: list[str] = []

    for name in values:
        path = base / name
        if not path.is_file():
            issues.append(f"缺少 {name}")
            continue
        try:
            values[name] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(f"{name} 读取失败（{type(exc).__name__}）")

    if issues:
        status = "⚠️ " + "；".join(issues) + "。可在页面填写后显式保存。"
    else:
        empty = [name for name, value in values.items() if not value.strip()]
        status = (
            "⚠️ " + "、".join(empty) + " 内容为空，可在页面中编辑。"
            if empty
            else "✅ 已加载 resume.txt 和 jd.txt。"
        )
    return values["resume.txt"], values["jd.txt"], status


def save_inputs(
    resume: str,
    jd: str,
    root: Path | None = None,
) -> str:
    """Explicitly persist both page inputs as UTF-8 files."""

    if not isinstance(resume, str) or not resume.strip():
        return "❌ 简历内容不能为空，未修改本地文件。"
    if not isinstance(jd, str) or not jd.strip():
        return "❌ JD 内容不能为空，未修改本地文件。"

    base = _resolve_root(root)
    resume_path = base / "resume.txt"
    jd_path = base / "jd.txt"
    targets = {
        resume_path: resume,
        jd_path: jd,
    }
    token = uuid.uuid4().hex
    temporary_files = {
        target: target.with_name(f".{target.name}.{token}.tmp")
        for target in targets
    }
    backup_files = {
        target: target.with_name(f".{target.name}.{token}.bak")
        for target in targets
    }
    originally_existed = {target: target.exists() for target in targets}

    try:
        base.mkdir(parents=True, exist_ok=True)
        for target, content in targets.items():
            temporary_files[target].write_text(content, encoding="utf-8")
        for target in targets:
            if target.exists():
                target.replace(backup_files[target])
        for target in targets:
            temporary_files[target].replace(target)
    except OSError as exc:
        rollback_failed = False
        for target in reversed(targets):
            backup = backup_files[target]
            try:
                if backup.exists():
                    if target.exists():
                        target.unlink()
                    backup.replace(target)
                elif not originally_existed[target] and target.exists():
                    target.unlink()
            except OSError:
                rollback_failed = True
        rollback_note = "；回滚未完全成功，请检查隐藏备份文件" if rollback_failed else ""
        return (
            f"❌ 保存失败（{type(exc).__name__}），已保留原文件{rollback_note}。"
        )
    else:
        cleanup_failed = False
        for backup in backup_files.values():
            if backup.exists():
                try:
                    backup.unlink()
                except OSError:
                    cleanup_failed = True
        if cleanup_failed:
            return "✅ 文件保存成功；旧版本隐藏备份未能清理。"
        return "✅ resume.txt 和 jd.txt 保存成功。"
    finally:
        for path in temporary_files.values():
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass


_MARKDOWN_SPECIALS = frozenset("\\`*_{}[]()#+-!|")


def _md(value: Any) -> str:
    """Render untrusted text literally inside a Markdown component."""

    text = html.escape(str(value if value is not None else ""), quote=True)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    escaped_lines: list[str] = []
    for line in lines:
        escaped = "".join(
            f"\\{character}" if character in _MARKDOWN_SPECIALS else character
            for character in line
        )
        escaped_lines.append(re.sub(r"^(\s*\d+)\.(?=\s)", r"\1\\.", escaped))
    return "<br>".join(escaped_lines)


def _bullet_list(values: Any, empty_text: str = "无") -> str:
    if not isinstance(values, list) or not values:
        return f"- {empty_text}"
    return "\n".join(f"- {_md(value)}" for value in values)


def render_result(
    result: dict[str, Any],
) -> tuple[str, str, str, str, dict[str, Any], str]:
    """Convert one Agent result into all approved page views."""

    if not isinstance(result, dict):
        result = {
            "error": {"code": "INVALID_RESULT", "message": "结果格式无效"},
            "warnings": [],
            "summary": "分析失败。",
        }

    error = result.get("error")
    if isinstance(error, dict):
        message = _md(error.get("message", "分析失败"))
        return (
            f"### 暂无评分\n\n{message}",
            "### 匹配分析\n\n暂无结果",
            "### STAR 改写\n\n暂无结果",
            "### 增补关键词\n\n暂无结果",
            result,
            _md(result.get("summary", message)),
        )

    scores = result.get("scores") if isinstance(result.get("scores"), dict) else {}
    score_view = (
        f"## 总分：{_md(result.get('total_score', 'N/A'))}\n\n"
        "| 分项 | 得分 |\n|---|---:|\n"
        f"| 硬性条件 | {_md(scores.get('hard_requirements', 'N/A'))} |\n"
        f"| 技术技能 | {_md(scores.get('technical_skills', 'N/A'))} |\n"
        f"| 项目经历 | {_md(scores.get('project_experience', 'N/A'))} |"
    )

    matched = result.get("matched_skills", [])
    missing = result.get("missing_skills", [])
    unmet = result.get("unmet_hard_requirements", [])
    unmet_lines: list[str] = []
    if isinstance(unmet, list):
        for item in unmet:
            if isinstance(item, dict):
                unmet_lines.append(
                    f"- **{_md(item.get('requirement', '未说明要求'))}**："
                    f"{_md(item.get('reason', '未达到要求'))}"
                )
            else:
                unmet_lines.append(f"- {_md(item)}")
    unmet_view = "\n".join(unmet_lines) if unmet_lines else "- 无"
    matching_view = (
        "### 已匹配技能\n"
        f"{_bullet_list(matched)}\n\n"
        "### 缺失技能\n"
        f"{_bullet_list(missing)}\n\n"
        "### 不满足的硬性条件\n"
        f"{unmet_view}"
    )

    projects = result.get("rewritten_project_experience", [])
    project_sections: list[str] = []
    if isinstance(projects, list):
        for index, project in enumerate(projects, start=1):
            if not isinstance(project, dict):
                continue
            project_sections.append(
                f"### 项目 {index}\n"
                f"- **Situation：** {_md(project.get('situation', ''))}\n"
                f"- **Task：** {_md(project.get('task', ''))}\n"
                f"- **Action：** {_md(project.get('action', ''))}\n"
                f"- **Result：** {_md(project.get('result', ''))}\n\n"
                f"> {_md(project.get('star_text', ''))}"
            )
    star_view = "\n\n".join(project_sections) or "### STAR 改写\n\n暂无项目结果"

    supplements = result.get("supplemental_keywords", [])
    keyword_rows = ["| 关键词 | 原因 | 建议位置 |", "|---|---|---|"]
    if isinstance(supplements, list):
        for item in supplements:
            if not isinstance(item, dict):
                continue
            keyword_rows.append(
                f"| {_md(item.get('keyword', ''))} "
                f"| {_md(item.get('reason', ''))} "
                f"| {_md(item.get('suggested_section', ''))} |"
            )
    if len(keyword_rows) == 2:
        keyword_rows.append("| 无 | 无需增补 | - |")
    keyword_view = "\n".join(keyword_rows)

    summary = _md(result.get("summary", ""))
    return score_view, matching_view, star_view, keyword_view, result, summary


def _empty_analysis_outputs(status: str) -> tuple[
    str, str, str, str, str, dict[str, Any], str
]:
    empty_result: dict[str, Any] = {}
    return (
        status,
        "### 暂无评分",
        "### 匹配分析\n\n暂无结果",
        "### STAR 改写\n\n暂无结果",
        "### 增补关键词\n\n暂无结果",
        empty_result,
        "",
    )


def analyze_inputs(
    resume: str,
    jd: str,
    root: Path | None = None,
    agent: object | None = None,
) -> tuple[str, str, str, str, str, dict[str, Any], str]:
    """Analyze current page text without persisting the two input files."""

    if not isinstance(resume, str) or not resume.strip():
        return _empty_analysis_outputs("❌ 简历内容不能为空，未启动分析。")
    if not isinstance(jd, str) or not jd.strip():
        return _empty_analysis_outputs("❌ JD 内容不能为空，未启动分析。")

    runner = agent if agent is not None else ResumeAgent()
    try:
        result = runner.run(resume, jd)
    except Exception as exc:
        return _empty_analysis_outputs(
            f"❌ 分析失败（{type(exc).__name__}），请检查模型与输入配置。"
        )

    views = render_result(result)
    error = result.get("error") if isinstance(result, dict) else None
    if isinstance(error, dict):
        status = f"❌ {_md(error.get('message', '分析失败'))}"
        return (status, *views)

    base = _resolve_root(root)
    try:
        write_result(base / "result.txt", result)
        status = "✅ 分析完成，结果已保存到 result.txt。"
    except OSError as exc:
        status = (
            f"⚠️ 分析完成，但 result.txt 保存失败（{type(exc).__name__}）。"
        )

    warnings = result.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        status += "\n\n模型降级提示：" + "、".join(_md(item) for item in warnings)
    return (status, *views)


_PAGE_CSS = """
.gradio-container { max-width: 1440px !important; margin: 0 auto !important; }
.app-title { text-align: center; margin: 0.5rem 0 0.25rem; }
.app-subtitle { text-align: center; color: #64748b; margin-bottom: 1rem; }
.status-panel { border-radius: 12px; padding: 0.2rem 0.8rem; }
.primary-action { min-height: 46px; font-weight: 700; }
@media (max-width: 768px) {
  .gradio-container { padding: 0.5rem !important; }
}
"""


def build_demo(root: Path | None = None, agent: object | None = None) -> object:
    """Build the local Gradio page without launching a server."""

    try:
        import gradio as gr
    except ImportError as exc:
        raise RuntimeError("缺少 gradio，请先安装项目依赖") from exc

    base = _resolve_root(root)

    def load_callback() -> tuple[str, str, str]:
        return load_inputs(base)

    def save_callback(resume: str, jd: str) -> str:
        return save_inputs(resume, jd, base)

    def analyze_callback(
        resume: str, jd: str
    ) -> tuple[str, str, str, str, str, dict[str, Any], str]:
        return analyze_inputs(resume, jd, base, agent)

    with gr.Blocks(title="简历 JD 精准匹配 Agent") as demo:
        gr.Markdown(
            "# 简历 JD 精准匹配 Agent",
            elem_classes=["app-title"],
        )
        gr.Markdown(
            "自动加载本地文件，精准评分、STAR 改写并生成增补关键词。",
            elem_classes=["app-subtitle"],
        )
        status = gr.Markdown(
            "正在读取 resume.txt 和 jd.txt…",
            elem_classes=["status-panel"],
        )

        with gr.Row():
            resume_input = gr.Textbox(
                label="简历内容",
                lines=18,
                placeholder="页面打开后会自动加载 resume.txt，也可在此临时编辑。",
            )
            jd_input = gr.Textbox(
                label="岗位 JD",
                lines=18,
                placeholder="页面打开后会自动加载 jd.txt，也可在此临时编辑。",
            )

        with gr.Row():
            analyze_button = gr.Button(
                "开始精准分析",
                variant="primary",
                elem_classes=["primary-action"],
            )
            reload_button = gr.Button("重新加载文件", variant="secondary")
            save_button = gr.Button("保存到文件", variant="secondary")

        with gr.Tabs():
            with gr.Tab("评分总览"):
                score_output = gr.Markdown("### 暂无评分")
                summary_output = gr.Markdown()
            with gr.Tab("匹配分析"):
                matching_output = gr.Markdown("暂无结果")
            with gr.Tab("STAR 改写"):
                star_output = gr.Markdown("暂无结果")
            with gr.Tab("增补关键词"):
                keyword_output = gr.Markdown("暂无结果")
            with gr.Tab("完整结果"):
                json_output = gr.JSON(label="标准 JSON", open=False)

        load_outputs = [resume_input, jd_input, status]
        analysis_outputs = [
            status,
            score_output,
            matching_output,
            star_output,
            keyword_output,
            json_output,
            summary_output,
        ]
        demo.load(load_callback, outputs=load_outputs)
        reload_button.click(load_callback, outputs=load_outputs)
        save_button.click(
            save_callback,
            inputs=[resume_input, jd_input],
            outputs=status,
        )
        analyze_button.click(
            analyze_callback,
            inputs=[resume_input, jd_input],
            outputs=analysis_outputs,
        )

    demo.queue(default_concurrency_limit=1)
    return demo


def launch_web() -> None:
    """Launch the page on a loopback-only address."""

    build_demo().launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        css=_PAGE_CSS,
    )


def main() -> None:
    launch_web()


if __name__ == "__main__":
    main()
