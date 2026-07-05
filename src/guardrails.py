import os

MAX_TOKEN = 4096
SAFE_DIR = os.path.abspath("./data")
SENSITIVE_WORDS = ["badword"]

def check_file_path(file_path):
    abs_p = os.path.abspath(file_path)
    if not abs_p.startswith(SAFE_DIR):
        return False, "path forbidden"
    return True, "ok"

def check_sensitive(text):
    for word in SENSITIVE_WORDS:
        if word in text:
            return False, "sensitive content"
    return True, "ok"

def limit_text(text):
    if len(text) > MAX_TOKEN * 2:
        return text[:MAX_TOKEN*2], "text too long"
    return text, "ok"