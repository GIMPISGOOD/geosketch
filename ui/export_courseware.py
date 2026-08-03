"""导出到课件：一键生成课件包（含向导）。
修复：bat 中文路径乱码、网页图形拉伸、缺少新对象类型。
"""
import json
import math
import os
import re
import sys
import urllib.request
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QWidget, QWizard, QWizardPage,
                               QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QCheckBox, QSpinBox, QFormLayout)

from ui import theme
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import QByteArray, QBuffer, QPointF, Qt
from core.registry import RENDER_REGISTRY
from media.base import MediaObject

JSX_URL = "https://cdn.jsdelivr.net/npm/jsxgraph@1.8.0/distrib/jsxgraphcore.js"
JSX_CSS_URL = "https://cdn.jsdelivr.net/npm/jsxgraph@1.8.0/distrib/jsxgraph.css"


# ───────────── 预览图（带角标）─────────────
def render_preview(canvas, w=1280, h=800, add_badge=True) -> QImage:
    img = canvas.render_to_image(fit=True, bg_mode="grid", scale=1.0)
    img = img.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)
    if add_badge:
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bw, bh = 190, 52
        x, y = img.width() - bw - 18, img.height() - bh - 18
        p.setPen(QPen(QColor(0, 0, 0, 0), 0))
        p.setBrush(QColor(230, 73, 128, 235))
        p.drawRoundedRect(x, y, bw, bh, 12, 12)
        p.setPen(QColor("#ffffff"))
        f = p.font(); f.setPixelSize(22); f.setBold(True)
        p.setFont(f)
        p.drawText(x, y, bw, bh, 0x0084, "▶  点击运行")
        p.end()
    return img

def _render_media_to_base64(obj):
    """把媒体对象渲染成高分辨率 PNG 的 Base64 字符串，供网页版使用。"""
    view_scale = 60.0  # 1 世界单位 = 60 像素，保证网页里清晰
    w_px = int(obj.width * view_scale)
    h_px = int(obj.height * view_scale)
    if w_px <= 0 or h_px <= 0:
        return None
        
    img = QImage(w_px, h_px, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 构造一个模拟的 view，把对象左上角映射到 (0,0)
    class MockView:
        def __init__(self, obj, scale):
            self.scale = scale
            self.obj = obj
        def to_screen(self, x, y):
            return QPointF((x - self.obj.x) * self.scale, (y - self.obj.y) * self.scale)
            
    mock_view = MockView(obj, view_scale)
    
    # 查找并调用对应的渲染器
    renderer = None
    for cls in type(obj).__mro__:
        if cls in RENDER_REGISTRY:
            renderer = RENDER_REGISTRY[cls]
            break
            
    if renderer:
        old_sel = getattr(obj, 'selected', False)
        obj.selected = False          # 临时取消选中，避免画出 ✎ 按钮和缩放手柄
        try:
            renderer(p, obj, mock_view)
        except Exception:
            pass
        obj.selected = old_sel
    p.end()
    
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return ba.toBase64().data().decode('ascii')


# ───────────── 表达式转换（Python → JS）─────────────
def _py_expr_to_js(expr, var_names):
    s = expr.replace("^", "**")
    s = s.replace("sin(", "Math.sin(")
    s = s.replace("cos(", "Math.cos(")
    s = s.replace("tan(", "Math.tan(")
    s = s.replace("sqrt(", "Math.sqrt(")
    s = s.replace("abs(", "Math.abs(")
    s = s.replace("ln(", "Math.log(")
    s = s.replace("log(", "Math.log10(")
    s = s.replace("exp(", "Math.exp(")
    s = re.sub(r'\bpi\b', 'Math.PI', s)
    s = re.sub(r'\be\b', 'Math.E', s)
    for v in var_names:
        s = re.sub(r'\b' + re.escape(v) + r'\b', f'{v}.Value()', s)
    return s


# ───────────── 交互网页（JSXGraph）─────────────
def _jsx_export(doc, include_vars=True):
    lines = []
    names = {}
    counter = [0]
    all_var_names = doc.vars.names()

    def nv():
        counter[0] += 1
        return f"o{counter[0]}"

    # 导出变量为 slider
    for vname in all_var_names:
        var = doc.vars.get_var(vname)
        if var:
            visible = "true" if include_vars else "false"
            lines.append(f"var {vname} = board.create('slider', ["
                         f"[-8, 9], [8, 9], [{var.vmin}, {var.value}, {var.vmax}]], "
                         f"{{name: '{vname}', precision: 2, visible: {visible}}});")

    # ★ 修复拉伸：boundingbox 宽高比与容器 CSS（92vw × 82vh ≈ 1.8:1）匹配
    ASPECT = 1.8
    xs = [o.x for o in doc.objects
          if type(o).__name__ in ("FreePoint", "PointOnObject", "Midpoint", "ExprPoint")
          and o.exists]
    ys = [o.y for o in doc.objects
          if type(o).__name__ in ("FreePoint", "PointOnObject", "Midpoint", "ExprPoint")
          and o.exists]
    if xs and ys:
        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        half_w = max(x_span, y_span * ASPECT, 4.0) * 0.7 + 2.0
        half_h = half_w / ASPECT
        bb = [cx - half_w, cy + half_h, cx + half_w, cy - half_h]
    else:
        bb = [-10, 10, 10, -10]

    lines.insert(0, f"var board = JXG.JSXGraph.initBoard('box', "
                 f"{{boundingbox: {bb}, axis: true, showNavigation: false}});")

    var_names = all_var_names

    for obj in doc.objects:
        if not (obj.visible and obj.exists):
            continue
        tn = type(obj).__name__

        if tn in ("FreePoint", "ExprPoint"):
            n = nv(); names[obj.id] = n
            lines.append(f"var {n} = board.create('point', [{obj.x:.4f}, {obj.y:.4f}], "
                         f"{{name: 'P{obj.id}', size: 2}});")

        elif tn == "PointOnObject":
            host_name = names.get(obj.host.id)
            if host_name:
                n = nv(); names[obj.id] = n
                lines.append(f"var {n} = board.create('glider', "
                             f"[{obj.x:.4f}, {obj.y:.4f}, {host_name}], "
                             f"{{name: 'P{obj.id}', size: 2}});")

        elif tn == "Segment":
            a, b = names.get(obj.a.id), names.get(obj.b.id)
            if a and b:
                n = nv(); names[obj.id] = n
                lines.append(f"var {n} = board.create('segment', [{a}, {b}], "
                             f"{{strokeColor: '#1971c2', strokeWidth: 2}});")

        elif tn == "Line":
            a, b = names.get(obj.a.id), names.get(obj.b.id)
            if a and b:
                n = nv(); names[obj.id] = n
                lines.append(f"var {n} = board.create('line', [{a}, {b}], "
                             f"{{strokeColor: '#495057', strokeWidth: 2, "
                             f"straightFirst: true, straightLast: true}});")

        elif tn == "Ray":
            origin, through = names.get(obj.origin.id), names.get(obj.through.id)
            if origin and through:
                n = nv(); names[obj.id] = n
                lines.append(f"var {n} = board.create('line', [{origin}, {through}], "
                             f"{{strokeColor: '#0b7285', strokeWidth: 2, "
                             f"straightFirst: false, straightLast: true}});")

        elif tn == "Circle":
            c, t = names.get(obj.center.id), names.get(obj.through.id)
            if c and t:
                n = nv(); names[obj.id] = n
                lines.append(f"var {n} = board.create('circle', [{c}, {t}], "
                             f"{{strokeColor: '#2f9e44', strokeWidth: 2}});")

        elif tn == "Midpoint":
            seg = names.get(obj.seg.id) if hasattr(obj, "seg") else None
            if seg:
                n = nv(); names[obj.id] = n
                lines.append(f"var {n} = board.create('midpoint', "
                             f"[{seg}.point1, {seg}.point2], {{name: '', size: 2}});")

        elif tn == "RegularPolygon":
            c, v = names.get(obj.center.id), names.get(obj.vertex.id)
            if c and v:
                n = nv(); names[obj.id] = n
                lines.append(f"var {n} = board.create('regularpolygon', [{c}, {v}, {obj.n}], "
                             f"{{fillColor: '#ff6b6b', fillOpacity: 0.25, "
                             f"strokeColor: '#ff6b6b', strokeWidth: 2}});")

        elif tn == "IntersectPoint":
            a, b = names.get(obj.a.id), names.get(obj.b.id)
            if a and b:
                n = nv(); names[obj.id] = n
                lines.append(f"var {n} = board.create('intersection', [{a}, {b}, {obj.branch}], "
                             f"{{name: '', size: 2}});")

        elif tn == "Ellipse":
            c_name = names.get(obj.center.id)
            a_name = names.get(obj.axis_a.id)
            b_name = names.get(obj.axis_b.id)
            if c_name and a_name and b_name:
                n = nv(); names[obj.id] = n
                code = (
                    f"var {n} = board.create('curve', ["
                    f"function(t) {{ return {c_name}.X() + ({a_name}.X() - {c_name}.X()) * Math.cos(t) "
                    f"+ ({b_name}.X() - {c_name}.X()) * Math.sin(t); }}, "
                    f"function(t) {{ return {c_name}.Y() + ({a_name}.Y() - {c_name}.Y()) * Math.cos(t) "
                    f"+ ({b_name}.Y() - {c_name}.Y()) * Math.sin(t); }}, "
                    f"0, 2 * Math.PI], {{strokeColor: '#862e9c', strokeWidth: 2}});"
                )
                lines.append(code)

        elif tn == "CubicBezier":
            p0 = names.get(obj.p0.id)
            p1 = names.get(obj.p1.id)
            p2 = names.get(obj.p2.id)
            p3 = names.get(obj.p3.id)
            if p0 and p1 and p2 and p3:
                n = nv(); names[obj.id] = n
                code = (
                    f"var {n} = board.create('curve', ["
                    f"function(t) {{ var u=1-t; return u*u*u*{p0}.X() + 3*u*u*t*{p1}.X() "
                    f"+ 3*u*t*t*{p2}.X() + t*t*t*{p3}.X(); }}, "
                    f"function(t) {{ var u=1-t; return u*u*u*{p0}.Y() + 3*u*u*t*{p1}.Y() "
                    f"+ 3*u*t*t*{p2}.Y() + t*t*t*{p3}.Y(); }}, "
                    f"0, 1], {{strokeColor: '#087f5b', strokeWidth: 2}});"
                )
                lines.append(code)

        elif tn == "AngleMeasure":
            v_name = names.get(obj.vertex.id)
            p1_name = names.get(obj.p1.id)
            p2_name = names.get(obj.p2.id)
            if v_name and p1_name and p2_name:
                n = nv(); names[obj.id] = n
                lines.append(f"var {n} = board.create('angle', [{p1_name}, {v_name}, {p2_name}], "
                             f"{{strokeColor: '#e8590c', strokeWidth: 2}});")

        elif tn == "FunctionCurve":
            n = nv(); names[obj.id] = n
            js_expr = _py_expr_to_js(obj.expr, var_names)
            if obj.kind == "explicit":
                lines.append(f"var {n} = board.create('functiongraph', "
                             f"[function(x) {{ return {js_expr}; }}], "
                             f"{{strokeColor: '{obj.color}', strokeWidth: 2}});")
            elif obj.kind == "parametric":
                js_expr2 = _py_expr_to_js(obj.expr2, var_names)
                domain = obj.domain or (0, 2 * math.pi)
                lines.append(f"var {n} = board.create('curve', ["
                             f"function(t) {{ return {js_expr}; }}, "
                             f"function(t) {{ return {js_expr2}; }}, "
                             f"{domain[0]}, {domain[1]}], "
                             f"{{strokeColor: '{obj.color}', strokeWidth: 2}});")
            elif obj.kind == "polar":
                domain = obj.domain or (0, 2 * math.pi)
                lines.append(f"var {n} = board.create('curve', ["
                             f"function(t) {{ return {js_expr} * Math.cos(t); }}, "
                             f"function(t) {{ return {js_expr} * Math.sin(t); }}, "
                             f"{domain[0]}, {domain[1]}], "
                             f"{{strokeColor: '{obj.color}', strokeWidth: 2}});")

        # ★ 新增：墨迹笔画
        elif tn == "InkStroke":
            n = nv(); names[obj.id] = n
            xs = [p[0] for p in obj.points]
            ys = [p[1] for p in obj.points]
            lines.append(f"var {n} = board.create('curve', [{xs}, {ys}], "
                         f"{{strokeColor: '{obj.color}', strokeWidth: {obj.width}, "
                         f"opacity: {obj.opacity}}});")
        # ★ 新增：媒体对象（表格/图表/图像）转图片渲染
        elif isinstance(obj, MediaObject):
            b64 = _render_media_to_base64(obj)
            if b64:
                n = nv(); names[obj.id] = n
                # JSXGraph 的 image 坐标是左下角，且高度向上延伸
                x_bl = obj.x
                y_bl = obj.y + obj.height
                # 替换 Base64 中的换行符以防 JS 报错
                b64_clean = b64.replace("\n", "")
                lines.append(f"var {n} = board.create('image', "
                             f"['data:image/png;base64,{b64_clean}', "
                             f"[{x_bl}, {y_bl}], [{obj.width}, {obj.height}]], "
                             f"{{fixed: false, highlight: false}});")

    return "\n".join(lines), bb


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>GeoSketch 交互课件</title>
<script src="jsxgraphcore.js"></script>
<link rel="stylesheet" href="jsxgraph.css">
<style>
  body {{ margin: 0; background: #eef2f8; display: flex; flex-direction: column;
         align-items: center; font-family: "Microsoft YaHei", sans-serif; }}
  h1 {{ font-size: 16px; color: #2c3a4e; margin: 14px 0 8px; }}
  #box {{ width: 92vw; height: 82vh; max-width: 1100px; background: #f8fafd;
          border: 1px solid #dde5ef; border-radius: 10px; }}
  .tip {{ color: #5a6b82; font-size: 12px; margin-top: 8px; }}
</style>
</head>
<body>
<h1>GeoSketch 交互课件 —— 直接拖动点试一试</h1>
<div id="box" class="jxgbox"></div>
<div class="tip">提示：拖动彩色点，依赖它的图形会跟着变。完整版功能请用"运行.bat"。</div>
<script>
{code}
</script>
</body>
</html>"""


def _fetch_jsxgraph(dest_dir: Path) -> bool:
    for fname, url in [("jsxgraphcore.js", JSX_URL), ("jsxgraph.css", JSX_CSS_URL)]:
        try:
            urllib.request.urlretrieve(url, dest_dir / fname)
        except Exception:
            return False
    return True


def _make_launcher(dest_dir: Path, json_name: str):
    """★ 修复：用 utf-8-sig（带 BOM）写入，json 用纯英文名避免乱码。"""
    py = sys.executable
    app = os.path.abspath(sys.argv[0])
    bat = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        f'"{py}" "{app}" "%~dp0{json_name}"\r\n'
    )
    (dest_dir / "运行.bat").write_text(bat, encoding="utf-8-sig")


def _do_export(canvas, folder, gen_preview=True, gen_web=True, gen_launcher=True,
               gen_readme=True, preview_w=1280, preview_h=800, add_badge=True,
               offline=True, include_vars=True, parent=None):
    doc = canvas.doc
    pkg = Path(folder) / "GeoSketch课件"
    pkg.mkdir(parents=True, exist_ok=True)

    if gen_preview:
        render_preview(canvas, preview_w, preview_h, add_badge).save(str(pkg / "预览.png"))

    # ★ 修复：json 用纯英文名，避免 bat 中文路径乱码
    json_name = "sketch.json"
    doc.save(str(pkg / json_name))

    if gen_launcher:
        _make_launcher(pkg, json_name)

    if gen_web:
        code, _ = _jsx_export(doc, include_vars=include_vars)
        offline_ok = _fetch_jsxgraph(pkg) if offline else False
        html = HTML_TEMPLATE.format(code=code)
        if not offline_ok:
            html = html.replace('src="jsxgraphcore.js"', f'src="{JSX_URL}"')
            html = html.replace('<link rel="stylesheet" href="jsxgraph.css">',
                                f'<link rel="stylesheet" href="{JSX_CSS_URL}">')
        (pkg / "交互.html").write_text(html, encoding="utf-8")

    if gen_readme:
        readme = (
            "GeoSketch 课件包 使用说明\n" + "=" * 30 + "\n\n"
            "【在 PPT / WPS 中使用】\n"
            "1. 把\"预览.png\"插入幻灯片；\n"
            "2. 右键图片 → 超链接/动作设置 → 选择\"运行程序\" → 选中本文件夹里的\"运行.bat\"；\n"
            "3. 放映时点击预览图，即自动打开 GeoSketch 并载入本草图。\n\n"
            "【浏览器版（无需安装）】\n"
            "双击\"交互.html\"即可在浏览器中打开，点可拖动。\n"
            + ("" if offline else "注意：交互.html 需联网才能打开。\n")
            + "\n【注意】运行.bat 里写死了当前电脑上 Python 和应用的路径，\n"
            "若换电脑或移动了 GeoSketch 文件夹，需右键\"运行.bat\"→编辑，改成新路径。\n"
        )
        (pkg / "使用说明.txt").write_text(readme, encoding="utf-8")

    if parent:
        QMessageBox.information(parent, "导出成功", f"课件包已生成：\n{pkg}")


class CoursewareWizard(QWizard):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setWindowTitle("导出课件向导")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setMinimumSize(500, 400)
        self.addPage(self._page_location())
        self.addPage(self._page_preview())
        self.addPage(self._page_web())
        self.setButtonText(QWizard.WizardButton.FinishButton, "导出")
        self.setButtonText(QWizard.WizardButton.CancelButton, "取消")
        self.setButtonText(QWizard.WizardButton.NextButton, "下一步")
        self.setButtonText(QWizard.WizardButton.BackButton, "上一步")

    def _page_location(self):
        page = QWizardPage()
        page.setTitle("导出位置与内容")
        layout = QVBoxLayout(page)
        loc_layout = QHBoxLayout()
        self.loc_edit = QLineEdit()
        self.loc_edit.setPlaceholderText("选择导出文件夹...")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse)
        loc_layout.addWidget(QLabel("位置:"))
        loc_layout.addWidget(self.loc_edit)
        loc_layout.addWidget(browse_btn)
        layout.addLayout(loc_layout)
        self.chk_preview = QCheckBox("生成预览图 (预览.png)")
        self.chk_preview.setChecked(True)
        self.chk_web = QCheckBox("生成交互网页 (交互.html)")
        self.chk_web.setChecked(True)
        self.chk_launcher = QCheckBox("生成启动器 (运行.bat)")
        self.chk_launcher.setChecked(True)
        self.chk_readme = QCheckBox("生成说明文件 (使用说明.txt)")
        self.chk_readme.setChecked(True)
        layout.addWidget(self.chk_preview)
        layout.addWidget(self.chk_web)
        layout.addWidget(self.chk_launcher)
        layout.addWidget(self.chk_readme)
        layout.addStretch()
        return page

    def _page_preview(self):
        page = QWizardPage()
        page.setTitle("预览图设置")
        layout = QFormLayout(page)
        self.preview_w = QSpinBox()
        self.preview_w.setRange(640, 3840)
        self.preview_w.setValue(1280)
        self.preview_h = QSpinBox()
        self.preview_h.setRange(480, 2160)
        self.preview_h.setValue(800)
        self.chk_badge = QCheckBox("添加\"▶ 点击运行\"角标")
        self.chk_badge.setChecked(True)
        layout.addRow("宽度:", self.preview_w)
        layout.addRow("高度:", self.preview_h)
        layout.addRow(self.chk_badge)
        return page

    def _page_web(self):
        page = QWizardPage()
        page.setTitle("交互网页设置")
        layout = QVBoxLayout(page)
        self.chk_offline = QCheckBox("下载 JSXGraph 到本地 (离线可用)")
        self.chk_offline.setChecked(True)
        self.chk_vars = QCheckBox("包含变量滑杆 (如果文档有变量)")
        self.chk_vars.setChecked(True)
        layout.addWidget(self.chk_offline)
        layout.addWidget(self.chk_vars)
        layout.addStretch()
        return page

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        if folder:
            self.loc_edit.setText(folder)

    def accept(self):
        folder = self.loc_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "提示", "请先选择导出文件夹。")
            return
        try:
            _do_export(
                self.canvas, folder,
                gen_preview=self.chk_preview.isChecked(),
                gen_web=self.chk_web.isChecked(),
                gen_launcher=self.chk_launcher.isChecked(),
                gen_readme=self.chk_readme.isChecked(),
                preview_w=self.preview_w.value(),
                preview_h=self.preview_h.value(),
                add_badge=self.chk_badge.isChecked(),
                offline=self.chk_offline.isChecked(),
                include_vars=self.chk_vars.isChecked(),
                parent=self
            )
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中发生错误：\n{e}")


def export_courseware(canvas, parent=None):
    wiz = CoursewareWizard(canvas, parent)
    wiz.exec()