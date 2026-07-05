import os
import dotenv
from openai import OpenAI

dotenv.load_dotenv(".env.example")

class ModelClient:
    def __init__(self):
        self.client = OpenAI(
            base_url=os.getenv("OLLAMA_BASE_URL"),
            api_key=os.getenv("API_KEY")
        )
        self.model = os.getenv("MODEL_NAME")
        print(f"[DEBUG] 初始化模型: {self.model}")

    def test_connect(self):
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=10
            )
            return {
                "status": "success",
                "model": self.model,
                "token_used": resp.usage.total_tokens
            }
        except Exception as e:
            return {"status": "fail", "error": str(e)}

    def chat(self, prompt, temperature=0.0):
        # 🔥 关键调试：打印收到的 prompt
        print(f"[DEBUG ModelClient] 收到 prompt 长度: {len(prompt)}")
        print(f"[DEBUG ModelClient] prompt 前200字符: {repr(prompt[:200])}")
        print(f"[DEBUG ModelClient] prompt 完整内容:\n{prompt}")
        
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=2048
        )
        
        content = resp.choices[0].message.content
        print(f"[DEBUG ModelClient] 模型返回长度: {len(content) if content else 0}")
        print(f"[DEBUG ModelClient] 模型返回内容: {repr(content)}")
        
        return resp