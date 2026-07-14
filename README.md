# Resume Optimizer Agent

## 功能

该程序会自动完成以下串行流程：

1. 将 JD 拆分为硬性门槛、技术技能和软素质。
2. 分别计算硬性条件、技术关键词和项目经历得分。
3. 按 STAR 结构改写项目经历，不虚构简历中不存在的事实。
4. 输出需要增补的技术关键词清单。
5. 将标准 JSON 和中文总结保存到 `result.txt`。

评分由确定性规则完成；本地 Ollama 仅用于自然语言 STAR 改写。模型不可用时，程序仍会完成评分、保守改写和结果导出。

## 环境安装

```text
conda env create -f environment.yml
conda activate resume-agent
pip install openai python-dotenv
pip install "gradio>=6,<7"
```

## 准备输入文件

1. 参考 `resume.example.txt`，将真实简历保存为项目根目录的 `resume.txt`。
2. 参考 `jd.example.txt`，将真实招聘描述保存为项目根目录的 `jd.txt`。

## 自动文件模式

在项目根目录运行：

```text
python src/main.py
```

程序会直接读取两个输入文件并更新 `result.txt`，不需要网页操作。

## 本地网页模式

在项目根目录运行：

```text
python src/web.py
```

然后访问 `http://127.0.0.1:7860`。网页会自动加载 `resume.txt` 和 `jd.txt`，并提供：

- “开始精准分析”：使用页面当前内容分析并更新 `result.txt`，不会覆盖两个输入文件。
- “重新加载文件”：放弃页面中未保存的修改，重新读取磁盘文件。
- “保存到文件”：显式将页面当前内容写回 `resume.txt` 和 `jd.txt`。

网页服务只监听本机地址，不创建公网分享链接。

输入和输出文件均使用 UTF-8 编码。
真实输入和生成结果已由 `.gitignore` 排除，避免误提交个人信息。
