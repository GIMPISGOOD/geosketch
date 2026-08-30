根据您提供的格式，以下是对 GeoSketch 项目全部文件 的完整说明（已略去末尾 bug 描述，仅保留纯净的目录结构与功能摘要）。

项目整体目录树
geosketch/
├── main.py                      # 应用入口：初始化 QApp、加载扩展、启动主窗口
├── models/                      # ★ 新增：本地 AI 模型文件目录
├── animation/                   # 动画系统（关键帧/轨道/录制/时间轴 UI）
├── constraints/                 # 约束求解器（LM 算法 + 各类几何约束）
├── core/                        # 核心层：文档模型、变量系统、脚本引擎
├── examples/                    # 示例项目库（.zip 课件包，含缩略图）
├── geo/                         # 几何内核：点/线/圆/曲线/填充/求交
├── media/                       # 媒体对象：图表/表格/图片/脚本按钮
├── plugins/                     # 扩展插件：垂线/角平分线/度量/多边形等
├── resources/                   # 静态资源（如 STIX2Math.otf 字体）
├── tests/                       # 单元测试（pytest，覆盖核心与几何逻辑）
├── tools/                       # 基础交互工具（选择/画点/画线/画圆等）
├── transforms/                  # 几何变换（平移/旋转/缩放/反演/迭代）
└── ui/                          # 用户界面（画布/面板/主题/数学排版）

根目录
main.py
说明：程序的启动脚本，负责初始化 `QApplication`、加载约束和动画扩展（`load_constraints` / `load_animation`）、创建主窗口，并在退出时清理后台采样线程。

models/（★ 新增：本地 AI 模型）
models/qwen2.5-3b-instruct-q4_k_m.gguf
说明：Qwen2.5-3B 指令微调模型（Q4_K_M 量化，约 2.1 GB）。用于自然语言构造推理：将用户的中文几何描述（如"画一个等边三角形 ABC，边长 5，再作它的外接圆"）转化为 GeoSketch DSL 脚本。选择 3B 而非更大模型的原因：笔记本 CPU 可达 8-15 token/s，中文数学术语理解优秀。

models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf
说明：Qwen2.5-Coder-1.5B 代码专用模型（Q4_K_M 量化，约 1.2 GB）。用于脚本编辑器的 AI 补全与代码生成。1.5B 参数量在代码补全场景下足够，且推理速度更快（15-25 token/s），适合实时补全的低延迟需求。

core/（核心引擎）
core/__init__.py
说明：空文件，标识 `core` 为 Python 包。

core/document.py
说明：项目最核心的 "上帝类"——`Document`。持有所有几何对象、变量、约束、动画列表，负责增删改查、级联重算、撤销重做（Undo/Redo）、序列化存/加载 `.wgeo` 文件）。★ 已原生集成约束和动画（去补丁化）。`solve_constraints()` 在收集可优化点时，除 `FreePoint` 外还收集 `PointOnObject`（吸附点）进入 `free_set`，使求解器能驱动吸附点沿宿主曲线滑动以满足距离/角度等约束。

core/variables.py
说明：变量系统（`VariableStore`）。支持表达式求值（`evaluate`）、变量绑定（绑定到几何度量值）、模板渲染（`render_template`，即文本中 `{a}` 的替换），是连接"代数"与"几何"的桥梁。

core/registry.py
说明：全局注册表（`GEO_REGISTRY` / `TOOL_REGISTRY` / `RENDER_REGISTRY`）。所有几何对象、工具、渲染器通过装饰器（如 `@register_geo`）在此注册，实现"高内聚低耦合"的插件架构。

core/macro.py
说明：宏录制与回放系统（`MacroRecorder` / `MacroPlayer` / `MacroManager`）。监听文档变化，生成宏命令列表，支持回放和宏管理。

core/scripting/__init__.py
说明：脚本引擎入口。暴露 `run_script`、`parse`、`register_script_library` 等接口。

core/scripting/ast_nodes.py
说明：定义脚本的抽象语法树（AST）节点（`Program`、`FuncDef`、`If`、`ForRange`、`Call` 等）。

core/scripting/parser.py
说明：递归下降语法分析器，将 Token 流解析为 AST。

core/scripting/tokens.py
说明：词法分析器，将脚本源码切分为 Token（支持中英文关键字，如 `func` / `函数`，`if` / `如果`）。

core/scripting/interpreter.py
说明：AST 解释器（`Interpreter`）。执行脚本，管理作用域链，调用 `ObjectFactory` 创建几何对象，并支持 `wait` 等待（依赖 Qt 事件循环）。

core/scripting/scope.py
说明：作用域（`Scope`）与用户函数（`UserFunction`）定义。支持变量查找的链式委托。

core/scripting/errors.py
说明：自定义脚本异常（`ScriptError`、`ScriptReturn`），带行号定位。

core/scripting/functions.py
说明：内置全局函数映射（`sin/cos/point/segment/circle/print` 等），将 DSL 函数绑定到 `ObjectFactory` 的具体方法。

core/scripting/object_factory.py
说明：几何对象工厂（`ObjectFactory`），将脚本中的 `point(1,2)` 等调用转换为实际的 `FreePoint`、`Segment` 等 Python 对象。

core/scripting/object_destructor.py
说明：脚本对象销毁器，处理 `delete` 语句，并检查 `__allow_delete_user` 等安全标志。

core/scripting/macro_converter.py
说明：宏 → 脚本转换引擎（`macro_to_script`）。通过 `@register_converter` 注册不同类型对象的转换逻辑，将录制的宏命令（`add/move/delete`）翻译为可读的 DSL 脚本代码。

core/scripting/libraries/__init__.py
说明：内置库入口，根据库名（`math` / `geo` / `draw` / `doc`）返回对应的函数字典。

core/scripting/libraries/math_lib.py
说明：`math` 库，提供 `sin/cos/sqrt/pi/random` 等数学函数。

core/scripting/libraries/geo_lib.py
说明：`geo` 库，提供 `distance/length/area/perimeter/slope` 等几何度量函数。

core/scripting/libraries/draw_lib.py
说明：`draw` 库，提供 `point/segment/circle/line` 等绘图函数（与全局函数类似，但显式归类）。

core/scripting/libraries/doc_lib.py
说明：`doc` 库，提供 `delete/find/delete_all` 等文档操作函数。

geo/（几何内核）
geo/__init__.py
说明：自动导入 `geo/` 下所有子模块，触发 `@register_geo` 注册。

geo/base.py
说明：所有几何对象的基类 `GeoObject`。定义 `parents` / `children` 依赖树、`recompute()` 级联更新、`dump()` / `build()` 序列化契约，以及 `point_at(t)` / `project(x,y)` 参数化接口（用于磁吸吸附）。

geo/points.py
说明：点对象（`AbstractPoint` / `FreePoint` / `PointOnObject`）。`FreePoint` 可自由拖动，`PointOnObject` 吸附在曲线/线段上。包含磁吸查询函数 `nearest_point` 和自动标签生成（A、B、C...）。

geo/segments.py
说明：`Segment` 线段，由两个端点定义。实现了 `length()`、`point_at(t)`、`project(x,y)`，支持吸附和度量。

geo/circles.py
说明：`Circle` 圆，由圆心和圆周上一点定义。支持参数化 `point_at(t)` 和投影 `project(x,y)`（闭合曲线）。

geo/curves.py
说明：参数曲线基类 `ParamCurve`，提供数值投影算法（`_numeric_project`）。`Ellipse` 和 `CubicBezier` 继承于此。

geo/directed_line.py
说明：方向直线基类 `DirectedLine`，用于垂线、平行线、角平分线等无限长直线的数学表示，实现点吸附与求交。

geo/division.py
说明：等分点 `DivisionPoint`，由两个端点 + 比例 `t` 确定，拖动端点时自动按比例重算位置。

geo/intersects.py
说明：交点求解器（`solve`）。注册了线段-线段、线段-圆、圆-圆等求交算法，支持 `IntersectPoint` 对象（根据 `branch` 参数取第几个解）。

geo/function_curve.py
说明：函数曲线 `FunctionCurve`，支持显式 `y=f(x)`、参数方程、极坐标。表达式可含变量，采样在子线程中异步执行（`FunctionSamplerThread`），不阻塞 UI。

geo/function_sampler.py
说明：函数曲线后台采样线程，负责在 `QThread` 中计算大量点，采样完成后通过信号回传主线程更新缓存。

geo/implicit_curve.py
说明：隐函数曲线 `ImplicitCurve`（如 `x^2+y^2=1`）。使用 Marching Squares 算法提取等值线线段，支持变量驱动的动态变形。

geo/implicit_sampler.py
说明：隐函数后台采样线程，将 Marching Squares 的计算移到子线程，避免卡 UI。

geo/chain_fill.py
说明：链式填充 `ChainFill`。支持由直线段和曲线段围成的任意闭合区域填充（纯色/渐变/斜线/交叉斜线），并支持弧段方向选择（短弧/长弧/逆时针/顺时针）。

geo/constraints.py
说明：表达式约束几何对象：`ExprSegment`（表达式线段）、`ExprAngle`（表达式角度）、`ExprCircle`（表达式圆）、`ExprPoint`（表达式点）。它们将自身的几何属性（长度/角度/半径/坐标）锁定为变量代数式，实现"代数驱动几何"。

geo/ink.py
说明：墨迹对象（`InkStroke` 钢笔/荧光笔/铅笔）和橡皮擦（`InkEraser`）。存储手绘点列，渲染为光滑路径或背景色擦除带。

ui/（用户界面）
ui/__init__.py
说明：空文件，标识 `ui` 为 Python 包。


ui/theme.py
说明：多主题系统（纸白/墨夜/蓝图/黑板）。通过模块级 `__getattr__` 动态返回当前主题颜色，并提供 `pen()`、`dashed_pen()`、`brush()` 等绘图工具函数。支持自定义主题的保存/导入/导出。

ui/canvas.py
说明：核心画布 `Canvas`（`QWidget`）。处理鼠标事件（拖拽/点击/滚轮）、工具切换（`set_tool`）、渲染主循环（`paintEvent`）、背景网格/坐标轴绘制。聚合了工具栏（`ToolRail`）、缩放栏（`ZoomBar`）、属性面板（`PropertyPanel`）和函数侧栏（`FunctionEditorDock`）。

ui/canvas_render.py
说明：画布渲染辅助函数。包括背景网格/坐标轴绘制、`content_bbox`（计算所有对象的边界框）、导出高清图时的 `render_to_image`，以及"出版样式（黑白线稿）"的专用渲染逻辑。

ui/canvas_menu.py
说明：画布右键上下文菜单逻辑。包含重命名、隐藏/显示、复制/剪切/粘贴、置顶/置底、选择父/子对象，以及"绑定度量到变量"的快捷入口。

ui/canvas_snow.py
说明：隐藏彩蛋（Easter Egg）——当文档标题为 "Snow" 时，触发下雪粒子动画。

ui/main_window.py
说明：主窗口 `MainWindow`（`QMainWindow`）。构建菜单栏（文件/编辑/视图/构造/度量/变换/插入/高级/帮助）、状态栏、连接信号槽、初始化宏管理器（`MacroManager`）和函数编辑器停靠栏。

ui/tool_rail.py
说明：左侧悬浮工具栏 `ToolRail`。读取 `TOOL_REGISTRY` 中 `panel="rail"` 的工具，生成磨砂玻璃质感的按钮组，点击后切换画布工具。

ui/zoom_bar.py
说明：右下角缩放控件 `ZoomBar`。包含放大/缩小/重置按钮，显示当前缩放百分比（以画布中心为锚点）。

ui/property_panel.py
说明：右侧可折叠属性面板 `PropertyPanel`。根据当前选中对象的类型（点/线段/圆/媒体/函数等），动态生成对应的属性编辑控件（坐标/大小/颜色/表达式等）。

ui/variable_widgets.py
说明：变量滑杆面板（`VariableSliderPanel`）和变量创建向导（`VariableWizard`）。列出所有变量及其滑杆，支持拖拽修改值、绑定到度量（`⛓` 按钮）、解绑和删除变量。

ui/function_panel.py
说明：函数编辑器停靠栏（`FunctionEditorDock`）。以卡片列表形式展示所有函数/隐函数曲线，支持显示/隐藏、编辑（`✎`）、改色（点色块）和删除。可按类型（显式/参数/极坐标/隐函数）过滤。

ui/formula_editor.py
说明：函数/隐函数编辑对话框 `FormulaEditor`。提供虚拟数学键盘（含 `x/y/t/θ`、`sqrt(`、`sin(` 等按键），支持四种模式（显式/参数/极坐标/隐函数），并带有实时 LaTeX 风格数学预览。

ui/script_editor.py
说明：脚本编辑器对话框 `ScriptEditorDialog`。带语法高亮（`ScriptHighlighter`）、行号显示、自动补全（`QCompleter`）、错误行红色高亮，支持 `Ctrl+R` 运行和 `Ctrl+S` 保存。

ui/script_library_manager.py
说明：脚本库管理器 `ScriptLibraryManager`。管理 `doc.script_libs` 中的自定义库（仅允许 `func` 和 `import` 语句，禁止执行代码），提供新建/编辑/删除功能。

ui/macro_dialog.py
说明：宏管理器对话框 `MacroDialog`。列出所有宏，支持回放、重命名、删除，以及核心功能"转为脚本"（调用 `macro_converter.py` 生成脚本代码并预览/复制）。

ui/export_wizard.py
说明：导出图像向导 `ExportWizard`。提供实时预览，支持 PNG（1×/2×/3×）和 SVG 格式，可切换"当前视图"或"适配内容"，以及"出版样式（黑白线稿）"模式。

ui/export_courseware.py
说明：课件包导出向导 `CoursewareWizard`。一键生成包含 `预览.png`、`sketch.json`、`运行.bat` 和 `交互.html`（基于 JSXGraph 的网页版）的独立课件文件夹。

ui/help_gallery.py
说明：示例项目库浏览器 `HelpGalleryWidget`。全屏覆盖主窗口，左侧分类树，右侧网格卡片（每个卡片显示缩略图和标题）。点击卡片自动加载对应的 `.wgeo` 示例文件。

ui/about_dialog.py
说明：关于对话框，带有一个跳跃的圆规图标（物理弹跳动画）。

ui/theme_editor.py
说明：可视化主题编辑器 `ThemeEditorDialog`。允许用户调整所有颜色项（背景/网格/点/线/面等），支持保存/导入/导出主题 JSON 文件。

ui/icons.py
说明：图标工具库。使用 `qtawesome` 加载 Font Awesome / Material Design 图标，提供 `tool_icon(key)`、`trash_icon()`、`zoom_icon()` 等接口，支持主题换色（墨色 ↔ 强调色）。

ui/math/__init__.py
说明：数学排版引擎对外接口。提供 `draw_math(x, y, text, size, color)` 和 `measure_math(text, size)`，内部缓存 AST 和度量结果以提升性能。★ 自动将 `sqrt(...)` 转换为 `\sqrt{...}`。

ui/math/parser.py
说明：LaTeX 风格数学表达式解析器。词法分析（`tokenize`）+ 递归下降语法分析（`parse`），输出 AST（`Ord`、`Bin`、`Sup`、`Sub`、`Frac`、`Sqrt`、`Paren`、`Row` 等节点）。支持希腊字母（`\alpha`）、特殊符号（`\frac`、`\sqrt`）和中文。

ui/math/layout.py
说明：数学排版布局引擎 `MathLayout`。两遍扫描：`measure()` 计算 (宽度, 升部, 降部)，`draw()` 按基线绘制。处理分数、根号、上下标、括号的精确堆叠和基线对齐。

ui/math/font.py
说明：数学字体加载。优先使用随包的 `STIX Two Math` 字体，回退到系统 `Cambria Math` 或 `Times New Roman`，并处理 CJK 字符的正立（非斜体）渲染。

constraints/（约束求解器）
constraints/__init__.py
说明：约束包入口。自动导入 `types/` 下所有约束类型（触发 `@register_constraint` 注册），并注册约束工具的图标。

constraints/base.py
说明：约束基类 `GeometricConstraint`。定义 `involved_points()`、`residual()`、`jacobian()`（雅可比矩阵）接口，以及约束注册表 `CONSTRAINT_REGISTRY` 和 `@register_constraint` 装饰器。`_chain_rule_jacobian()` 中包含三级分发：
① 自由点在 `vars_map` 中 → 直接写入数值偏导；
② 从动点（`PointOnObject` 等）本身在 `vars_map` 中 → 直接写入数值偏导（跳过链式法则，避免父点不在优化集时雅可比归零）；
③ 从动点不在 `vars_map` 中 → 走链式法则转换为父自由点偏导。

constraints/solver.py
说明：Levenberg-Marquardt 非线性最小二乘求解器 `ConstraintSolver`。输入约束列表和自由点，通过迭代优化使所有残差趋近于零。对 `PointOnObject`（吸附点）执行投影修正：每步更新 `(x, y)` 后调用 `host.project()` + `host.point_at()` 将点投影回宿主曲线，同步更新参数 `t`；LM 拒绝步时同步恢复 `t`，保证状态一致性。支持 `quick=True` 低精度模式（12 次迭代，用于拖动帧实时求解）和 `quick=False` 高精度模式（50 次迭代，用于松手后收敛）。

constraints/graph.py
说明：约束图算法（`get_affected_constraints`）。根据触发点（被拖动的点）查找受影响的约束连通分量，避免每次拖动时求解全部约束，提升性能。

constraints/chain_rule.py
说明：从动点坐标对自由点坐标的偏导数（链式法则）。当约束涉及 `PointOnObject`（吸附点）或 `DivisionPoint`（等分点）时，求解器需要知道这些从动点的坐标如何随其父自由点变化，此模块提供解析导数。

constraints/document_ext.py
说明：★ 已废弃（去补丁化）。仅保留空壳 `patch_document()`，实际逻辑已原生集成到 `core/document.py`。

constraints/serialization.py
说明：★ 已废弃（去补丁化）。仅保留空壳 `patch_save_load()`，序列化已原生集成到 `Document.snapshot` / `_load_state`。

constraints/select_ext.py
说明：★ 已废弃（去补丁化）。原用于补丁 `SelectTool.move` / `release`，现已被 `tools/select.py` 内联的 `doc.solve_constraints()` 调用取代。

constraints/types/__init__.py
说明：约束类型包入口，触发所有约束子模块的导入。

constraints/types/distance.py
说明：距离约束 `DistanceConstraint`（两点之间距离等于表达式）。实现解析雅可比矩阵。

constraints/types/angle.py
说明：角度约束 `AngleConstraint`（夹角等于表达式，单位度）。

constraints/types/horizontal.py
说明：水平约束 `HorizontalConstraint`（两点 Y 坐标相等）。提供解析雅可比。

constraints/types/vertical.py
说明：竖直约束 `VerticalConstraint`（两点 X 坐标相等）。提供解析雅可比。

constraints/types/parallel.py
说明：平行约束 `ParallelConstraint`（两条线方向向量叉积为零）。

constraints/types/perpendicular.py
说明：垂直约束 `PerpendicularConstraint`（两条线方向向量点积为零）。

constraints/types/collinear.py
说明：共线约束 `CollinearConstraint`（三点共线，叉积为零）。

constraints/types/fixed.py
说明：固定约束 `FixedConstraint`（点固定在 (x, y) 坐标）。提供解析雅可比。

constraints/types/circle_constraints.py
说明：圆相关约束：`ConcentricConstraint`（同心）、`EqualRadiusConstraint`（等半径）、`TangentCirclesConstraint`（圆-圆相切）、`TangentLineCircleConstraint`（线-圆相切）。

constraints/types/tangent.py
说明：★ 与 `circle_constraints.py` 可能有重叠，保留为向后兼容或新实现。包含 `TangentCC`（圆-圆相切）和 `TangentCL`（线-圆相切）的解析雅可比。

constraints/ui/overlay.py
说明：★ 已废弃（画布约束可视化已直接集成到 `canvas.paintEvent` 中）。原用于在画布上绘制约束参考线（虚线 + 锚点）。

constraints/ui/tools.py
说明：约束创建工具集。包括距离约束工具、固定约束工具、水平/竖直/角度/平行/垂直/共线工具，以及圆相关的同心/等半径/相切工具。核心亮点：实现"智能拾取引擎"（`_extract_points`），点击线段/圆时可自动提取其定义点作为约束目标。

animation/（动画系统）
animation/__init__.py
说明：动画包入口。声明"★ 不再做猴子补丁"，导入 `tracks` 和 `recorder` 完成轨道类型注册。

animation/base.py
说明：动画轨道基类 `AnimationTrack`。定义 `evaluate(time)`、`dump()`、`build()` 契约，以及轨道注册表 `TRACK_REGISTRY` 和 `@register_track` 装饰器。

animation/tracks.py
说明：具体轨道实现：`VariableTrack`（变量轨道）、`GliderTrack`（路径吸附点轨道）、`PropertyTrack`（对象属性轨道，如 `size/rotation/opacity`）。

animation/keyframe.py
说明：关键帧 `Keyframe` 和插值器（`Interpolator`）。支持 6 种缓动函数：线性（`linear`）、缓入缓出（`ease_in_out`）、贝塞尔（`bezier`）、阶梯（`step`）、弹跳（`bounce`）、弹性（`elastic`）。

animation/clip.py
说明：动画片段 `AnimationClip`，包含一组轨道和全局设置（循环/速度/时长）。提供预设模板（匀速往返/缓入缓出/弹跳/弹性/阶梯/正弦往返）。

animation/controller.py
说明：动画控制器 `AnimationController`（`QObject`）。使用 `QTimer` 驱动播放，计算当前时间并调用所有轨道的 `evaluate()` 方法。直接访问 `doc._mutation_count` 来判断是否需要重建对象映射（已原生集成）。

animation/recorder.py
说明：动画录制器 `AnimationRecorder`。每 50ms 采样一次变量或对象属性的值，自动生成关键帧列表。

animation/serialization.py
说明：★ 已废弃（去补丁化）。仅保留空壳，序列化已原生集成到 `Document`。

animation/ui/__init__.py
说明：动画 UI 包入口。

animation/ui/timeline.py
说明：时间轴面板 `TimelineDock`（`QDockWidget`）。包含播放/停止按钮、速度控制、循环开关、时间滑杆、轨道列表，以及"添加轨道"和"录制"功能。

animation/ui/track_editor.py
说明：轨道编辑对话框（`AddTrackDialog` / `EditTrackDialog` / `KeyframeEditor`）。用于添加/编辑轨道中的关键帧（时间/值/插值方式）。

tools/（基础交互工具）
tools/__init__.py
说明：自动导入 `tools/` 下所有子模块，触发 `@register_tool` 注册。

tools/base.py
说明：选择工具 `SelectTool`。支持点选/框选、拖拽移动对象、多选联动拖动，并原生集成约束求解。拖动时将被拖动的点作为 `pinned_points` 传入 `doc.solve_constraints()`（即鼠标位置不可被求解器篡改），其余自由点与吸附点由求解器实时驱动跟随（`quick=True`）；释放时执行完整精度收敛（`quick=False`）。同时提供智能参考线（对齐吸附时的红色虚线引导）。

tools/select.py
说明：选择工具 `SelectTool`。支持点选/框选、拖拽移动对象、多选联动拖动，并原生集成约束求解（拖动时调用 `doc.solve_constraints(quick=True)`，释放时调用 `quick=False`）。同时提供智能参考线（对齐吸附时的红色虚线引导）。

tools/point_tool.py
说明：点工具，点击画布生成点（自动磁吸）。

tools/segment_tool.py
说明：线段工具，点击两次生成线段（端点自动磁吸）。

tools/circle_tool.py
说明：圆工具，点击两次（圆心 → 圆周点）生成圆，拖拽时有虚线预览。

tools/box_select.py
说明：框选工具，拖拽矩形批量选择对象。

tools/ink_tool.py
说明：墨迹工具，支持钢笔/荧光笔/铅笔/橡皮擦四种模式。橡皮擦会真正分割被擦到的笔画（而非简单删除整条）。

tools/intersect_tool.py
说明：交点工具，依次点击两个几何图形（线段/圆/多边形/直线等），生成它们的全部交点（自动去重）。

tools/fixed_angle_tool.py
说明：定角工具，先点顶点和一边点，输入角度值，移动光标选择方向后生成精确角。

tools/length_seg_tool.py
说明：定长线段工具，先点起点，输入长度，移动光标选择方向后生成精确长度的线段。

tools/chain_fill_tool.py
说明：自由填充工具（链式填充）。点→曲线→点→曲线… 描出闭合区域并填充。支持弧段方向选择（短弧/长弧/逆时针/顺时针）和填充规则（偶数/非零环绕）。

plugins/（扩展插件工具）
plugins/__init__.py
说明：自动导入 `plugins/` 下所有子模块，触发工具和几何对象注册。

plugins/line_tool.py
说明：直线工具（过两点无限长直线）及 `Line` 几何对象。

plugins/ray_tool.py
说明：射线工具（端点+方向点）及 `Ray` 几何对象。

plugins/perp_tool.py
说明：垂线工具（先选参照线/线段，再选目标点）及 `PerpLine` 几何对象。

plugins/parallel_tool.py
说明：平行线工具及 `ParallelLine` 几何对象。

plugins/bisector_tool.py
说明：角平分线工具及 `AngleBisector` 几何对象。

plugins/angle_divide_tool.py
说明：等分角工具（将角 n 等分，生成 n-1 条分界线）及 `AngleDivLine` 几何对象。

plugins/construction_tools.py
说明：构造工具集：过三点圆（`ThreePointCircle`）、中垂线（`PerpBisector`）、内心（`Incenter`）、重心（`Centroid`）。

plugins/polygon.py
说明：正多边形工具（`RegularPolygon`），支持边数 3~8 的浮动选择器。同时为 `RegularPolygon` 注册了与线段/圆的交点求解器。

plugins/ellipse_tool.py
说明：椭圆工具（中心+两个轴端点）及 `Ellipse` 几何对象。

plugins/bezier_tool.py
说明：三次贝塞尔曲线工具（4 个控制点）及 `CubicBezier` 几何对象。

plugins/angle_tool.py
说明：角度测量工具及 `AngleMeasure` 几何对象（显示角度值 + 弧形标记）。

plugins/ratio_tool.py
说明：比例工具（两条线段长度比，显示为最简分数）及 `RatioMeasure` 几何对象。

plugins/measure_tools.py
说明：度量工具全家桶：长度/距离/角度/比值/面积/周长/半径/直径/斜率/坐标。包含 `Measure` 对象（通用度量）和 `RegionMeasure` 对象（任意多边形区域的面积+周长）。

plugins/text_tool.py
说明：文本工具及 `TextObject` 几何对象。支持锚定到点（跟随移动）和 `{变量}` 模板渲染。

plugins/divide_tool.py
说明：N 等分工具（将线段 N 等分，生成 N-1 个等分点），支持边数 2~12 的浮动选择器。

plugins/midpoint_tool.py
说明：中点工具（两点连线段的中点）。

plugins/expr_tools.py
说明：表达式工具：`ExprSegmentTool`（表达式线段）和 `ExprAngleTool`（表达式角度）。提供浮动输入面板，实时显示表达式求值结果。

plugins/expr_geo_tools.py
说明：表达式几何工具：`ExprCircleTool`（表达式圆，点圆心 + 输入半径表达式）和 `new_expr_point`（表达式点，输入 x/y 坐标表达式）。

media/（媒体对象）
media/__init__.py
说明：自动导入 `media/` 下所有子模块，触发媒体对象注册。

media/base.py
说明：媒体对象基类 `MediaObject`（继承 `GeoObject`）。提供位置/尺寸/旋转、屏幕矩形计算、编辑/缩放/旋转手柄的命中检测，以及统一的装饰绘制（选中边框 + ✎ 按钮 + 缩放/旋转手柄）。

media/image_obj.py
说明：图片对象 `ImageObject`（支持旋转、等比缩放）。图片数据在保存时内嵌入 `.wgeo` 文件的 `media/images/` 目录。

media/table_obj.py
说明：表格对象 `TableObject`，支持单元格内容中的 `{变量}` 表达式动态求值，以及每格独立背景色。

media/table_wizard.py
说明：插入表格向导（两步：行列数 → 单元格内容与颜色）。

media/chart_obj.py
说明：图表对象：饼图（`PieChartObject`）、柱状图（`BarChartObject`）、折线图（`LineChartObject`）、环形图（`DonutChartObject`）。数据支持 `{变量}` 表达式，变量变化时图表自动重绘。

media/pie_wizard.py
说明：图表数据编辑向导（项数、标签、数值、颜色），供饼图/柱状图/折线图/环形图复用。

media/script_button.py
说明：脚本按钮对象 `ScriptButtonObject`（画布上的可点击按钮）。单击运行绑定的脚本，双击/点击 ✎ 按钮打开脚本编辑器。

media/script_button_tool.py
说明：插入脚本按钮工具（注册到"插入"菜单）。

media/script_button_wizard.py
说明：脚本按钮向导，提供四种预设动作（创建示例图形/清空脚本创建的对象/显示提示/自定义脚本），降低使用门槛。

media/insert_tools.py
说明：插入工具集（注册到"插入"菜单）：插入图像、插入表格、插入饼图、插入柱状图、插入折线图、插入环形图。

transforms/（几何变换）
transforms/__init__.py
说明：自动导入 `transforms/` 下所有子模块，触发变换对象注册。

transforms/base.py
说明：变换数学基础。包含表达式求值（`eval_num`）、矩阵运算（`identity`、`translation`、`rotation_matrix`、`scale_matrix`、`reflect_matrix`、`apply_matrix`），以及通过三组对应点求解仿射矩阵的 `solve_affine` 函数。

transforms/objects.py
说明：变换核心对象：`TransformDriver`（变换驱动器，存储变换类型/参数/表达式）、`TransformPoint`（变换点，由驱动器作用于源点生成）、`CircleAxisPoint`（圆上的辅助轴点）、`InvertedCircle`（圆在反演变换下的像）、`IterPoint`（迭代点，`x_{n+1}=f(x_n,y_n)`）。

transforms/apply.py
说明：变换应用引擎 `create_transformed_copies`。将 `TransformDriver` 应用到选中的几何对象（点/线段/直线/射线/圆/椭圆/正多边形），支持深度迭代（`depth` 参数）。

transforms/tools.py
说明：变换工具集（注册到"变换"菜单）。包括平移（坐标/向量/线段）、旋转（角度）、缩放（因子/线段比）、反射（轴对称/中心对称）、仿射（矩阵/三对应点）、反演（圆/中心+半径）、迭代点列。

resources/ 和 examples/
resources/fonts/STIX2Math.otf
说明：数学排版引擎使用的 STIX Two Math 字体文件（OpenType），用于渲染根号、分式、上下标等数学符号。

examples/基础几何/三角形内角和.zip
说明：示例项目包（ZIP 格式），内含 `.wgeo` 文件和缩略图，通过 `help_gallery` 加载。

tests/（单元测试）
tests/conftest.py
说明：pytest 配置，提供 `qapp`（离屏 Qt 应用）、`doc`（空文档）和 `canvas`（离屏画布）等测试夹具。

tests/test_core_document.py
说明：`Document` 核心功能测试（增删改查、撤销重做、级联删除、复制粘贴）。

tests/test_core_variables.py
说明：变量系统测试（定义/修改/删除、从动变量求值、表达式求值、模板渲染）。

tests/test_geometry_objects.py
说明：几何对象测试（点/线段/圆/直线/射线/等分点/吸附点/椭圆/填充/交点/函数曲线）。

tests/test_solver.py
说明：约束求解器集成测试（距离约束 + 水平约束、吸附点链式法则、圆相切解析雅可比、交点约束）。

tests/test_attached_point.py
说明：吸附点（`PointOnObject`）专项测试（在线段/圆上的投影、拖动边界、父对象移动时跟随）。

tests/test_function_curve.py
说明：函数曲线专项测试（显式/参数/极坐标的求值、变量联动、采样有效性）。

tests/test_scripting_engine.py
说明：脚本引擎测试（变量定义、控制流 if/for、函数定义与调用、delete 语句）。

tests/test_macro_system.py
说明：宏系统测试（录制 add/move、回放、撤销）。

tests/test_save_load.py
说明：保存/加载 `.wgeo` 文件端到端测试（含变量和几何对象）。

tests/test_rendering_smoke.py
说明：渲染冒烟测试（确保常见对象可离屏渲染，不抛异常）。

tests/test_tools.py
说明：工具交互测试（点工具/线段工具/圆工具/框选工具/选择工具）。

tests/test_transforms.py
说明：变换系统测试（平移/旋转/缩放/反射/迭代点）。

tests/test_variable_binding.py
说明：变量绑定度量值测试（绑定到线段长度、删除对象自动解绑、保存/加载后恢复绑定）。

tests/test_variable_binding_comprehensive.py
说明：变量绑定综合测试（覆盖 UI 到引擎全链路，包括 `VariableSliderPanel`、`VariableWizard`、`Measure`/`RegionMeasure` 的集成）。

tests/test_media_objects.py
说明：媒体对象测试（表格、饼图、柱状图的基础创建和 `dump`/`build`）。

tests/test_overlay_visible.py
说明：工具覆盖层（`draw_overlay`）可见性回归测试（防止画圆预览/框选框/选择工具参考线消失）。

tests/test_sqrt_rendering.py
说明：数学排版根号渲染测试（验证 `sqrt(x)` 和 `\sqrt{x}` 的解析与绘制差异）。

tests/test_new_features.py
说明：新特性综合测试（隐函数/橡皮擦/图表/图片内嵌/汉化/线程安全）。

tests/test_settings.py（★ 新增）
说明：偏好设置全链路测试（58 项）。覆盖 `SettingsStore` 基本操作、`DEFAULTS` 类型与范围合法性、序列化往返、字体构建安全性（`pointSize > 0`）、`theme.refresh_fonts` 不崩溃、`Document.save/load` 中 `settings.json` 持久化、边界值与非法输入防御。