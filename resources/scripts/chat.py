"""
通用本地 LLM 终端聊天框架
特性：流式输出、多模型管理、动态 Prompt、会话持久化、Rich 美化渲染。
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Generator

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.live import Live
from rich.text import Text
from rich.table import Table

# 尝试导入 llama-cpp-python
try:
    from llama_cpp import Llama
except ImportError:
    print("[bold red]错误：[/bold red] 请先安装 llama-cpp-python: pip install llama-cpp-python")
    sys.exit(1)

console = Console()

# ═══════════════════════════════════════════════════════════
# 1. 模型管理器 (Model Manager)
# ═══════════════════════════════════════════════════════════
class ModelManager:
    """负责扫描、加载和管理本地 GGUF 模型。"""
    
    SEARCH_DIRS = [
        Path("./models"),
        Path.home() / ".geosketch" / "models",
    ]

    def __init__(self):
        self.loaded_model = None
        self.current_path = None

    def scan_models(self) -> list[Path]:
        """扫描所有搜索目录下的 .gguf 文件。"""
        found = []
        for d in self.SEARCH_DIRS:
            if d.exists():
                found.extend(sorted(d.glob("*.gguf")))
        return found

    def load_model(self, path: Path, n_ctx: int = 2048) -> Llama:
        """加载指定的 GGUF 模型。"""
        if self.current_path == path and self.loaded_model is not None:
            return self.loaded_model
            
        console.print(f"[dim]正在加载模型: {path.name} (上下文: {n_ctx})...[/dim]")
        start = time.time()
        
        # 核心加载参数（针对 8GB 内存/核显优化）
        self.loaded_model = Llama(
            model_path=str(path),
            n_ctx=n_ctx,
            n_threads=os.cpu_count() or 4,
            n_batch=256,
            verbose=False,
            use_mlock=True,  # 锁定内存，防止 8GB 机器 swap 卡顿
        )
        self.current_path = path
        console.print(f"[bold green]✅ 模型加载完成！[/bold green] [dim](耗时 {time.time()-start:.1f}s)[/dim]")
        return self.loaded_model


# ═══════════════════════════════════════════════════════════
# 2. 会话与上下文管理 (Chat Session)
# ═══════════════════════════════════════════════════════════
class ChatSession:
    """管理对话历史、System Prompt 和上下文截断。"""
    
    def __init__(self, n_ctx: int = 2048):
        self.n_ctx = n_ctx
        self.system_prompt = "你是一个乐于助人的 AI 助手。"
        self.history: list[dict] = []  # 仅包含 user 和 assistant

    def set_system_prompt(self, prompt: str):
        self.system_prompt = prompt

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self._trim_context()

    def _trim_context(self):
        """智能截断：保留 System Prompt，丢弃最早的历史，确保不超 n_ctx。"""
        # 粗略估算：1 token ≈ 4 个字符 (英文) 或 1.5 个汉字
        def estimate_tokens(text: str) -> int:
            return len(text) // 2 
        
        sys_tokens = estimate_tokens(self.system_prompt)
        while self.history:
            total_tokens = sys_tokens + sum(estimate_tokens(m["content"]) for m in self.history)
            if total_tokens < self.n_ctx - 200:  # 预留 200 token 给输出
                break
            self.history.pop(0)  # 丢弃最早的一条消息

    def get_messages(self) -> list[dict]:
        """构建发送给 LLM 的完整消息列表。"""
        msgs = [{"role": "system", "content": self.system_prompt}]
        msgs.extend(self.history)
        return msgs

    def save(self, path: str):
        data = {"system": self.system_prompt, "history": self.history}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        console.print(f"[green]💾 会话已保存至: {path}[/green]")

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.system_prompt = data.get("system", self.system_prompt)
        self.history = data.get("history", [])
        console.print(f"[green]📂 已加载会话: {path} ({len(self.history)} 条记录)[/green]")

    def clear(self):
        self.history = []


# ═══════════════════════════════════════════════════════════
# 3. 预设 Prompt 库 (Prompt Presets)
# ═══════════════════════════════════════════════════════════
PRESETS = {
    "default": "你是一个乐于助人的 AI 助手，请用简洁清晰的中文回答问题。",
    "coder": "你是一个资深的 Python 程序员。请提供高质量、带注释的代码，并解释核心逻辑。",
    "translator": "你是一个专业的中英翻译官。如果输入是中文，翻译成地道的英文；如果是英文，翻译成流畅的中文。不要输出任何额外解释。",
    "math": "你是一个数学专家。请使用 LaTeX 格式（如 $E=mc^2$）输出数学公式，并逐步展示推导过程。",
}


# ═══════════════════════════════════════════════════════════
# 4. 终端 UI 与主循环 (Terminal UI)
# ═══════════════════════════════════════════════════════════
class TerminalChatApp:
    def __init__(self):
        self.model_mgr = ModelManager()
        self.session = ChatSession()
        self.llm = None
        self.running = True

    def _select_model(self):
        """交互式选择模型。"""
        models = self.model_mgr.scan_models()
        if not models:
            console.print("[bold red]❌ 未找到任何 .gguf 模型文件！[/bold red]")
            console.print(f"[dim]请将模型放入以下目录之一：[/dim]")
            for d in self.model_mgr.SEARCH_DIRS:
                console.print(f"  - {d}")
            sys.exit(1)

        table = Table(title="📦 发现以下本地模型", show_lines=True)
        table.add_column("序号", style="cyan", justify="center")
        table.add_column("模型名称", style="magenta")
        table.add_column("大小", style="green")

        for i, m in enumerate(models, 1):
            size_mb = m.stat().st_size / (1024 * 1024)
            table.add_row(str(i), m.name, f"{size_mb:.0f} MB")
        
        console.print(table)
        
        while True:
            choice = Prompt.ask("请选择模型序号", default="1")
            if choice.isdigit() and 1 <= int(choice) <= len(models):
                idx = int(choice) - 1
                self.llm = self.model_mgr.load_model(models[idx])
                break
            console.print("[red]输入无效，请重新输入。[/red]")

    def _stream_generate(self, messages: list[dict]) -> Generator[str, None, None]:
        """流式生成文本。"""
        stream = self.llm.create_chat_completion( # type: ignore
            messages=messages,# type: ignore
            max_tokens=1024,
            temperature=0.7,
            stream=True,
        )
        for chunk in stream:
            delta = chunk["choices"][0]["delta"]# type: ignore
            if "content" in delta:
                yield delta["content"]# type: ignore

    def _render_stream(self, generator: Generator) -> str:
        """使用 Rich Live 渲染流式输出（打字机效果）。"""
        full_text = ""
        # 初始占位符
        with Live("", console=console, refresh_per_second=12, transient=False) as live:
            for chunk in generator:
                full_text += chunk
                # 实时渲染 Markdown
                live.update(Markdown(full_text))
        return full_text

    def _handle_command(self, cmd: str):
        """处理斜杠命令。"""
        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if action in ("/quit", "/exit", "/q"):
            self.running = False
        elif action == "/clear":
            self.session.clear()
            console.print("[yellow]🧹 对话历史已清空。[/yellow]")
        elif action == "/help":
            self._show_help()
        elif action == "/prompts":
            self._list_prompts()
        elif action == "/use":
            if arg in PRESETS:
                self.session.set_system_prompt(PRESETS[arg])
                console.print(f"[green]✅ 已切换 System Prompt 为: [bold]{arg}[/bold][/green]")
            else:
                console.print(f"[red]❌ 未知的预设: {arg}。输入 /prompts 查看列表。[/red]")
        elif action == "/save":
            path = arg or "chat_history.json"
            self.session.save(path)
        elif action == "/load":
            if not arg:
                console.print("[red]用法: /load <文件路径>[/red]")
            else:
                self.session.load(arg)
        else:
            console.print(f"[red]❓ 未知命令: {action}。输入 /help 查看帮助。[/red]")

    def _show_help(self):
        help_text = """
[bold cyan]可用命令：[/bold cyan]
  /help        - 显示此帮助
  /clear       - 清空当前对话历史
  /prompts     - 列出所有预设 System Prompt
  /use <name>  - 切换预设 Prompt (如: /use coder)
  /save [path] - 保存当前对话到 JSON (默认: chat_history.json)
  /load <path> - 从 JSON 加载对话历史
  /quit        - 退出程序

[bold cyan]使用技巧：[/bold cyan]
  - 直接输入文本即可与 AI 对话。
  - 支持多轮上下文，AI 会记住之前的对话。
  - 代码块会自动进行语法高亮。
"""
        console.print(Panel(help_text, title="帮助", border_style="blue"))

    def _list_prompts(self):
        table = Table(title="📝 预设 System Prompt", show_lines=True)
        table.add_column("名称", style="cyan")
        table.add_column("描述", style="white")
        
        descs = {
            "default": "通用助手，简洁清晰",
            "coder": "Python 编程专家，带注释",
            "translator": "中英互译，无额外废话",
            "math": "数学专家，使用 LaTeX 公式",
        }
        for k, v in PRESETS.items():
            table.add_row(k, descs.get(k, v[:30] + "..."))
        console.print(table)

    def run(self):
        console.print(Panel.fit(
            "[bold cyan]🚀 通用本地 LLM 终端[/bold cyan]\n"
            "[dim]输入 /help 查看命令，直接输入文本开始对话。[/dim]",
            border_style="green"
        ))
        
        self._select_model()

        while self.running:
            try:
                # 构建输入提示符
                prompt_text = Text()
                prompt_text.append("You", style="bold green")
                prompt_text.append(" ❯ ", style="dim")
                
                user_input = console.input(prompt_text).strip()
                if not user_input:
                    continue

                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue

                # 记录用户输入
                self.session.add_message("user", user_input)
                
                # AI 回复
                console.print()  # 空行
                ai_label = Text("Assistant", style="bold blue")
                console.print(ai_label)
                
                try:
                    # 流式生成并渲染
                    generator = self._stream_generate(self.session.get_messages())
                    reply = self._render_stream(generator)
                    
                    # 记录 AI 回复
                    self.session.add_message("assistant", reply)
                    console.print("[dim]─" * 50 + "[/dim]")
                    
                except Exception as e:
                    console.print(f"\n[bold red]❌ 推理出错: {e}[/bold red]")

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]再见！ 👋[/dim]")
                break


if __name__ == "__main__":
    app = TerminalChatApp()
    app.run()