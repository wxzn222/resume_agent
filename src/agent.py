from src.tools import resume_jd_matcher
import logging

logger = logging.getLogger(__name__)

class ResumeAgent:
    def analyze(self, resume: str, jd: str):
        logger.info(f"开始分析，简历长度: {len(resume)}, JD长度: {len(jd)}")
        
        # 输入校验
        if not resume or not resume.strip():
            return "错误：简历内容不能为空"
        if not jd or not jd.strip():
            return "错误：岗位JD不能为空"
        
        match_res = resume_jd_matcher(resume, jd, score_top=3)
        logger.info(f"匹配结果: {match_res}")
        
        # 防御性取值
        try:
            result = f"""匹配得分：{match_res.get('match_score', 'N/A')}
匹配技能：{', '.join(match_res.get('match_keywords', []))}
缺失技能：{', '.join(match_res.get('missing_skills', []))}
优化建议：{', '.join(match_res.get('suggest', []))}"""
            
            # 如果有错误标记，追加显示
            if "_error" in match_res:
                result += f"\n\n⚠️ 提示：模型解析异常，显示为默认数据（错误: {match_res['_error']}）"
            
            return result
        except Exception as e:
            logger.error(f"结果组装失败: {e}")
            return f"处理结果时出错：{str(e)}"