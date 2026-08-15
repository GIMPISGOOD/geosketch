"""宏 → 脚本转换引擎。
架构：注册表模式，每种对象类型注册独立的转换函数。
扩展：新增对象类型只需 @register_converter("TypeName") 即可。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

# ═══════════════════════════════════════════════════════════
#  对象类型 → 脚本函数名映射（用于生成有意义的变量名前缀）
# ═══════════════════════════════════════════════════════════
TYPE_PREFIX: Dict[str, str] = {
    # 点
    "FreePoint": "P",
    "PointOnObject": "P",
    "IntersectPoint": "X",
    "DivisionPoint": "D",
    "PolygonVertex": "V",
    "TransformPoint": "TP",
    "IterPoint": "IP",
    "CircleAxisPoint": "AP",
    "ExprPoint": "P",
    "Incenter": "I",
    "Centroid": "G",
    # 线
    "Segment": "S",
    "Line": "L",
    "Ray": "R",
    "DirectedLine": "DL",
    "PerpLine": "PL",
    "ParallelLine": "ParL",
    "AngleBisector": "AB",
    "AngleDivLine": "ADL",
    "PerpBisector": "PB",
    "ExprSegment": "S",
    # 圆 / 曲线
    "Circle": "C",
    "ExprCircle": "C",
    "ThreePointCircle": "C",
    "InvertedCircle": "IC",
    "Ellipse": "E",
    "CubicBezier": "Bez",
    "FunctionCurve": "f",
    # 面
    "RegularPolygon": "Poly",
    "ChainFill": "Fill",
    # 度量
    "AngleMeasure": "Ang",
    "RatioMeasure": "Rat",
    "Measure": "M",
    "RegionMeasure": "RM",
    "ExprAngle": "Ang",
    # 变换
    "TransformDriver": "Drv",
    # 媒体
    "TextObject": "T",
    "ScriptButtonObject": "Btn",
    "TableObject": "Tbl",
    "PieChartObject": "Pie",
    "BarChartObject": "Bar",
    "ImageObject": "Img",
    "InkStroke": "Ink",
    "InkEraser": "Eraser",
}

# ═══════════════════════════════════════════════════════════
#  转换器注册表
# ═══════════════════════════════════════════════════════════
ConvertFn = Callable[[Dict[str, str], dict, "MacroToScriptConverter"], str]
CONVERTERS: Dict[str, ConvertFn] = {}


def register_converter(type_name: str):
    """装饰器：为指定对象类型注册转换函数。"""
    def deco(fn: ConvertFn):
        CONVERTERS[type_name] = fn
        return fn
    return deco


# ═══════════════════════════════════════════════════════════
#  主转换器
# ═══════════════════════════════════════════════════════════
class MacroToScriptConverter:
    """将宏命令序列转换为可执行的脚本代码。

    用法：
        converter = MacroToScriptConverter()
        script = converter.convert(macro_dict)
    """

    def __init__(self, *, keep: bool = True, comment_header: bool = True):
        """
        参数：
            keep: 是否在脚本头部添加 __keep = true（默认 True）
            comment_header: 是否添加注释头
        """
        self.keep = keep
        self.comment_header = comment_header
        self.alias_to_var: Dict[str, str] = {}
        self._counters: Dict[str, int] = {}

    # ─────────────── 对外入口 ───────────────
    def convert(self, macro: dict) -> str:
        """将宏字典转换为脚本字符串。

        参数：
            macro: {"name": "...", "commands": [...]}
        返回：
            脚本代码字符串
        """
        self.alias_to_var.clear()
        self._counters.clear()

        lines: List[str] = []

        # 1. 注释头
        if self.comment_header:
            name = macro.get("name", "未命名宏")
            cmd_count = len(macro.get("commands", []))
            lines.append(f"# ===== 由宏「{name}」自动生成 =====")
            lines.append(f"# 原始命令数：{cmd_count}")
            lines.append("")

        # 2. __keep
        if self.keep:
            lines.append("__keep = true")
            lines.append("")

        # 3. 逐条转换命令
        commands = macro.get("commands", [])
        for cmd in commands:
            converted = self._convert_command(cmd)
            if converted:
                lines.append(converted)

        return "\n".join(lines)

    # ─────────────── 命令分发 ───────────────
    def _convert_command(self, cmd: dict) -> str:
        cmd_type = cmd.get("type", "")
        if cmd_type == "add":
            return self._convert_add(cmd)
        elif cmd_type == "move":
            return self._convert_move(cmd)
        elif cmd_type == "delete":
            return self._convert_delete(cmd)
        elif cmd_type == "set_var":
            return self._convert_set_var(cmd)
        elif cmd_type == "clear":
            return "delete all"
        return f"# 未知命令类型：{cmd_type}"

    # ─────────────── add ───────────────
    def _convert_add(self, cmd: dict) -> str:
        type_name = cmd.get("class", "")
        alias = cmd.get("alias", "")

        # 分配变量名
        var = self._make_var(alias, type_name)
        self.alias_to_var[alias] = var

        # 查找转换器
        converter_fn = CONVERTERS.get(type_name)
        if converter_fn is None:
            return f"# ⚠ 暂不支持的对象类型：{type_name}（变量 {var}）"

        try:
            return converter_fn(self.alias_to_var, cmd, self)
        except Exception as e:
            return f"# ⚠ 转换 {type_name} 时出错：{e}"

    # ─────────────── move ───────────────
    def _convert_move(self, cmd: dict) -> str:
        alias = cmd.get("alias", "")
        var = self.alias_to_var.get(alias, alias)
        params = cmd.get("params", {})

        # 尝试提取坐标信息
        if "x" in params and "y" in params:
            x = self._fmt_num(params["x"])
            y = self._fmt_num(params["y"])
            return f"# 移动 {var} 到 ({x}, {y})（脚本暂不支持属性赋值，需手动调整）"

        # 其他参数
        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
        return f"# 修改 {var}：{param_str}（需手动调整）"

    # ─────────────── delete ───────────────
    def _convert_delete(self, cmd: dict) -> str:
        alias = cmd.get("alias", "")
        var = self.alias_to_var.get(alias, alias)
        return f"delete {var}"

    # ─────────────── set_var ───────────────
    def _convert_set_var(self, cmd: dict) -> str:
        name = cmd.get("name", "x")
        value = cmd.get("value", 0)
        return f"global {name} = {self._fmt_num(value)}"

    # ─────────────── 变量命名 ───────────────
    def _make_var(self, alias: str, type_name: str) -> str:
        """根据对象类型生成有意义的变量名。"""
        prefix = TYPE_PREFIX.get(type_name, "Obj")
        count = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = count
        return f"{prefix}{count}"

    @staticmethod
    def _fmt_num(v: Any) -> str:
        """格式化数字：整数不带小数点，浮点数保留合理精度。"""
        if isinstance(v, float):
            if abs(v - round(v)) < 1e-9:
                return str(int(round(v)))
            return f"{v:.6g}"
        return str(v)

    def resolve_parent(self, parent_alias: str) -> str:
        """将父对象别名解析为脚本变量名。"""
        return self.alias_to_var.get(parent_alias, f"/* {parent_alias} */")


# ═══════════════════════════════════════════════════════════
#  各对象类型的转换函数（注册表）
# ═══════════════════════════════════════════════════════════

# ───────── 点 ─────────
@register_converter("FreePoint")
def _conv_free_point(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    params = cmd.get("params", {})
    x = conv._fmt_num(params.get("x", 0))
    y = conv._fmt_num(params.get("y", 0))
    var = am[cmd["alias"]]
    return f"{var} = point({x}, {y})"


@register_converter("DivisionPoint")
def _conv_division_point(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    params = cmd.get("params", {})
    t = params.get("t", 0.5)
    var = am[cmd["alias"]]
    if len(parents) < 2:
        return f"# ⚠ DivisionPoint 缺少父对象"
    a = conv.resolve_parent(parents[0])
    b = conv.resolve_parent(parents[1])
    if abs(t - 0.5) < 1e-9:
        return f"{var} = midpoint({a}, {b})"
    return f"{var} = division_point({a}, {b}, {conv._fmt_num(t)})"


@register_converter("IntersectPoint")
def _conv_intersect_point(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    params = cmd.get("params", {})
    branch = params.get("branch", 0)
    var = am[cmd["alias"]]
    if len(parents) < 2:
        return f"# ⚠ IntersectPoint 缺少父对象"
    a = conv.resolve_parent(parents[0])
    b = conv.resolve_parent(parents[1])
    return f"{var} = intersect({a}, {b}, {branch})"


@register_converter("PointOnObject")
def _conv_point_on_object(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    params = cmd.get("params", {})
    t = params.get("t", 0.5)
    var = am[cmd["alias"]]
    if len(parents) < 1:
        return f"# ⚠ PointOnObject 缺少宿主对象"
    host = conv.resolve_parent(parents[0])
    return f"# ⚠ PointOnObject（吸附点）暂不支持直接转换，宿主：{host}，t={conv._fmt_num(t)}"


@register_converter("PolygonVertex")
def _conv_polygon_vertex(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    params = cmd.get("params", {})
    k = params.get("k", 0)
    var = am[cmd["alias"]]
    if len(parents) < 1:
        return f"# ⚠ PolygonVertex 缺少父对象"
    poly = conv.resolve_parent(parents[0])
    return f"# ⚠ PolygonVertex（多边形顶点）暂不支持，所属：{poly}，索引：{k}"


# ───────── 线 ─────────
@register_converter("Segment")
def _conv_segment(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    var = am[cmd["alias"]]
    if len(parents) < 2:
        return f"# ⚠ Segment 缺少父对象"
    a = conv.resolve_parent(parents[0])
    b = conv.resolve_parent(parents[1])
    return f"{var} = segment({a}, {b})"


@register_converter("Line")
def _conv_line(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    var = am[cmd["alias"]]
    if len(parents) < 2:
        return f"# ⚠ Line 缺少父对象"
    a = conv.resolve_parent(parents[0])
    b = conv.resolve_parent(parents[1])
    return f"{var} = line({a}, {b})"


@register_converter("Ray")
def _conv_ray(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    var = am[cmd["alias"]]
    if len(parents) < 2:
        return f"# ⚠ Ray 缺少父对象"
    a = conv.resolve_parent(parents[0])
    b = conv.resolve_parent(parents[1])
    return f"{var} = ray({a}, {b})"


@register_converter("DirectedLine")
def _conv_directed_line(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ DirectedLine（方向直线）暂不支持转换（变量 {var}）"


@register_converter("PerpLine")
def _conv_perp_line(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ PerpLine（垂线）暂不支持转换（变量 {var}）"


@register_converter("ParallelLine")
def _conv_parallel_line(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ ParallelLine（平行线）暂不支持转换（变量 {var}）"


@register_converter("AngleBisector")
def _conv_angle_bisector(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ AngleBisector（角平分线）暂不支持转换（变量 {var}）"


@register_converter("AngleDivLine")
def _conv_angle_div_line(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ AngleDivLine（等分角线）暂不支持转换（变量 {var}）"


@register_converter("PerpBisector")
def _conv_perp_bisector(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ PerpBisector（中垂线）暂不支持转换（变量 {var}）"


# ───────── 圆 / 曲线 ─────────
@register_converter("Circle")
def _conv_circle(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    var = am[cmd["alias"]]
    if len(parents) < 2:
        return f"# ⚠ Circle 缺少父对象"
    center = conv.resolve_parent(parents[0])
    through = conv.resolve_parent(parents[1])
    return f"{var} = circle({center}, {through})"


@register_converter("ExprCircle")
def _conv_expr_circle(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    params = cmd.get("params", {})
    expr = params.get("expr", "1")
    var = am[cmd["alias"]]
    if len(parents) < 1:
        return f"# ⚠ ExprCircle 缺少圆心"
    center = conv.resolve_parent(parents[0])
    return f'{var} = circle({center}, "{expr}")'


@register_converter("ThreePointCircle")
def _conv_three_point_circle(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ ThreePointCircle（过三点圆）暂不支持转换（变量 {var}）"


@register_converter("Ellipse")
def _conv_ellipse(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    var = am[cmd["alias"]]
    if len(parents) < 3:
        return f"# ⚠ Ellipse 缺少父对象"
    center = conv.resolve_parent(parents[0])
    axis_a = conv.resolve_parent(parents[1])
    axis_b = conv.resolve_parent(parents[2])
    return f"{var} = ellipse({center}, {axis_a}, {axis_b})"


@register_converter("CubicBezier")
def _conv_cubic_bezier(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ CubicBezier（贝塞尔曲线）暂不支持转换（变量 {var}）"


@register_converter("FunctionCurve")
def _conv_function_curve(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    params = cmd.get("params", {})
    kind = params.get("kind", "explicit")
    expr = params.get("expr", "x")
    expr2 = params.get("expr2", "")
    var = am[cmd["alias"]]
    if kind == "explicit":
        return f'{var} = function("{expr}")'
    elif kind == "parametric":
        return f'{var} = parametric("{expr}", "{expr2}")'
    elif kind == "polar":
        return f'{var} = polar("{expr}")'
    return f'# ⚠ FunctionCurve 未知类型：{kind}'


# ───────── 多边形 ─────────
@register_converter("RegularPolygon")
def _conv_regular_polygon(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    parents = cmd.get("parents", [])
    params = cmd.get("params", {})
    n = params.get("n", 3)
    var = am[cmd["alias"]]
    if len(parents) < 2:
        return f"# ⚠ RegularPolygon 缺少父对象"
    center = conv.resolve_parent(parents[0])
    vertex = conv.resolve_parent(parents[1])
    return f"{var} = regular_polygon({center}, {vertex}, {n})"


@register_converter("ChainFill")
def _conv_chain_fill(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ ChainFill（链式填充）暂不支持转换（变量 {var}）"


# ───────── 度量 ─────────
@register_converter("AngleMeasure")
def _conv_angle_measure(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ AngleMeasure（角度度量）暂不支持转换（变量 {var}）"


@register_converter("RatioMeasure")
def _conv_ratio_measure(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ RatioMeasure（比例度量）暂不支持转换（变量 {var}）"


@register_converter("Measure")
def _conv_measure(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    params = cmd.get("params", {})
    kind = params.get("kind", "unknown")
    var = am[cmd["alias"]]
    return f"# ⚠ Measure（{kind} 度量）暂不支持转换（变量 {var}）"


@register_converter("ExprSegment")
def _conv_expr_segment(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    params = cmd.get("params", {})
    expr = params.get("expr", "")
    var = am[cmd["alias"]]
    return f"# ⚠ ExprSegment（表达式线段，表达式：{expr}）暂不支持转换（变量 {var}）"


@register_converter("ExprAngle")
def _conv_expr_angle(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    params = cmd.get("params", {})
    expr = params.get("expr", "")
    var = am[cmd["alias"]]
    return f"# ⚠ ExprAngle（表达式角度，表达式：{expr}）暂不支持转换（变量 {var}）"


@register_converter("ExprPoint")
def _conv_expr_point(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    params = cmd.get("params", {})
    ex = params.get("expr_x", "0")
    ey = params.get("expr_y", "0")
    var = am[cmd["alias"]]
    return f"# ⚠ ExprPoint（表达式点，x={ex}, y={ey}）暂不支持转换（变量 {var}）"


# ───────── 文本 / 媒体 ─────────
@register_converter("TextObject")
def _conv_text_object(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    params = cmd.get("params", {})
    text = params.get("text", "")
    color = params.get("color", "#1f2937")
    size = params.get("size", 16)
    pos = params.get("pos", [0, 0])
    var = am[cmd["alias"]]
    text_escaped = str(text).replace('"', '\\"').replace("\n", "\\n")
    px = conv._fmt_num(pos[0]) if len(pos) > 0 else "0"
    py = conv._fmt_num(pos[1]) if len(pos) > 1 else "0"
    return f'{var} = text({px}, {py}, "{text_escaped}", {size}, "{color}")'


@register_converter("ScriptButtonObject")
def _conv_script_button(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ ScriptButtonObject（脚本按钮）暂不支持转换（变量 {var}）"


@register_converter("TableObject")
def _conv_table(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ TableObject（表格）暂不支持转换（变量 {var}）"


@register_converter("PieChartObject")
def _conv_pie_chart(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ PieChartObject（饼图）暂不支持转换（变量 {var}）"


@register_converter("BarChartObject")
def _conv_bar_chart(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ BarChartObject（柱状图）暂不支持转换（变量 {var}）"


@register_converter("ImageObject")
def _conv_image(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ ImageObject（图片）暂不支持转换（变量 {var}）"


@register_converter("InkStroke")
def _conv_ink_stroke(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ InkStroke（墨迹）暂不支持转换（变量 {var}）"


@register_converter("InkEraser")
def _conv_ink_eraser(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ InkEraser（橡皮擦）暂不支持转换（变量 {var}）"


# ───────── 变换 ─────────
@register_converter("TransformDriver")
def _conv_transform_driver(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ TransformDriver（变换驱动器）暂不支持转换（变量 {var}）"


@register_converter("TransformPoint")
def _conv_transform_point(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ TransformPoint（变换点）暂不支持转换（变量 {var}）"


@register_converter("IterPoint")
def _conv_iter_point(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ IterPoint（迭代点）暂不支持转换（变量 {var}）"


@register_converter("InvertedCircle")
def _conv_inverted_circle(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ InvertedCircle（反演圆）暂不支持转换（变量 {var}）"


@register_converter("CircleAxisPoint")
def _conv_circle_axis_point(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ CircleAxisPoint（圆轴点）暂不支持转换（变量 {var}）"


@register_converter("RegionMeasure")
def _conv_region_measure(am: dict, cmd: dict, conv: MacroToScriptConverter) -> str:
    var = am[cmd["alias"]]
    return f"# ⚠ RegionMeasure（区域度量）暂不支持转换（变量 {var}）"


# ═══════════════════════════════════════════════════════════
#  便捷函数
# ═══════════════════════════════════════════════════════════
def macro_to_script(macro: dict, *, keep: bool = True) -> str:
    """一键转换：宏字典 → 脚本字符串。"""
    converter = MacroToScriptConverter(keep=keep)
    return converter.convert(macro)
