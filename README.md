# GeoSketch · 几何画板

**一个基于 Python 与 PySide6 的开源动态几何画板**  
支持尺规作图、动态变量、函数曲线、几何变换、交互式课件导出……  
代码体积仅 462KB，却具备专业软件的扩展性与交互体验。
  
（*实际运行界面以主题为准，支持纸白/墨夜/蓝图/黑板四种配色*）

---

## 🎯 简介

GeoSketch 是一款**响应式动态几何软件**，它不同于传统绘图工具，而是构建了一个**基于依赖图的约束求解引擎**。用户绘制几何对象时，系统自动维护对象间的依赖关系——拖动任意父对象，所有子对象（如交点、中点、垂线、表达式线段）都会**实时联动更新**。

主要应用场景：
- 数学教学（几何定理演示、函数图像探索）
- 课件制作（一键导出可交互的 HTML 课件）
- 几何可视化与原型设计

---

## ✨ 主要特性

| 类别 | 功能 |
|------|------|
| **几何作图** | 点（自由/吸附/交点/等分）、线段、圆、椭圆、直线、射线、多边形、贝塞尔曲线 |
| **动态约束** | 表达式线段（长度绑定变量）、表达式角度、表达式圆、表达式点 |
| **函数曲线** | 显函数 `y=f(x)`、参数方程 `(x(t),y(t))`、极坐标 `r=f(θ)`，支持变量联动和异步采样 |
| **变换系统** | 平移、旋转、缩放、反射、中心对称、仿射（矩阵/三点定）、反演、迭代点列 |
| **度量工具** | 长度、距离、角度、比例、面积、周长、半径、直径、斜率、坐标 |
| **媒体对象** | 插入图片、表格（可含变量）、饼图、柱状图（数据可绑定变量） |
| **变量与滑杆** | 创建独立/从动变量，实时滑杆控制，表达式即时求值 |
| **墨迹注释** | 钢笔/荧光笔/铅笔/橡皮擦，支持撤销单笔 |
| **主题系统** | 内置四套配色（纸白/墨夜/蓝图/黑板），支持自定义导入导出 |
| **导出功能** | PNG/SVG 高清导出，交互式 HTML 课件（含 JSXGraph 引擎），课件包可直接嵌入 PPT |
| **扩展机制** | 通过装饰器注册新对象、工具、渲染器，无需改动主代码 |

---

## 🚀 安装与运行

### 环境要求
- Python 3.9 或更高版本
- 操作系统：Windows / macOS / Linux

### 安装依赖
```bash
pip install PySide6 qtawesome
```

### 启动
```bash
python main.py
```

### 直接打开 `.wgeo` 文件
```bash
python main.py 草图.wgeo
```

---

## 🧭 使用指南

### 界面布局
- **左侧工具栏**：核心作图工具（点、线段、圆、选择、框选等）
- **右侧函数编辑器**：管理变量与函数曲线（可折叠）
- **右下缩放条**：以画布中心缩放 / 重置视图
- **信息面板**：显示选中对象的属性（位置、长度、面积等）
- **状态栏**：鼠标坐标、当前工具提示、对象数量

### 基本操作
| 操作 | 说明 |
|------|------|
| 左键点击 | 使用当前工具（创建对象或选择） |
| 按住并拖动 | 移动选中的点或图形（仅限自由点） |
| 滚轮 | 以光标位置缩放 |
| 中键拖拽 | 平移画布 |
| `Delete` / `Backspace` | 删除选中的对象（级联删除） |
| `Esc` | 取消当前工具状态 |

### 工具速览
- **选择** (`V`)：点选对象，拖拽移动，靠近坐标轴/其他点时有智能吸附参考线
- **点** (`P`)：点击生成自由点；点击线段/圆上生成吸附点
- **线段** (`S`)：点击两点生成线段
- **圆** (`C`)：点击圆心与半径点
- **框选**：按住拖拽矩形框批量选择
- **交点** (`X`)：依次点击两个图形（线段/圆/多边形）生成全部交点
- **多边形** (`G`)：选中心与顶点，上方浮层选择边数（3~8）
- **函数曲线**：通过右侧「函数编辑器」添加，支持显式/参数/极坐标
- **更多插件工具**：角平分线、平行线、垂线、N等分、贝塞尔、定长线段、定角……

---

## 🔬 核心机制解析

### 1. 响应式依赖引擎
所有几何对象（`GeoObject`）维护 `parents`（父对象）和 `children`（子对象）列表。当任何父对象发生变动，`Document` 自动调用 `recompute_from(roots)`，**仅重算受影响子树**，极大提升大型作图的性能。

### 2. 表达式与变量系统
- 变量名支持任意 UTF-8 字符（如 `边长`、`α`）。
- 表达式语法支持 `+ - * / ^`、函数（`sin/cos/sqrt/ln` 等）、常量（`pi/e`）以及**隐式乘法**（`2a` 等价 `2*a`）。
- 变量分为**独立变量**（由滑杆拖动）和**从动变量**（由表达式定义，如 `b = 2*a + 1`），支持多级依赖。
- 表达式对象（`ExprSegment`、`ExprAngle`、`ExprCircle`、`ExprPoint`）将几何属性与变量绑定，随变量变化实时更新。

### 3. 函数曲线异步采样
函数曲线由后台线程计算采样点，主线程仅绘制缓存，避免滑杆拖动时界面卡顿。同时实现了**版本号缓存**，仅当变量或视窗变化时才重新采样。

### 4. 变换系统
- 支持平移、旋转、缩放、反射、中心对称、仿射（矩阵 / 三对应点）、反演。
- 变换可**迭代应用**（深度控制），轻松创建分形图案。
- 变换支持复合对象（线段、圆、椭圆、多边形等），自动处理点映射。

---

## 🧩 扩展开发

GeoSketch 采用**注册表驱动**的插件架构，无需修改内核即可增加新功能。

### 添加新几何对象
1. 在 `geo/` 下新建 `.py` 文件。
2. 定义类继承 `GeoObject`，实现 `recompute()`、`distance_to()`、`point_at()`（若需吸附）、`dump()`/`build()`（序列化）。
3. 使用 `@register_geo("类型名")` 注册。
4. 编写渲染函数，用 `@register_renderer(类名)` 注册。

```python
from core.registry import register_geo, register_renderer
from geo.base import GeoObject

@register_geo("MyCurve")
class MyCurve(GeoObject):
    # ... 实现
    pass

@register_renderer(MyCurve)
def draw_my_curve(p, obj, view):
    # ... 绘制
    pass
```

### 添加新工具
1. 在 `tools/` 或 `plugins/` 下新建文件。
2. 定义类继承 `Tool`，实现 `press`/`move`/`release` 等方法。
3. 使用 `@register_tool(name, shortcut, order, panel, hint, icon)` 注册，`panel` 可选 `"rail"`（左侧工具栏）、`"menu"`（工具菜单）、`"insert"`（插入菜单）、`"measure"`（度量菜单）、`"transform"`（变换菜单）。

```python
@register_tool(name="我的工具", shortcut="M", panel="rail", hint="示例工具")
class MyTool(Tool):
    def press(self, canvas, wpt, hit):
        # 处理点击
        pass
```

### 添加主题
在 `ui/theme.py` 的 `THEMES` 字典中新增条目，键为颜色名（如 `BG_TOP`），值为十六进制字符串或 RGBA 元组。

---

## 📦 项目结构

```
GeoSketch/
├── main.py                 # 程序入口
├── core/                   # 核心引擎
│   ├── document.py         # 文档模型（对象管理、撤销/重做、序列化）
│   ├── registry.py         # 全局注册表
│   └── variables.py        # 变量系统（表达式求值、存储）
├── geo/                    # 几何对象库
│   ├── base.py             # GeoObject 基类
│   ├── points.py           # 点类（自由/吸附）
│   ├── segments.py         # 线段
│   ├── circles.py          # 圆
│   ├── function_curve.py   # 函数曲线
│   ├── constraints.py      # 表达式约束
│   ├── chain_fill.py       # 区域填充
│   └── ...                 # 其他对象（椭圆、贝塞尔、多边形等）
├── tools/                  # 交互工具
│   ├── base.py             # Tool 基类与辅助函数
│   ├── select.py           # 选择工具
│   ├── point_tool.py
│   ├── segment_tool.py
│   ├── circle_tool.py
│   └── ...
├── plugins/                # 扩展工具（自动扫描）
│   ├── angle_tool.py
│   ├── bisector_tool.py
│   ├── divide_tool.py
│   └── ...
├── media/                  # 媒体对象（图片、表格、图表）
├── transforms/             # 变换系统（驱动、点、圆、工具）
├── ui/                     # 界面组件
│   ├── canvas.py           # 画布控件
│   ├── main_window.py      # 主窗口
│   ├── theme.py            # 主题系统
│   ├── math/               # 数学排版引擎
│   ├── variable_widgets.py
│   └── ...
└── tests/                  # 单元测试（pytest）
```

---

## 🔗 依赖项

- [PySide6](https://pypi.org/project/PySide6/) —— Qt for Python，GUI 框架
- [qtawesome](https://pypi.org/project/qtawesome/) —— 图标库（Font Awesome / Material Design Icons）

*可选*：若要离线使用课件导出，需要联网下载 JSXGraph 库（`jsxgraphcore.js` 与 `jsxgraph.css`）。

---

## 📄 许可证

本项目采用 **MIT License**，欢迎自由使用、修改和分发。

---

## 🙏 致谢

- 灵感来源于 [GeoGebra](https://www.geogebra.org/) 与 [Desmos](https://www.desmos.com/)
- 图标由 [Font Awesome](https://fontawesome.com/) 与 [Material Design Icons](https://materialdesignicons.com/) 提供
- 数学渲染引擎参考了 [MathJax](https://www.mathjax.org/) 的排版思想

---

## 📬 反馈与贡献

欢迎提交 Issue 或 Pull Request。如果你有改进建议或发现 Bug，请通过 GitHub 与我们联系。

**Enjoy dynamic geometry!** 🎨📐