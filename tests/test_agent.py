from src.agent import ResumeAgent
from src.guardrails import check_file_path, check_sensitive

agent = ResumeAgent()

def test_normal_task():
    resume = "Python developer, familiar with MySQL"
    jd = "Backend engineer, require Python and MySQL skills"
    res = agent.run(resume, jd)
    assert "match_info" in res

def test_sensitive_intercept():
    resume = "test resume"
    jd = "illegal part-time job"
    res = agent.run(resume, jd)
    assert "error" in res

def test_path_guard():
    safe, msg = check_file_path("C:/Windows/system32")
    assert safe is False

def test_empty_text():
    res = agent.run("", "backend developer position")
    assert "match_info" in res

def test_long_text():
    long_str = "content"*5000
    res = agent.run(long_str, "backend developer")
    assert "match_info" in res