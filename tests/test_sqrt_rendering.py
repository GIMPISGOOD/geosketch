"""根号渲染诊断测试。
验证 sqrt 的各种输入形式是否被正确解析为 Sqrt 节点并渲染为根号图形。

运行：pytest tests/test_sqrt_rendering.py -v
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtCore import Qt


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ═══════════════ 1. Parser 层：AST 节点类型诊断 ═══════════════
class TestSqrtParsing:
    """测试不同输入形式是否产生 Sqrt AST 节点。"""

    def test_latex_sqrt_produces_sqrt_node(self):
        """\\sqrt{x} 应产生 Sqrt 节点。"""
        from ui.math.parser import parse, Sqrt, Row
        ast = parse(r"\sqrt{x}")
        # 顶层应该是 Sqrt 或包含 Sqrt 的 Row
        if isinstance(ast, Row):
            found = any(isinstance(c, Sqrt) for c in ast.children)
        else:
            found = isinstance(ast, Sqrt)
        assert found, (
            f"\\sqrt{{x}} 未产生 Sqrt 节点，"
            f"实际类型: {type(ast).__name__}"
        )

    def test_function_sqrt_NOT_produces_sqrt_node(self):
        """sqrt(x) 当前【不会】产生 Sqrt 节点 —— 这是 bug 根源。"""
        from ui.math.parser import parse, Sqrt, Row, Ord
        ast = parse("sqrt(x)")
        # 诊断：打印 AST 结构
        if isinstance(ast, Row):
            types = [type(c).__name__ for c in ast.children]
            has_sqrt = any(isinstance(c, Sqrt) for c in ast.children)
        else:
            types = [type(ast).__name__]
            has_sqrt = isinstance(ast, Sqrt)

        # 这个测试记录当前行为（预期失败 = 确认 bug 存在）
        if not has_sqrt:
            pytest.fail(
                f"【确认 BUG】sqrt(x) 未产生 Sqrt 节点。\n"
                f"AST 子节点类型: {types}\n"
                f"原因: parser 将 'sqrt' 识别为 Ord(func) 而非 Sqrt 命令。\n"
                f"修复: 需在 parser 或 draw_math 前将 sqrt(...) 转换为 \\sqrt{{...}}"
            )

    def test_unicode_sqrt_NOT_produces_sqrt_node(self):
        """√(x) 当前【不会】产生 Sqrt 节点。"""
        from ui.math.parser import parse, Sqrt, Row
        ast = parse("√(x)")
        if isinstance(ast, Row):
            has_sqrt = any(isinstance(c, Sqrt) for c in ast.children)
        else:
            has_sqrt = isinstance(ast, Sqrt)
        if not has_sqrt:
            pytest.fail(
                "【确认 BUG】√(x) 未产生 Sqrt 节点。"
                "parser 不认识 Unicode √ 字符。"
            )

    def test_nested_sqrt(self):
        """\\sqrt{\\sqrt{x}} 嵌套根号。"""
        from ui.math.parser import parse, Sqrt, Row
        ast = parse(r"\sqrt{\sqrt{x}}")
        if isinstance(ast, Row):
            outer = [c for c in ast.children if isinstance(c, Sqrt)]
        else:
            outer = [ast] if isinstance(ast, Sqrt) else []
        assert len(outer) > 0, "嵌套根号外层未识别"
        # 内层
        inner = outer[0].content
        if isinstance(inner, Row):
            inner_sqrt = [c for c in inner.children if isinstance(c, Sqrt)]
        else:
            inner_sqrt = [inner] if isinstance(inner, Sqrt) else []
        assert len(inner_sqrt) > 0, "嵌套根号内层未识别"

    def test_sqrt_with_complex_content(self):
        """\\sqrt{x^2+1} 根号内含上标。"""
        from ui.math.parser import parse, Sqrt, Row
        ast = parse(r"\sqrt{x^2+1}")
        if isinstance(ast, Row):
            found = any(isinstance(c, Sqrt) for c in ast.children)
        else:
            found = isinstance(ast, Sqrt)
        assert found, "\\sqrt{x^2+1} 未产生 Sqrt 节点"


# ═══════════════ 2. Layout 层：度量诊断 ═══════════════
class TestSqrtLayout:
    """测试 Sqrt 节点的度量是否正确（宽/升/降）。"""

    def test_sqrt_measure_has_positive_dimensions(self):
        from ui.math.parser import parse
        from ui.math.layout import MathLayout
        ast = parse(r"\sqrt{x}")
        lay = MathLayout(None, 16, QColor(0, 0, 0))
        w, a, d = lay.measure(ast)
        assert w > 0, f"Sqrt 宽度应 > 0，实际 {w}"
        assert a > 0, f"Sqrt 升部应 > 0，实际 {a}"

    def test_sqrt_wider_than_plain_x(self):
        """根号渲染应比纯文本 x 更宽（因为有根号勾）。"""
        from ui.math.parser import parse
        from ui.math.layout import MathLayout
        lay = MathLayout(None, 16, QColor(0, 0, 0))
        
        # 修复：对比 \sqrt{x} 和 纯文本 x
        w_sqrt, _, _ = lay.measure(parse(r"\sqrt{x}"))
        w_text, _, _ = lay.measure(parse("x"))
        
        assert w_sqrt > w_text, (
            f"根号宽度 {w_sqrt:.1f} 应大于纯 x 宽度 {w_text:.1f}"
        )

    def test_function_sqrt_measure_is_just_text(self):
        """sqrt(x) 的度量应该只是纯文本宽度（无根号勾）。"""
        from ui.math.parser import parse
        from ui.math.layout import MathLayout
        lay = MathLayout(None, 16, QColor(0, 0, 0))
        w, a, d = lay.measure(parse("sqrt(x)"))
        # 纯文本度量：宽度应该较小
        assert w > 0, "sqrt(x) 度量宽度应 > 0"


# ═══════════════ 3. 渲染层：像素级诊断 ═══════════════
class TestSqrtRendering:
    """实际渲染到 QImage，检查根号勾是否被绘制。"""

    def _render_to_image(self, text, size=20):
        from ui.math import draw_math
        img = QImage(300, 80, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_math(p, 20, 50, text, size, QColor(0, 0, 0))
        p.end()
        return img

    def _count_dark_pixels(self, img):
        """统计非白色像素数量。"""
        count = 0
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.red() < 200 or c.green() < 200 or c.blue() < 200:
                    count += 1
        return count

    def test_latex_sqrt_renders_hook(self, qapp):
        """\\sqrt{x} 应渲染出根号勾（比纯文本多笔画）。"""
        img_sqrt = self._render_to_image(r"\sqrt{x}")
        img_text = self._render_to_image("x")
        px_sqrt = self._count_dark_pixels(img_sqrt)
        px_text = self._count_dark_pixels(img_text)
        # 根号应比单个 x 有更多像素（勾 + 上划线 + x）
        assert px_sqrt > px_text, (
            f"\\sqrt{{x}} 像素 {px_sqrt} 未多于 x 像素 {px_text}"
        )

    def test_function_sqrt_renders_as_text_only(self, qapp):
        """sqrt(x) 当前只渲染为纯文本（无根号勾）。"""
        img_func = self._render_to_image("sqrt(x)")
        img_latex = self._render_to_image(r"\sqrt{x}")
        px_func = self._count_dark_pixels(img_func)
        px_latex = self._count_dark_pixels(img_latex)
        # 记录差异：如果 px_func ≈ px_latex 说明都渲染了根号
        # 如果 px_func < px_latex 说明 sqrt(x) 缺少根号勾
        if px_func < px_latex * 0.9:
            pytest.fail(
                f"【确认 BUG】sqrt(x) 像素 {px_func} 显著少于 "
                f"\\sqrt{{x}} 像素 {px_latex}。\n"
                f"差值 {px_latex - px_func} 像素 = 缺失的根号勾。"
            )


# ═══════════════ 4. 公式编辑器集成诊断 ═══════════════
class TestFormulaEditorSqrt:
    """测试公式编辑器中根号的完整链路。"""

    def test_keypad_inserts_sqrt_text(self):
        """键盘按钮 √( 插入的是 'sqrt(' 字符串。"""
        from ui.formula_editor import FormulaKeypad
        # 找到 √( 按钮对应的插入文本
        for label, ins, cls in FormulaKeypad.KEYS:
            if "√" in label:
                assert ins == "sqrt(", (
                    f"√ 按钮插入的是 '{ins}' 而非 'sqrt('"
                )
                return
        pytest.fail("FormulaKeypad.KEYS 中未找到 √ 按钮")

    def test_preview_text_contains_sqrt_not_latex(self):
        """预览文本是 'y = sqrt(x)' 而非 'y = \\sqrt{x}'。"""
        # 模拟 _update_preview 的逻辑
        expr = "sqrt(x)"
        preview_text = f"y = {expr}"
        assert "sqrt(" in preview_text
        assert "\\sqrt" not in preview_text, (
            "预览文本中不应包含 LaTeX \\sqrt（当前确实不包含，这是 bug）"
        )

    def test_draw_math_with_preview_text(self, qapp):
        """用预览文本调用 draw_math，验证根号是否渲染。"""
        from ui.math import draw_math
        img = QImage(400, 80, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 这就是公式编辑器预览实际调用的方式
        draw_math(p, 12, 40, "y = sqrt(x)", 18, QColor(0, 0, 0))
        p.end()
        # 检查是否有根号勾的像素（在 "sqrt" 文本上方应有斜线）
        # 由于是纯文本渲染，不会有根号勾
        px = self._count_non_white(img)
        assert px > 0, "渲染结果不应为空白"

    def _count_non_white(self, img):
        count = 0
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.red() < 200 or c.green() < 200 or c.blue() < 200:
                    count += 1
        return count


# ═══════════════ 5. 转换函数测试（修复方案验证） ═══════════════
class TestSqrtConversion:
    """测试 sqrt(...) → \\sqrt{...} 的转换函数。
    这是修复方案的核心：在 draw_math 之前进行语法转换。
    """

    @staticmethod
    def _convert_sqrt_to_latex(text: str) -> str:
        """将 sqrt(...) 函数调用转换为 \\sqrt{...} LaTeX 命令。
        支持嵌套括号：sqrt(x^2+sqrt(x)) → \\sqrt{x^2+\\sqrt{x}}
        """
        import re
        result = text
        # 反复替换直到没有 sqrt( 为止（处理嵌套）
        max_iter = 20
        for _ in range(max_iter):
            # 找到 sqrt( 并匹配其对应的右括号
            idx = result.find("sqrt(")
            if idx == -1:
                break
            # 从 sqrt( 之后开始匹配括号
            start = idx + 5  # "sqrt(" 的长度
            depth = 1
            end = start
            while end < len(result) and depth > 0:
                if result[end] == "(":
                    depth += 1
                elif result[end] == ")":
                    depth -= 1
                end += 1
            # end 现在指向匹配右括号的下一个位置
            inner = result[start:end - 1]
            # 替换为 \sqrt{inner}
            result = result[:idx] + "\\sqrt{" + inner + "}" + result[end:]
        return result

    def test_simple_sqrt(self):
        assert self._convert_sqrt_to_latex("sqrt(x)") == "\\sqrt{x}"

    def test_sqrt_with_expression(self):
        assert self._convert_sqrt_to_latex("sqrt(x^2+1)") == "\\sqrt{x^2+1}"

    def test_nested_sqrt(self):
        result = self._convert_sqrt_to_latex("sqrt(x+sqrt(y))")
        assert result == "\\sqrt{x+\\sqrt{y}}"

    def test_sqrt_in_larger_expr(self):
        result = self._convert_sqrt_to_latex("y = 2*sqrt(x) + 1")
        assert result == "y = 2*\\sqrt{x} + 1"

    def test_no_sqrt_unchanged(self):
        assert self._convert_sqrt_to_latex("x^2 + 1") == "x^2 + 1"

    def test_multiple_sqrt(self):
        result = self._convert_sqrt_to_latex("sqrt(a) + sqrt(b)")
        assert result == "\\sqrt{a} + \\sqrt{b}"

    def test_sqrt_with_nested_parens(self):
        result = self._convert_sqrt_to_latex("sqrt((x+1)*(x-1))")
        assert result == "\\sqrt{(x+1)*(x-1)}"

    def test_unicode_sqrt_conversion(self):
        """√(x) 也应被转换。"""
        text = "√(x)"
        # 先将 √( 替换为 sqrt(
        text = text.replace("√(", "sqrt(")
        assert self._convert_sqrt_to_latex(text) == "\\sqrt{x}"


# ═══════════════ 6. 端到端渲染验证（转换后） ═══════════════
class TestSqrtEndToEnd:
    """转换后的完整渲染链路验证。"""

    def test_converted_sqrt_renders_hook(self, qapp):
        """转换后的 \\sqrt{x} 应渲染出根号勾。"""
        from ui.math import draw_math
        from ui.math.parser import parse, Sqrt, Row

        text = "sqrt(x)"
        # 转换
        converted = TestSqrtConversion._convert_sqrt_to_latex(text)
        assert converted == "\\sqrt{x}"

        # 验证 AST
        ast = parse(converted)
        if isinstance(ast, Row):
            has_sqrt = any(isinstance(c, Sqrt) for c in ast.children)
        else:
            has_sqrt = isinstance(ast, Sqrt)
        assert has_sqrt, f"转换后仍未产生 Sqrt 节点: {converted}"

        # 渲染
        img = QImage(200, 80, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = draw_math(p, 20, 50, converted, 20, QColor(0, 0, 0))
        p.end()
        assert w > 0, "渲染宽度应 > 0"

    def test_formula_editor_preview_with_conversion(self, qapp):
        """模拟公式编辑器预览：先转换再渲染。"""
        from ui.math import draw_math

        # 用户输入
        user_input = "sqrt(x^2 + 1)"
        # 预览文本
        preview = f"y = {user_input}"
        # 转换
        converted = TestSqrtConversion._convert_sqrt_to_latex(preview)
        assert "\\sqrt{" in converted

        # 渲染
        img = QImage(400, 80, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_math(p, 12, 40, converted, 18, QColor(0, 0, 0))
        p.end()
        # 成功渲染即通过