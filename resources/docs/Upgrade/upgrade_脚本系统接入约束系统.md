# Upgrade: 脚本系统接入约束系统

## 1. 更新概述
本次更新打通了 **脚本引擎 (Scripting Engine)** 与 **几何约束求解器 (Constraint Solver)** 之间的底层链路。用户现在可以直接通过脚本代码定义复杂的参数化几何约束模型，而无需手动在 UI 上逐个点击。
更重要的是，本次更新引入了**约束事务管理机制**，确保了脚本执行过程中的原子性：无论是脚本运行报错，还是设置了 `__keep = false`，系统都能完美回滚已创建的约束并恢复几何点坐标，彻底杜绝了“幽灵约束”和图形状态损坏的问题。

## 2. 核心新增功能

### 2.1 脚本全局约束 API
在脚本环境中注入了一系列 `constraint_*` 函数及其中文别名，支持通过代码创建所有主流几何约束：
- **点级约束**：`constraint_fixed` (固定), `constraint_distance` (距离), `constraint_angle` (角度), `constraint_horizontal` (水平), `constraint_vertical` (竖直), `constraint_collinear` (共线)。
- **线级约束**：`constraint_parallel` (平行), `constraint_perpendicular` (垂直)。
- **对象级约束**：`constraint_concentric` (同心), `constraint_equal_radius` (等半径), `constraint_tangent` (相切，支持圆-圆、线-圆，支持内外切模式)。
- **控制 API**：`constraint_solve` (手动触发求解), `remove_constraint` / `delete_constraint` (删除约束)。

### 2.2 智能参数解析引擎
脚本约束函数具备与 UI 工具同等的“智能拾取”能力。传入参数时，无需手动拆解对象：
- 传入**线段/直线**对象，自动提取两个端点参与约束。
- 传入**圆**对象，自动提取圆心和圆周点。
- 支持直接传入**对象名字符串**（如 `"S1"`），引擎会自动在作用域和文档中查找对应对象。

### 2.3 约束事务与完美回滚 (核心亮点)
- **`__keep = false` 清理**：当脚本成功执行完毕但标记为不保留时，系统不仅会删除脚本创建的几何对象，还会**自动移除脚本创建的所有约束**，并将被约束求解器移动过的点**恢复到初始坐标**。
- **运行时报错回滚**：如果脚本在创建约束后发生语法或运行时错误，系统会触发 `_rollback()`，安全撤销所有已添加的约束并恢复点坐标，保证文档状态干净。
- **过约束静默处理**：脚本批量创建约束时，如果发生过约束冲突，不再弹出阻塞界面的 `QMessageBox`，而是将错误信息记录到 `Document.last_constraint_error` 并抛出 `ScriptError`，由脚本引擎统一捕获处理。

### 2.4 约束删除支持
扩展了 `delete` 语句和 `delete all` 逻辑：
- 支持 `delete c`（`c` 为约束对象句柄）。
- 支持 `remove_constraint("c12")`（通过约束 ID 字符串删除）。
- `delete all` 和 `delete created` 现在会同步清理相关的脚本约束。

## 3. 底层架构修改

| 模块/文件 | 修改内容说明 |
| :--- | :--- |
| `core/document.py` | `add_constraint` 新增 `silent=False` 参数。支持静默模式，避免脚本批量执行时弹窗；新增 `last_constraint_error` 字段存储过约束详细信息。 |
| `core/scripting/constraint_factory.py` | **(新增)** 约束工厂类，封装了对象解析、点提取、表达式转换及调用 `doc.add_constraint` 的完整逻辑。 |
| `core/scripting/interpreter.py` | 1. 新增 `created_constraints` 列表跟踪脚本创建的约束。<br>2. 新增 `_point_backup` 机制，在首次创建约束前备份所有自由点和吸附点坐标。<br>3. 重构 `_finalize_success` 和 `_rollback`，实现约束与坐标的联动清理/恢复。<br>4. 修复 Pylance 对动态类型属性赋值的警告（改用 `setattr`）。 |
| `core/scripting/functions.py` | 在 `build_global_env` 中批量注入约束 API 及中文别名。 |
| `core/scripting/object_destructor.py` | 1. 修复 `delete created` 中的变量名拼写错误 (`obj` -> `o`)。<br>2. 扩展 `delete_object` 识别约束对象并调用 `doc.remove_constraint`。<br>3. 扩展 `delete_all` 同步清理脚本约束。 |
| `ui/script_editor.py` | 在代码自动补全列表 (`FUNCS`) 中加入所有 `constraint_*` 函数，提升编写体验。 |

## 4. 脚本使用示例

### 示例 1：参数化正方形构建
```text
__keep = true

# 1. 创建基础点与线段
A = point(0, 0)
B = point(5, 2)
C = point(3, 6)
D = point(-2, 4)

S1 = segment(A, B)
S2 = segment(B, C)
S3 = segment(C, D)
S4 = segment(D, A)

# 2. 添加等长约束（传入线段对象，自动提取端点）
constraint_distance(S1, 5)
constraint_distance(S2, 5)
constraint_distance(S3, 5)
constraint_distance(S4, 5)

# 3. 添加垂直约束（传入四个点）
constraint_perpendicular(A, B, B, C)
constraint_perpendicular(B, C, C, D)

# 4. 触发求解
constraint_solve()