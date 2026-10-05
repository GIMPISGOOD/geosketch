# 修复总览(2026/10/5)

## P0 级别（共 2 个）

| # | 问题 | 修改文件 | 修复方式 |
| 1 | `_rollback` 未清理约束且未恢复点坐标 | core/scripting/interpreter.py | 在 `_rollback` 中按序调用 `_remove_created_constraints()` 与 `_restore_point_backup()`，确保事务原子性 |
| 2 | `delete created` 列表推导式中变量名 `obj` 未定义 | core/scripting/object_destructor.py | 将推导式内部判断条件中的 `obj` 修正为循环变量 `o` |

## P1 级别（共 1 个）

| # | 问题 | 修改文件 | 修复方式 |
| 3 | `solve_constraints` 递归调用返回值被丢弃，深层求解失败被静默吞没 | core/document.py | 接收递归返回值 `sub_success`，与当前层 `success` 做逻辑与合并 |

## P2 级别（共 1 个）

| # | 问题 | 修改文件 | 修复方式 |
| 4 | `ConstraintFactory.remove` 对约束句柄不在列表时跳过字符串回退分支 | core/scripting/constraint_factory.py | 简化对象句柄赋值逻辑，将"是否在文档中"的校验统一后置 |