# MCP Tool: resume_jd_matcher
Function: Compare resume and JD, calculate match score and give optimize suggestions

Params:
resume_text: string
jd_text: string
score_top: int(1~5)

Return:
match_score:int 0-100
match_keywords: list
missing_skills: list
optimize_suggest: list

Error types:
input_too_long: text exceed limit
empty_content: input is empty
sensitive_content: contains forbidden words