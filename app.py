# app.py
from flask import Flask, request, jsonify, render_template, send_from_directory
import json
import time
import re
import requests
import tiktoken
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

class CodeAssistant:
    def __init__(self):
        self.api_key = "sk-b37a7b019b094a27ae424507af28ca61"
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-reasoner"
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.max_context = 8192
        self.temp = 0.3
        self.sessions = {}

    def process_query(self, session_id, query):
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        
        try:
            # 构建上下文
            context = self._build_context(session_id, query)
            
            # API请求
            response = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": context,
                    "temperature": self.temp,
                    "max_tokens": 2048
                },
                timeout=30
            )
            
            if response.status_code != 200:
                return {"error": f"API Error: {response.text}"}, 500
                
            reply = response.json()['choices'][0]['message']['content']
            self._update_history(session_id, query, reply)
            
            return {"reply": reply}, 200
            
        except Exception as e:
            return {"error": str(e)}, 500

    def _build_context(self, session_id, query):
        history = self.sessions.get(session_id, [])
        context = [{
            "role": "system",
            "content": "你是一个专业的代码助手，需要生成带有详细注释的代码，使用代码块包裹代码片段"
        }]
        
        current_tokens = self.encoder.encode(query)
        token_count = len(current_tokens)
        
        for msg in reversed(history):
            msg_tokens = self.encoder.encode(msg['content'])
            if token_count + len(msg_tokens) > self.max_context:
                break
            context.insert(1, msg)
            token_count += len(msg_tokens)
            
        context.append({"role": "user", "content": query})
        return context

    def _update_history(self, session_id, query, reply):
        if session_id not in self.sessions:
            self.sessions[session_id] = []
            
        self.sessions[session_id].extend([
            {"role": "user", "content": query},
            {"role": "assistant", "content": reply}
        ])
        
        # 保持最近10轮对话
        if len(self.sessions[session_id]) > 20:
            self.sessions[session_id] = self.sessions[session_id][-20:]

assistant = CodeAssistant()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.json
    session_id = data.get('session_id', 'default')
    response, status = assistant.process_query(session_id, data['query'])
    return jsonify(response), status

@app.route('/export/<format_type>/<session_id>')
def export_report(format_type, session_id):
    history = assistant.sessions.get(session_id, [])
    if not history:
        return "No history found", 404
        
    # 生成报告内容（示例）
    report = {
        'html': _generate_html_report(history),
        'md': _generate_markdown_report(history)
    }.get(format_type, "")
    
    return report, 200, {'Content-Type': 'text/plain'}

def _generate_html_report(history):
    css = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .code-block { background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 10px 0; }
        .user { color: #2c3e50; margin: 15px 0; }
        .assistant { color: #3498db; margin: 15px 0; }
    </style>
    """
    content = "<h1>代码助手报告</h1>"
    for msg in history:
        content += f"""
        <div class="{msg['role']}">
            <h3>{'用户' if msg['role'] == 'user' else '助手'}</h3>
            <div>{_format_content(msg['content'])}</div>
        </div>
        """
    return f"<!DOCTYPE html><html><head>{css}</head><body>{content}</body></html>"

def _generate_markdown_report(history):
    content = "# 代码助手报告\n\n"
    for msg in history:
        content += f"## {'用户' if msg['role'] == 'user' else '助手'}\n{msg['content']}\n\n"
    return content

def _format_content(text):
    # 简单代码块格式化
    return re.sub(
        r'```(\w+)?\n(.*?)```',
        lambda m: f'<div class="code-block">{m.group(2)}</div>',
        text,
        flags=re.DOTALL
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
