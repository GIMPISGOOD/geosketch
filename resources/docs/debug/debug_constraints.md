# 修复总览(2026/10/3)

---

## P0 级别（共 4 个）

| # | 问题 | 修改文件 | 修复方式 |
|---|---|---|---|
| 1 | `PointOnObject` 雅可比方向错误 | `constraints/base.py` | 切线方向投影 |
| 2 | `_numeric_chain_fallback` 未重算父对象链 | `constraints/base.py` | 新增 `_recompute_subtree()` |
| 3 | 删除对象后约束悬挂引用 | `core/document.py` | `_constraint_touches_doomed` 三层检查 |
| 5 | `_numeric_fallback` 未重算父对象链 | `constraints/chain_rule.py` | 同上 |

## P1 级别（共 3 个）

| # | 问题 | 修改文件 | 修复方式 |
|---|---|---|---|
| 6 | 9 个约束缺解析雅可比 | 6 个约束类型文件 | 手写推导并补全 |
| 7 | BFS 算法 O(n²k) | `constraints/graph.py` | deque + 邻接表 |
| 8 | 递归求解语义不精确 | `core/document.py` | merged_pinned + 完整重算 |

## P2 级别（共 2 个）

| # | 问题 | 修改文件 | 修复方式 |
|---|---|---|---|
| 11 | 约束参考线 | `constraints/ui/overlay.py` | **撤回**（用户指出 `ui/canvas.py` 已原生实现） |
| 13 | 过约束检测简陋 | `core/document.py` | 逐约束残差 + 自适应阈值 + 完整回滚 |

## P3 级别（共 4 个）

| # | 问题 | 修改文件 | 修复方式 |
|---|---|---|---|
| 10 | 约束序列化冗余 | `core/document.py` | 删除 `constraints.json` 写入 |
| 14 | `select_ext.py` 死代码 | `constraints/select_ext.py` | 改为空壳 |
| 15 | `types/__init__.py` 导入被注释 | `constraints/types/__init__.py` | 添加文档说明 |
| 16 | 测试调用废弃接口 | `tests/test_solver.py` | 删除 `patch_document()` |

## 预览参考线重画（1 个）

| 问题 | 修改文件 | 最终方案 |
|---|---|---|
| 创建工具预览丑 | `constraints/ui/tools.py` | 实线 + `theme.ACCENT` / `theme.PREVIEW`，线宽 2，与线段渲染器同款 |
