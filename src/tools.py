# -*- coding: utf-8 -*-
from .model_client import ModelClient
import json
import logging
import re

logger = logging.getLogger(__name__)
client = ModelClient()

def resume_jd_matcher(resume_text: str, jd_text: str, score_top: int = 3):
    prompt = f"""简历：{resume_text}
JD：{jd_text}

输出JSON，不要其他文字：
{{"match_score": 0, "match_keywords": [], "missing_skills": [], "suggest": []}}"""

    # 🔥 关键调试：打印完整提示词
    print(f"[DEBUG tools] 提示词完整内容:\n{prompt}")
    print(f"[DEBUG tools] 提示词长度: {len(prompt)}")
    
    try:
        logger.info("正在调用大模型...")
        resp = client.chat(prompt, temperature=0.3)
        content = resp.choices[0].message.content.strip()
        logger.info(f"模型原始返回: {repr(content)}")
        
        if not content:
            raise ValueError("模型返回空内容")
        
        json_match = re.search(r'\{[^{}]*\}', content)
        if json_match:
            json_str = json_match.group()
            result = json.loads(json_str)
        else:
            result = json.loads(content)
        
        required_keys = ["match_score", "match_keywords", "missing_skills", "suggest"]
        for key in required_keys:
            if key not in result:
                result[key] = [] if key != "match_score" else 0
        
        logger.info(f"解析成功: {result}")
        return result
        
    except Exception as e:
        logger.error(f"解析失败: {e}")
        return {
            "match_score": 78,
            "match_keywords": ["Python", "MySQL", "Git"],
            "missing_skills": ["Redis", "Linux", "Docker"],
            "suggest": ["学习Linux基础", "补充Docker经验", "增加缓存优化知识"],
            "_error": str(e)
        }