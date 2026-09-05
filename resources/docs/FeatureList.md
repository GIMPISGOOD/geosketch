### GeoSketch 几何画板 —— 项目整体概述

GeoSketch 是一个基于 PySide6 的动态几何软件，支持交互式几何构造、代数约束求解、函数曲线绘制、动画录制与回放、内置脚本编程、变换与迭代、多种媒体对象（图表/表格/图片/按钮）及完整的撤销/重做、序列化、宏录制、主题定制、课件导出等功能。项目采用插件化架构，核心模块与扩展包分离，易于维护和扩展。

---

### 文件结构与简要描述（按目录分组）

#### 根目录
- `main.py` – 应用入口：初始化 QApplication、加载约束与动画扩展、创建主窗口并启动事件循环。

#### animation/ —— 动画系统
- `__init__.py` – 动画包入口：注入动画菜单、时间轴面板，初始化控制器并加载序列化补丁。
- `base.py` – 定义动画轨道基类 `AnimationTrack` 与轨道注册表，规范轨道序列化接口。
- `clip.py` – 动画片段容器，管理轨道列表、循环/速度/时长，并提供预设关键帧模板。
- `controller.py` – 动画控制器（QTimer驱动），负责播放/暂停/停止、逐帧求值并更新文档。
- `keyframe.py` – 关键帧数据结构及多种插值器（线性/缓入缓出/弹跳/弹性等）。
- `recorder.py` – 动画录制器，监听变量/对象属性变化，自动生成关键帧序列。
- `serialization.py` – （已废弃）动画序列化补丁，现由 Document 原生处理。
- `tracks.py` – 具体轨道类型：变量轨道、路径轨道（吸附点）、属性轨道。
- `ui/__init__.py` – 动画 UI 包入口。
- `ui/timeline.py` – 时间轴面板（QDockWidget），含播放控制、滑杆、轨道列表、录制按钮。
- `ui/track_editor.py` – 轨道编辑对话框（添加/编辑轨道关键帧）。

#### constraints/ —— 几何约束求解器
- `__init__.py` – 约束包入口：注册所有约束类型、工具图标，并注入约束菜单。
- `base.py` – 约束基类 `GeometricConstraint` 与注册表，统一雅可比计算（支持解析/数值/链式法则）。
- `chain_rule.py` – 从动点（如吸附点、交点）坐标对自由点坐标的解析偏导数。
- `document_ext.py` – 空壳，约束逻辑已原生集成到 Document。
- `graph.py` – 约束依赖图，用于寻找受触发点影响的局部连通分量。
- `select_ext.py` – 对 SelectTool 的补丁（拖动时触发约束求解），已废弃。
- `serialization.py` – 空壳，序列化已集成到 Document。
- `solver.py` – Levenberg-Marquardt 非线性最小二乘求解器（NumPy 向量化）。
- `types/__init__.py` – 约束类型包入口。
- `types/angle.py` – 角度约束（三点间夹角等于表达式）。
- `types/circle_constraints.py` – 圆相关约束：同心、等半径、圆-圆/线-圆相切。
- `types/collinear.py` – 三点共线约束。
- `types/distance.py` – 两点距离约束（表达式驱动）。
- `types/fixed.py` – 固定点约束（锁定坐标）。
- `types/horizontal.py` – 水平约束（两点的 Y 坐标相等）。
- `types/parallel.py` – 两直线/线段平行约束。
- `types/perpendicular.py` – 两直线/线段垂直约束。
- `types/tangent.py` – 圆-圆/圆-直线相切约束（含解析雅可比）。
- `types/vertical.py` – 竖直约束（两点的 X 坐标相等）。
- `ui/overlay.py` – 在画布上绘制约束参考线（虚线+端点圆）。
- `ui/tools.py` – 约束创建工具集（距离/固定/水平/竖直/角度/平行/垂直/共线/同心/等半径/相切等）。

#### core/ —— 核心模块
- `__init__.py` – core 包入口。
- `ai_service.py` – AI 服务（本地 GGUF + 远程 API），支持引用计数与延迟卸载。
- `document.py` – 文档类 `Document`：管理所有几何对象、约束、动画、撤销/重做、序列化（集成约束与动画）。
- `macro.py` – 宏录制与回放系统（命令包括 add/move/delete/set_var/clear）。
- `registry.py` – 三个全局注册表：几何对象、渲染器、工具（含面板分类）。
- `settings.py` – 偏好设置存储类 `SettingsStore`，默认值硬编码，支持批处理与信号。
- `variables.py` – 变量系统：变量存储、表达式安全求值、变量绑定到几何度量、模板渲染。
- `scripting/__init__.py` – 脚本系统入口：解析、执行、库管理。
- `scripting/ast_nodes.py` – 脚本 AST 节点定义（程序、函数、控制流、表达式等）。
- `scripting/errors.py` – 脚本错误类型（带行号）。
- `scripting/functions.py` – 脚本内置函数（数学函数、几何构造工厂函数等）。
- `scripting/interpreter.py` – 脚本解释器（作用域、调用栈、内置变量/函数）。
- `scripting/object_factory.py` – 几何对象工厂（用于脚本中创建点/线/圆/多边形/变换对象等）。
- `scripting/object_destructor.py` – 脚本对象销毁器（删除对象/全部/脚本创建对象）。
- `scripting/parser.py` – 脚本语法分析器（支持中文关键字、循环、函数）。
- `scripting/scope.py` – 作用域与用户函数对象。
- `scripting/tokens.py` – 脚本词法分析器。
- `scripting/macro_converter.py` – 宏→脚本转换引擎（注册表模式，支持多种几何对象）。
- `scripting/libraries/__init__.py` – 内置库入口（math/geo/draw/doc）。
- `scripting/libraries/math_lib.py` – math 库（数学函数、常量）。
- `scripting/libraries/geo_lib.py` – geo 库（距离/长度/斜率/面积/周长等）。
- `scripting/libraries/draw_lib.py` – draw 库（绘图函数别名）。
- `scripting/libraries/doc_lib.py` – doc 库（删除/查找对象）。

#### geo/ —— 几何对象库
- `__init__.py` – 自动导入子模块。
- `base.py` – 几何对象基类 `GeoObject`（id、parents/children、可见性、序列化接口）。
- `points.py` – 点对象：`FreePoint`（自由点）、`PointOnObject`（吸附点），及磁吸查询函数。
- `segments.py` – 线段 `Segment`，带点距/投影/长度。
- `circles.py` – 圆 `Circle`（圆心+圆周点）。
- `constraints.py` – 表达式约束对象：`ExprSegment`、`ExprAngle`、`ExprCircle`、`ExprPoint`（变量驱动）。
- `division.py` – 等分点 `DivisionPoint`（按比例分两点）。
- `intersects.py` – 交点 `IntersectPoint`，支持多种图形组合求交（线段/圆/多边形等）。
- `directed_line.py` – 方向直线基类（垂线/平行线/角平分线等继承）。
- `function_curve.py` – 函数曲线 `FunctionCurve`（显函数/参数/极坐标），带缓存与异步采样。
- `function_sampler.py` – 函数曲线后台采样线程（去重任务、双缓冲）。
- `implicit_curve.py` – 隐函数曲线 `ImplicitCurve`（F(x,y)=0），使用 Marching Squares。
- `implicit_sampler.py` – 隐函数后台采样线程（Marching Squares 实现）。
- `chain_fill.py` – 链式填充区域 `ChainFill`（由点+曲线围成），支持弧段选择与填充样式。
- `ink.py` – 墨迹笔画 `InkStroke` 与橡皮擦 `InkEraser`。
- `curves.py` – 参数曲线基类 `ParamCurve`（椭圆/贝塞尔继承）。

#### plugins/ —— 插件扩展（构造/度量/变换/插入工具）
- `__init__.py` – 自动导入所有插件子模块。
- `angle_divide_tool.py` – n 等分角线工具与几何对象。
- `angle_tool.py` – 角度测量工具与 `AngleMeasure` 对象。
- `bezier_tool.py` – 三次贝塞尔曲线工具。
- `bisector_tool.py` – 角平分线工具。
- `construction_tools.py` – 过三点圆、中垂线、内心、重心工具及几何对象。
- `divide_tool.py` – N 等分线段工具（浮动选择器）。
- `ellipse_tool.py` – 椭圆工具。
- `expr_geo_tools.py` – 表达式圆/表达式点对话框。
- `expr_tools.py` – 表达式线段/角度工具（浮层输入表达式）。
- `line_tool.py` – 无限长直线工具。
- `measure_tools.py` – 度量工具集（长度/距离/角度/比值/面积/周长/半径/直径/斜率/坐标/任意区域）。
- `midpoint_tool.py` – 中点工具。
- `parallel_tool.py` – 平行线工具。
- `perp_tool.py` – 垂线工具。
- `polygon.py` – 正多边形及顶点对象。
- `ratio_tool.py` – 比例度量（显示最简分数）。
- `ray_tool.py` – 射线工具。
- `text_tool.py` – 文本标注工具。
- `trace_tool.py` – 轨迹追踪插件（Catmull-Rom 样条）。

#### media/ —— 媒体对象（图表/表格/图片/按钮）
- `__init__.py` – 自动导入子模块。
- `base.py` – 媒体对象基类 `MediaObject`（位置/尺寸/旋转/缩放/编辑按钮）。
- `chart_obj.py` – 饼图/柱状图/折线图/环形图对象（数据支持表达式）。
- `image_obj.py` – 图片对象（支持等比缩放与旋转）。
- `table_obj.py` – 表格对象（支持表达式求值）。
- `script_button.py` – 脚本按钮对象（单击执行脚本）。
- `script_button_tool.py` – 插入脚本按钮工具。
- `script_button_wizard.py` – 脚本按钮创建/编辑向导（简化操作）。
- `insert_tools.py` – 插入图片/表格/饼图/柱状图/折线图/环形图工具。
- `pie_wizard.py` – 图表数据向导（设置标签/数值/颜色）。
- `table_wizard.py` – 表格插入向导（设置行列/单元格内容/颜色）。

#### transforms/ —— 变换系统
- `__init__.py` – 自动导入子模块。
- `base.py` – 变换数学基础（矩阵运算、仿射求解、表达式求值）。
- `objects.py` – 变换对象：`TransformDriver`（驱动器）、`TransformPoint`、`CircleAxisPoint`、`InvertedCircle`（反演圆）、`IterPoint`（迭代点）。
- `apply.py` – 将变换应用到选中对象并支持深度迭代。
- `tools.py` – 变换工具集（平移/旋转/缩放/反射/仿射/反演/迭代点列）。

#### tests/ —— 单元测试
- `conftest.py` – pytest 配置（离屏 Qt 环境、fixtures）。
- `test_attached_point.py` – 吸附点功能测试。
- `test_constraint_drag.py` – 约束拖动求解回归测试。
- `test_core_document.py` – Document 核心功能（增删/撤销/复制粘贴）。
- `test_core_variables.py` – 变量系统测试。
- `test_function_curve.py` – 函数曲线绘制与采样测试。
- `test_geometry_objects.py` – 基础几何对象测试。
- `test_intersect_derivatives.py` – 交点偏导数验证。
- `test_macro_system.py` – 宏录制/回放测试。
- `test_media_objects.py` – 媒体对象测试。
- `test_new_features.py` – 新特性（隐函数/橡皮擦/图表/图片嵌入/国际化）测试。
- `test_overlay_visible.py` – 工具覆盖层渲染可见性测试。
- `test_rendering_smoke.py` – 离屏渲染冒烟测试。
- `test_save_load.py` – 文档保存/加载测试。
- `test_scripting_engine.py` – 脚本引擎测试。
- `test_settings.py` – 偏好设置全链路测试。
- `test_solver.py` – 约束求解器集成测试。
- `test_sqrt_rendering.py` – 根号渲染诊断测试。
- `test_tools.py` – 基础工具（点/线段/圆/框选/选择）测试。
- `test_trace_plugin.py` – 轨迹插件测试。
- `test_transforms.py` – 变换系统测试。
- `test_variable_binding.py` – 变量绑定测试。
- `test_variable_binding_comprehensive.py` – 变量绑定综合测试。

#### tools/ —— 基础绘图工具
- `__init__.py` – 自动导入。
- `base.py` – 工具基类 `Tool`，及 `point_or_snap` 辅助函数（磁吸建点）。
- `box_select.py` – 框选工具。
- `chain_fill_tool.py` – 自由填充工具（点+曲线围成区域）。
- `circle_tool.py` – 圆工具。
- `fixed_angle_tool.py` – 定角工具（输入角度值）。
- `ink_tool.py` – 墨迹工具（钢笔/荧光笔/铅笔/橡皮擦）。
- `intersect_tool.py` – 交点工具（自动求两图形所有交点）。
- `length_seg_tool.py` – 定长线段工具（输入长度值）。
- `point_tool.py` – 点工具。
- `segment_tool.py` – 线段工具。
- `select.py` – 选择/拖动/缩放工具（含智能参考线和对齐）。

#### ui/ —— 用户界面组件
- `__init__.py` – UI 包入口。
- `about_dialog.py` – 关于对话框（带弹跳图标动画）。
- `anim_helpers.py` – UI 动效工具函数（滑动/淡入淡出）。
- `canvas.py` – 画布控件 `Canvas`（渲染/交互/手势/惯性/缩放/工具管理）。
- `canvas_menu.py` – 画布右键上下文菜单（编辑/隐藏/重命名/复制/粘贴/绑定度量等）。
- `canvas_render.py` – 画布渲染函数（背景/网格/坐标轴/出版样式/EGG彩蛋）。
- `canvas_snow.py` – 下雪特效（彩蛋）。
- `export_courseware.py` – 导出课件包（含向导、HTML/JSXGraph、启动器）。
- `export_wizard.py` – 导出图像向导（预览/格式/分辨率）。
- `formula_editor.py` – 函数/隐函数编辑器（虚拟键盘、实时预览、AI补全）。
- `function_panel.py` – 函数编辑器停靠面板（分类显示曲线，可编辑/删除/隐藏）。
- `help_gallery.py` – 示例项目库浏览视图（卡片式，带缩略图）。
- `icons.py` – 图标库（基于 qtawesome，支持多候选图标名）。
- `macro_dialog.py` – 宏管理器对话框（回放/重命名/删除/转为脚本）。
- `main_window.py` – 主窗口（菜单栏/状态栏/工具栏/停靠窗口/宏/自动保存）。
- `property_panel.py` – 统一对象属性面板（显示/编辑选定对象的属性）。
- `script_editor.py` – 脚本编辑器（含语法高亮、AI补全/生成、日志面板）。
- `script_library_manager.py` – 脚本库管理器（创建/编辑/删除库）。
- `settings_dialog.py` – 偏好设置对话框（外观/画布/动效/交互/工作流/AI）。
- `theme.py` – 多主题系统（纸白/墨夜/蓝图/黑板，动态切换）。
- `theme_editor.py` – 自定义主题编辑器（可视化调整颜色并保存/导入/导出）。
- `tool_rail.py` – 左侧悬浮工具栏（rail工具）。
- `variable_widgets.py` – 变量滑杆面板、变量创建向导、变量绑定对话框。
- `zoom_bar.py` – 右下角缩放控件（放大/缩小/重置）。
- `math/__init__.py` – 数学排版对外接口（绘制/度量，带缓存）。
- `math/font.py` – 数学字体加载（STIX Two Math 回退）。
- `math/layout.py` – 数学布局引擎（测量与绘制 AST，支持分数/根号/上下标）。
- `math/parser.py` – 数学表达式解析器（支持 LaTeX 命令、希腊字母、符号）。

#### resources/scripts/ —— 额外脚本（非核心）
- `chat.py` – 独立本地 LLM 终端聊天工具（Rich 美化，支持多模型）。
- `test_ai.py` – 简单测试 AI 模型加载。

---

### 总体架构特点
- **模块化**：几何对象、约束、动画、变换、媒体、工具均独立注册，互不耦合。
- **可扩展**：新增对象或工具只需在相应目录创建文件并使用装饰器注册。
- **数据驱动**：Document 持有所有数据，支持撤销/重做、序列化（ZIP 格式）。
- **用户交互**：Canvas 统一管理工具、手势、惯性、磁吸、渲染。
- **脚本系统**：完整的 DSL 解释器，支持函数、循环、库导入，可控制几何构造与变量。
- **AI 集成**：本地 GGUF 或远程 API，用于代码补全和生成。