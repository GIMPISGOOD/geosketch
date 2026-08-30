"""AI 服务：本地 GGUF + 远程 API 双引擎，应用级单例 + 引用计数。

生命周期
────────
• 应用启动时不加载任何模型。
• ScriptEditorDialog 打开 → acquire() → 引用计数 +1
• ScriptEditorDialog 关闭 → release() → 引用计数 -1
• 引用计数归零 → 延迟 30 秒 → 卸载模型释放内存
• 30 秒内再次打开编辑器 → 取消卸载，复用已加载模型
"""
from __future__ import annotations

import gc
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal


# ═══════════════════════════════════════════════════════
#  后台推理线程
# ═══════════════════════════════════════════════════════

class _InferWorker(QThread):
    done   = Signal(str, str)
    failed = Signal(str)

    def __init__(self, service: "AIService", prompt: str, mode: str,
                 parent=None):
        super().__init__(parent)
        self._svc    = service
        self._prompt = prompt
        self._mode   = mode

    def run(self):
        try:
            assert self._svc._settings is not None
            provider = self._svc._settings.get("ai.provider", "local")
            if provider == "remote":
                result = self._svc._remote_infer(self._prompt)
            else:
                result = self._svc._local_infer(self._prompt, self._mode)
            self.done.emit(result or "", self._mode)
        except Exception as e:
            self.failed.emit(str(e))


# ═══════════════════════════════════════════════════════
#  AI 服务单例
# ═══════════════════════════════════════════════════════

class AIService(QObject):
    loaded       = Signal()
    load_failed  = Signal(str)
    result_ready = Signal(str, str)
    error        = Signal(str)

    _instance: "AIService | None" = None

    @classmethod
    def instance(cls) -> "AIService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = None
        self._llm: dict[str, object] = {}   # {"complete": Llama, "generate": Llama}
        self._ref_count: int = 0
        self._unload_timer: QTimer | None = None
        self._worker: _InferWorker | None = None

    # ── 引用计数 ────────────────────────────────────

    def acquire(self, settings) -> None:
        """编辑器打开时调用。取消待执行的延迟卸载。"""
        self._settings = settings
        self._ref_count += 1
        if self._unload_timer is not None:
            self._unload_timer.stop()
            self._unload_timer = None

    def release(self) -> None:
        """编辑器关闭时调用。引用归零后延迟 30 秒卸载。"""
        self._ref_count = max(0, self._ref_count - 1)
        if self._ref_count == 0 and self._llm:
            self._unload_timer = QTimer(self)
            self._unload_timer.setSingleShot(True)
            self._unload_timer.timeout.connect(self._delayed_unload)
            self._unload_timer.start(30_000)

    def _delayed_unload(self) -> None:
        if self._ref_count == 0:
            self.unload()

    # ── 配置检测 ────────────────────────────────────

    def is_configured(self) -> bool:
        try:
            if self._settings is None:
                return False
            if not self._settings.get("ai.enabled", False):
                return False
            provider = self._settings.get("ai.provider", "local")
            if provider == "local":
                return self._find_model_file("complete") is not None
            if provider == "remote":
                url = self._settings.get("ai.api_url", "")
                key = self._settings.get("ai.api_key", "")
                return bool(url and key)
        except Exception:
            pass
        return False

    # ── 模型发现 ────────────────────────────────────

    def discover_models(self) -> list[str]:
        try:
            d = self._resolve_model_dir()
            if d is None or not d.is_dir():
                return []
            return sorted(f.name for f in d.glob("*.gguf"))
        except Exception:
            return []

    def _resolve_model_dir(self) -> Path | None:
        try:
            if self._settings is None:
                return None
            raw = self._settings.get("ai.model_dir", "models")
            if not raw:
                return None
            p = Path(raw)
            if not p.is_absolute():
                base = Path(__file__).resolve().parent.parent
                p = base / raw
            return p
        except Exception:
            return None

    def _find_model_file(self, mode: str = "complete") -> Path | None:
        """根据 mode 选择模型文件。
        优先级：{mode}_model_file → model_file → 目录第一个 .gguf
        """
        try:
            d = self._resolve_model_dir()
            if d is None or not d.is_dir():
                return None
            # 1. 用途专属模型
            key = f"ai.{mode}_model_file"
            name = self._settings.get(key, "") # type: ignore
            if name:
                f = d / name
                if f.is_file():
                    return f
            # 2. 通用模型
            assert self._settings is not None
            name = self._settings.get("ai.model_file", "")
            if name:
                f = d / name
                if f.is_file():
                    return f
            # 3. 自动选第一个
            files = sorted(d.glob("*.gguf"))
            return files[0] if files else None
        except Exception:
            return None

    # ── 加载 / 卸载 ────────────────────────────────

    def ensure_loaded(self, mode: str = "complete") -> bool:
        """按需加载指定用途的模型。"""
        try:
            if self._settings is None:
                return False
            provider = self._settings.get("ai.provider", "local")
            if provider == "remote":
                self.loaded.emit()
                return True
            if mode in self._llm and self._llm[mode] is not None:
                return True
            try:
                from llama_cpp import Llama
            except ImportError:
                self.load_failed.emit("llama-cpp-python 未安装")
                return False
            mp = self._find_model_file(mode)
            if mp is None:
                self.load_failed.emit("未找到 .gguf 模型文件")
                return False
            # 如果两个用途指向同一文件，复用同一实例
            other = "generate" if mode == "complete" else "complete"
            if other in self._llm and self._llm[other] is not None:
                other_path = self._find_model_file(other)
                if other_path is not None and other_path == mp:
                    self._llm[mode] = self._llm[other]
                    self.loaded.emit()
                    return True
            ctx = int(self._settings.get("ai.context_tokens", 2048))
            ctx = max(ctx, 2048)
            self._llm[mode] = Llama(
                model_path=str(mp), n_ctx=ctx, verbose=False)
            self.loaded.emit()
            return True
        except Exception as e:
            self._llm.pop(mode, None)
            self.load_failed.emit(f"模型加载失败: {e}")
            return False

    def unload(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(2000)
        self._worker = None
        self._llm.clear()
        gc.collect()

    # ── 异步推理 ────────────────────────────────────

    def request(self, prompt: str, mode: str = "complete") -> None:
        if not self.is_configured():
            self.error.emit("AI 未启用或未配置")
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker = _InferWorker(self, prompt, mode, self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, text: str, mode: str):
        self.result_ready.emit(text, mode)

    def _on_fail(self, msg: str):
        self.error.emit(msg)

    # ── 本地推理 ────────────────────────────────────

    def _local_infer(self, prompt: str, mode: str = "complete") -> str:
        if mode not in self._llm or self._llm[mode] is None:
            if not self.ensure_loaded(mode):
                return ""
        llm = self._llm.get(mode)
        if llm is None:
            return ""
        sys_prompt = self._settings.get("ai.system_prompt", "") # type: ignore
        max_tok    = int(self._settings.get("ai.max_tokens", 512)) # type: ignore
        assert self._settings is not None
        temp       = float(self._settings.get("ai.temperature", 0.2))
        try:
            resp = llm.create_chat_completion( # type: ignore
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=max_tok,
                temperature=temp,
            )
            raw = resp["choices"][0]["message"]["content"]
            return self._clean_response(raw)
        except Exception:
            return ""

    # ── 远程推理 ────────────────────────────────────

    def _remote_infer(self, prompt: str) -> str:
        try:
            import requests as req
        except ImportError:
            return ""
        if self._settings is None:
            return ""
        url        = self._settings.get("ai.api_url", "")
        key        = self._settings.get("ai.api_key", "")
        model      = self._settings.get("ai.api_model", "")
        sys_prompt = self._settings.get("ai.system_prompt", "")
        max_tok    = int(self._settings.get("ai.max_tokens", 512))
        temp       = float(self._settings.get("ai.temperature", 0.2))
        timeout_s  = int(self._settings.get("ai.timeout_ms", 15000)) / 1000.0
        if not url:
            return ""
        try:
            r = req.post(
                url,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user",   "content": prompt},
                    ],
                    "max_tokens": max_tok,
                    "temperature": temp,
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                },
                timeout=max(timeout_s, 1.0),
            )
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
            return self._clean_response(raw)
        except Exception:
            return ""

    # ── 后处理 ──────────────────────────────────────

    @staticmethod
    def _clean_response(text: str) -> str:
        if not text:
            return ""
        lines = text.strip().split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                continue
            lower = stripped.lower()
            if any(kw in lower for kw in (
                "以下是", "代码如下", "这是", "here is", "here's",
            )) and "=" not in stripped and "(" not in stripped:
                continue
            cleaned.append(line)
        result = "\n".join(cleaned).strip()
        return result if result else text.strip()