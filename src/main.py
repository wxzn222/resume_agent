"""Automatic command-line entry point for the resume optimizer."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import ResumeAgent, format_result_document, write_result


logger = logging.getLogger(__name__)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _error_result(code: str, message: str) -> dict[str, Any]:
    return {
        "error": {"code": code, "message": message},
        "warnings": [],
        "summary": f"分析未执行：{message}。",
    }


def _write_and_print(root: Path, result: dict[str, Any]) -> bool:
    document = format_result_document(result)
    print(document)
    try:
        write_result(root / "result.txt", result)
        return True
    except OSError as exc:
        logger.error("result.txt 写入失败：%s", type(exc).__name__)
        return False


def run_from_files(
    root: Path | None = None,
    agent: ResumeAgent | None = None,
) -> tuple[int, dict[str, Any]]:
    """Read root-level inputs, run all stages, and export the result."""

    base = Path(root).resolve() if root is not None else project_root()
    resume_path = base / "resume.txt"
    jd_path = base / "jd.txt"

    missing = [
        path.name for path in (resume_path, jd_path) if not path.is_file()
    ]
    if missing:
        result = _error_result(
            "INPUT_FILE_MISSING",
            f"缺少输入文件：{'、'.join(missing)}",
        )
        written = _write_and_print(base, result)
        return (2 if written else 3), result

    try:
        resume = resume_path.read_text(encoding="utf-8")
        jd = jd_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        result = _error_result(
            "INPUT_FILE_READ_ERROR",
            f"输入文件读取失败：{type(exc).__name__}",
        )
        written = _write_and_print(base, result)
        return (2 if written else 3), result

    empty = [
        name
        for name, content in (("resume.txt", resume), ("jd.txt", jd))
        if not content.strip()
    ]
    if empty:
        result = _error_result(
            "INPUT_FILE_EMPTY",
            f"输入文件内容为空：{'、'.join(empty)}",
        )
        written = _write_and_print(base, result)
        return (2 if written else 3), result

    runner = agent or ResumeAgent()
    result = runner.run(resume, jd)
    written = _write_and_print(base, result)
    if not written:
        return 3, result
    return (2 if "error" in result else 0), result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    exit_code, _ = run_from_files()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
