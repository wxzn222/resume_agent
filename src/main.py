import gradio as gr
from src.agent import ResumeAgent
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

agent = ResumeAgent()

def run_analyze(resume, jd):
    """Gradio调用的入口函数，必须返回字符串"""
    try:
        logger.info("收到分析请求")
        result = agent.analyze(resume, jd)
        logger.info(f"返回结果长度: {len(result)}")
        return result
    except Exception as e:
        logger.error(f"run_analyze 异常: {e}")
        return f"分析过程发生错误：{str(e)}"

with gr.Blocks(title="Resume Optimizer") as demo:
    gr.Markdown("# 📄 简历岗位匹配分析工具")
    gr.Markdown("输入简历内容和岗位JD，AI将自动分析匹配度并给出优化建议")
    
    with gr.Row():
        with gr.Column(scale=1):
            resume_input = gr.Textbox(
                label="📝 简历内容", 
                lines=8, 
                placeholder="请粘贴你的简历文本..."
            )
        with gr.Column(scale=1):
            output_result = gr.Textbox(
                label="📊 分析结果", 
                lines=8, 
                interactive=False
            )
    
    jd_input = gr.Textbox(
        label="💼 岗位JD要求", 
        lines=4, 
        placeholder="请粘贴目标岗位的职位描述..."
    )
    
    with gr.Row():
        submit_btn = gr.Button("🚀 开始分析", variant="primary")
        clear_btn = gr.ClearButton([resume_input, jd_input, output_result])
    
    # 正确的绑定方式：click 返回输出
    submit_btn.click(
        fn=run_analyze, 
        inputs=[resume_input, jd_input], 
        outputs=[output_result]
    )

if __name__ == "__main__":
    logger.info("启动Gradio服务: http://127.0.0.1:7860")
    demo.launch(
        server_name="127.0.0.1", 
        server_port=7860,
        share=False
    )