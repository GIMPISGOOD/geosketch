"""AI 服务：本地 GGUF 模型 + 远程 OpenAI 兼容 API 双引擎。

设计原则
────────
• 完全懒加载——仅在脚本编辑器打开且 ai.enabled=True 时才加载模型。
• 所有推理在后台 QThread 中执行，通过信号回传主线程。
• 任何异常均被捕获，绝不向上层抛出。
• 模型文件使用项目已有 models/ 目录，不新建文件夹。
"""
from __future__ import annotations

import gc
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal


# ═══════════════════════════════════════════════════════
#  后台推理线程
# ═══════════════════════════════════════════════════════

class _InferWorker(QThread):
    """在后台线程中执行一次推理，完成后通过信号回传。"""
    done   = Signal(str, str)   # (结果文本, 模式 "complete"|"generate")
    failed = Signal(str)        # 错误信息

    def __init__(self, service: "AIService", prompt: str, mode: str,
                 parent=None):
        super().__init__(parent)
        self._svc    = service
        self._prompt = prompt
        self._mode   = mode

    def run(self):
        try:
            provider = self._svc._settings.get("ai.provider", "local")
            if provider == "remote":
                result = self._svc._remote_infer(self._prompt)
            else:
                result = self._svc._local_infer(self._prompt)
            self.done.emit(result or "", self._mode)
        except Exception as e:
            self.failed.emit(str(e))


# ═══════════════════════════════════════════════════════
#  AI 服务主类
# ═══════════════════════════════════════════════════════

class AIService(QObject):
    """由 ScriptEditorDialog 按需创建，生命周期与编辑器绑定。"""

    loaded       = Signal()
    load_failed  = Signal(str)
    result_ready = Signal(str, str)   # (文本, "complete"|"generate")
    error        = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._llm      = None          # llama_cpp.Llama 实例
        self._worker: _InferWorker | None = None

    # ── 配置有效性检测 ──────────────────────────────

    def is_configured(self) -> bool:
        """检查当前配置是否足以执行推理（不加载模型）。"""
        try:
            if not self._settings.get("ai.enabled", False):
                return False
            provider = self._settings.get("ai.provider", "local")
            if provider == "local":
                return self._find_model_file() is not None
            if provider == "remote":
                url = self._settings.get("ai.api_url", "")
                key = self._settings.get("ai.api_key", "")
                return bool(url and key)
        except Exception:
            pass
        return False

    # ── 模型发现 ────────────────────────────────────

    def discover_models(self) -> list[str]:
        """返回模型目录下所有 .gguf 文件名（不加载）。"""
        try:
            d = self._resolve_model_dir()
            if d is None or not d.is_dir():
                return []
            return sorted(f.name for f in d.glob("*.gguf"))
        except Exception:
            return []

    def _resolve_model_dir(self) -> Path | None:
        try:
            raw = self._settings.get("ai.model_dir", "models")
            if not raw:
                return None
            p = Path(raw)
            if not p.is_absolute():
                # 相对于可执行文件 / 脚本所在目录
                base = Path(sys.executable).parent if hasattr(sys, 'frozen') \
                    else Path(__file__).resolve().parent.parent
                p = base / raw
            return p
        except Exception:
            return None
    # ── 后处理：清洗模型输出 ─────────────────────────

    @staticmethod
    def _clean_response(text: str) -> str:
        """去除 Markdown 代码块标记、引导语，提取纯 DSL 代码。"""
        if not text:
            return ""
        lines = text.strip().split("\n")
        cleaned = []
        in_block = False
        for line in lines:
            stripped = line.strip()
            # 跳过 ``` 开头的行
            if stripped.startswith("```"):
                in_block = not in_block
                continue
            # 跳过常见的自然语言引导
            lower = stripped.lower()
            if any(kw in lower for kw in (
                "以下是", "代码如下", "这是", "here is", "here's",
                "geo draw", "draw triangle", "draw a",
            )) and "=" not in stripped and "(" not in stripped:
                continue
            cleaned.append(line)
        # 如果全部被过滤了，返回原文（防御）
        result = "\n".join(cleaned).strip()
        return result if result else text.strip()
    
    def _find_model_file(self) -> Path | None:
        try:
            d = self._resolve_model_dir()
            if d is None or not d.is_dir():
                return None
            name = self._settings.get("ai.model_file", "")
            if name:
                f = d / name
                return f if f.is_file() else None
            files = sorted(d.glob("*.gguf"))
            return files[0] if files else None
        except Exception:
            return None

    # ── 加载 / 卸载 ────────────────────────────────

    def ensure_loaded(self) -> bool:
        """懒加载模型。远程模式无需加载，直接返回 True。"""
        try:
            provider = self._settings.get("ai.provider", "local")
            if provider == "remote":
                self.loaded.emit()
                return True
            if self._llm is not None:
                return True
            try:
                from llama_cpp import Llama
            except ImportError:
                self.load_failed.emit("llama-cpp-python 未安装")
                return False
            mp = self._find_model_file()
            if mp is None:
                self.load_failed.emit("未找到 .gguf 模型文件")
                return False
            ctx = int(self._settings.get("ai.context_tokens", 512))
            self._llm = Llama(model_path=str(mp), n_ctx=ctx, verbose=False)
            self.loaded.emit()
            return True
        except Exception as e:
            self._llm = None
            self.load_failed.emit(f"模型加载失败: {e}")
            return False

    def unload(self):
        """释放本地模型内存。远程模式无操作。"""
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(2000)       # 最多等 2 秒
        self._worker = None
        self._llm = None
        gc.collect()

    # ── 异步推理入口 ────────────────────────────────

    def request(self, prompt: str, mode: str = "complete"):
        """发起后台推理。mode: "complete" | "generate"。"""
        if not self.is_configured():
            self.error.emit("AI 未启用或未配置")
            return
        if self._worker is not None and self._worker.isRunning():
            return                        # 上一次推理未完成，忽略
        self._worker = _InferWorker(self, prompt, mode, self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, text: str, mode: str):
        self.result_ready.emit(text, mode)

    def _on_fail(self, msg: str):
        self.error.emit(msg)

    # ── 本地推理 ────────────────────────────────────

    def _local_infer(self, prompt: str) -> str:
        if self._llm is None:
            if not self.ensure_loaded():
                return ""
        sys_prompt = self._settings.get("ai.system_prompt", "")
        max_tok    = int(self._settings.get("ai.max_tokens", 256))
        temp       = float(self._settings.get("ai.temperature", 0.2))
        try:
            assert self._llm is not None
            resp = self._llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=max_tok,
                temperature=temp,
            )
            raw = resp["choices"][0]["message"]["content"] # type: ignore
            return self._clean_response(raw) # type: ignore
        except Exception:
            return ""

    # ── 远程推理（OpenAI 兼容） ─────────────────────

    def _remote_infer(self, prompt: str) -> str:
        try:
            import requests as req
        except ImportError:
            return ""
        url        = self._settings.get("ai.api_url", "")
        key        = self._settings.get("ai.api_key", "")
        model      = self._settings.get("ai.api_model", "")
        sys_prompt = self._settings.get("ai.system_prompt", "")
        max_tok    = int(self._settings.get("ai.max_tokens", 256))
        temp       = float(self._settings.get("ai.temperature", 0.2))
        timeout_s  = int(self._settings.get("ai.timeout_ms", 5000)) / 1000.0
        if not url:
            return ""
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {key}",
        }
        payload = {
            "model":      model,
            "messages":   [
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens":   max_tok,
            "temperature":  temp,
        }
        try:
            r = req.post(url, json=payload, headers=headers,
                         timeout=max(timeout_s, 1.0))
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            return ""