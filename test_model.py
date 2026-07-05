# -*- coding: utf-8 -*-
from src.model_client import ModelClient

client = ModelClient()

prompt = """请根据以下简历和岗位JD，输出匹配分析结果。只输出JSON格式，不要其他文字。

简历：熟悉Python、Django、MySQL，有3年开发经验。
JD：招聘Python后端开发，要求Django、MySQL、Redis、Linux。

输出JSON格式：
{"match_score": 85, "match_keywords": ["Python", "Django", "MySQL"], "missing_skills": ["Redis", "Linux"], "suggest": ["学习Redis缓存", "学习Linux基础操作"]}"""

try:
    resp = client.chat(prompt, temperature=0.5)
    content = resp.choices[0].message.content
    print("=== 模型原始输出 ===")
    print(repr(content))
    print("=== 输出长度 ===")
    print(len(content))
except Exception as e:
    print("错误:", e)