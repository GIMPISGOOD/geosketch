"""彩蛋功能测试套件。
测试触发条件、模块存在性、URL 可达性、下载逻辑、源码完整性。
运行方式：pytest tests/test_easter_egg.py -v
"""
import sys
import os
import tempfile
import urllib.request
from unittest.mock import patch, MagicMock
import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ============================================================
# 第一组：触发条件匹配测试
# ============================================================
class TestTriggerCondition:
    """测试触发词 [ACG] 的匹配逻辑"""

    def test_exact_match(self):
        text = "[ACG]"
        assert "[ACG]" in text

    def test_embedded_match(self):
        text = "hello [ACG] world"
        assert "[ACG]" in text

    def test_no_match(self):
        text = "hello world"
        assert "[ACG]" not in text

    def test_case_sensitive(self):
        text = "[acg]"
        assert "[ACG]" not in text

    def test_partial_no_match(self):
        text = "[AC"
        assert "[ACG]" not in text

    def test_new_year_no_match(self):
        """确认 [New Year] 不会触发（当前触发词是 [ACG]）"""
        text = "[New Year]"
        assert "[ACG]" not in text


# ============================================================
# 第二组：模块存在性测试
# ============================================================
class TestModuleExists:
    """测试 ui/easter_eggs.py 是否存在且可导入"""

    def test_file_exists(self):
        path = os.path.join(PROJECT_ROOT, "ui", "easter_eggs.py")
        assert os.path.exists(path), (
            f"★ 文件不存在: {path}\n"
            f"请创建 ui/easter_eggs.py，内容见下方说明。"
        )

    def test_importable(self):
        try:
            from ui.easter_eggs import trigger_new_year_egg
            assert callable(trigger_new_year_egg)
        except ImportError as e:
            pytest.fail(f"★ 无法导入 ui.easter_eggs: {e}")

    def test_function_signature(self):
        try:
            from ui.easter_eggs import trigger_new_year_egg
            import inspect
            sig = inspect.signature(trigger_new_year_egg)
            params = list(sig.parameters.keys())
            assert len(params) >= 1, "trigger_new_year_egg 至少需要一个参数 (canvas)"
        except ImportError:
            pytest.skip("ui/easter_eggs.py 不存在")


# ============================================================
# 第三组：URL 可达性测试
# ============================================================
class TestURLReachable:
    """测试目标 URL 是否可访问"""

    def test_url_returns_data(self):
        url = "https://eo-img.544521.xyz/"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
                assert len(data) > 0, "★ URL 返回了空数据"
                print(f"\n[DEBUG] URL 可访问，返回 {len(data)} bytes")
        except urllib.error.URLError as e:
            pytest.fail(f"★ URL 不可访问: {e}")
        except Exception as e:
            pytest.fail(f"★ 请求异常: {e}")

    def test_download_saves_to_temp(self):
        url = "https://eo-img.544521.xyz/"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()

            fd, temp_path = tempfile.mkstemp(suffix=".png", prefix="res_cache_")
            with os.fdopen(fd, "wb") as f:
                f.write(data)

            assert os.path.exists(temp_path), "临时文件未创建"
            assert os.path.getsize(temp_path) > 0, "临时文件为空"
            print(f"\n[DEBUG] 临时文件: {temp_path}, 大小: {os.path.getsize(temp_path)} bytes")
            os.unlink(temp_path)
        except Exception as e:
            pytest.fail(f"★ 下载保存失败: {e}")


# ============================================================
# 第四组：源码完整性测试（关键！）
# ============================================================
class TestSourceCodeIntegrity:
    """验证 text_tool.py 和 canvas_menu.py 中包含正确的触发代码"""

    def test_text_tool_has_trigger(self):
        path = os.path.join(PROJECT_ROOT, "plugins", "text_tool.py")
        if not os.path.exists(path):
            pytest.skip("plugins/text_tool.py 不存在")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "[ACG]" in content, "★ text_tool.py 中未找到触发词 [ACG]"
        assert "trigger_new_year_egg" in content, "★ text_tool.py 中未找到 trigger_new_year_egg"
        assert "ui.easter_eggs" in content, "★ text_tool.py 中未找到 ui.easter_eggs 导入"

    def test_canvas_menu_has_trigger(self):
        path = os.path.join(PROJECT_ROOT, "ui", "canvas_menu.py")
        if not os.path.exists(path):
            pytest.skip("ui/canvas_menu.py 不存在")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "[ACG]" in content, "★ canvas_menu.py 中未找到触发词 [ACG]"
        assert "trigger_new_year_egg" in content, "★ canvas_menu.py 中未找到 trigger_new_year_egg"

    def test_text_tool_trigger_in_commit(self):
        """确认触发代码在 _commit 方法内部（而不是在类外部）"""
        path = os.path.join(PROJECT_ROOT, "plugins", "text_tool.py")
        if not os.path.exists(path):
            pytest.skip("plugins/text_tool.py 不存在")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # 确认 _commit 方法存在且包含触发逻辑
        assert "_commit" in content, "★ text_tool.py 中未找到 _commit 方法"
        # 确认触发代码在 _commit 之后
        commit_idx = content.find("def _commit")
        trigger_idx = content.find('[ACG]')
        assert commit_idx != -1, "★ 未找到 _commit 方法定义"
        assert trigger_idx != -1, "★ 未找到 [ACG] 触发词"
        assert trigger_idx > commit_idx, "★ [ACG] 触发代码不在 _commit 方法之后"


# ============================================================
# 第五组：集成测试（模拟完整流程）
# ============================================================
class TestIntegration:
    """模拟完整的触发→下载→插入流程"""

    def test_simulated_text_commit(self):
        """模拟 TextTool._commit 的触发逻辑"""
        text = "我的文本 [ACG] 结尾"
        triggered = False
        if "[ACG]" in text:
            triggered = True
        assert triggered

    def test_simulated_canvas_menu_edit(self):
        """模拟 canvas_menu.edit_text_object 的触发逻辑"""
        obj_text = "编辑后的文本 [ACG]"
        triggered = False
        if "[ACG]" in obj_text:
            triggered = True
        assert triggered

    @patch("threading.Thread")
    def test_trigger_starts_thread(self, mock_thread_cls):
        """测试 trigger_new_year_egg 是否启动了后台线程"""
        try:
            from ui.easter_eggs import trigger_new_year_egg
        except ImportError:
            pytest.skip("ui/easter_eggs.py 不存在")

        mock_canvas = MagicMock()
        mock_canvas.doc = MagicMock()

        trigger_new_year_egg(mock_canvas)

        mock_thread_cls.assert_called_once()
        mock_thread_cls.return_value.start.assert_called_once()

    def test_full_download_and_insert_mock(self):
        """模拟完整的下载→插入流程（不实际下载）"""
        try:
            from ui.easter_eggs import trigger_new_year_egg
        except ImportError:
            pytest.skip("ui/easter_eggs.py 不存在")

        mock_canvas = MagicMock()
        mock_canvas.doc = MagicMock()

        # 模拟下载成功
        fake_image_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = fake_image_data
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            # 由于是异步线程，这里只验证函数不抛异常
            trigger_new_year_egg(mock_canvas)


# ============================================================
# 第六组：诊断测试（帮助定位问题）
# ============================================================
class TestDiagnostics:
    """诊断性测试，输出关键信息帮助排查"""

    def test_print_trigger_locations(self):
        """打印所有包含触发词的文件和行号"""
        print("\n" + "=" * 60)
        print("触发词 [ACG] 出现位置：")
        print("=" * 60)
        found = False
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # 跳过隐藏目录和 __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for fname in files:
                if fname.endswith('.py'):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            for lineno, line in enumerate(f, 1):
                                if '[ACG]' in line:
                                    rel = os.path.relpath(fpath, PROJECT_ROOT)
                                    print(f"  {rel}:{lineno}: {line.strip()}")
                                    found = True
                    except Exception:
                        pass
        if not found:
            print("  ★ 未在任何 .py 文件中找到 [ACG]！")
        print("=" * 60)
        assert found, "★ 整个项目中未找到 [ACG] 触发词"

    def test_print_easter_eggs_content(self):
        """打印 ui/easter_eggs.py 的内容（如果存在）"""
        path = os.path.join(PROJECT_ROOT, "ui", "easter_eggs.py")
        if not os.path.exists(path):
            print(f"\n★ ui/easter_eggs.py 不存在！这就是问题所在。")
            print("请创建该文件。")
            pytest.fail("ui/easter_eggs.py 不存在")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"\n{'=' * 60}")
        print(f"ui/easter_eggs.py 内容 ({len(content)} 字符)：")
        print(f"{'=' * 60}")
        print(content)
        print(f"{'=' * 60}")
        assert "trigger_new_year_egg" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])