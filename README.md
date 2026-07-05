# Resume Optimizer Agent
## Introduction
AI agent based on Ollama local model, support resume and JD matching, resume optimization and interview questions generation.

## Env setup
conda env create -f environment.yml
conda activate resume-agent
pip install openai python-dotenv pydantic pytest gradio

## Run commands
python src/main.py --check-model
python src/main.py