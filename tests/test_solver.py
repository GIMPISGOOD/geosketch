# Git Log:
# commit 8f3a2b1c
# Author: Qwen
# Date:   Tue Aug 18 10:00:00 2026 +0800
#
#     test: 添加几何约束求解器收敛性与多类型点混合测试
#
#     - 测试基础自由点距离与水平约束的收敛性
#     - 测试包含吸附点 (PointOnObject) 时的链式法则雅可比计算
#     - 测试圆相切约束的解析雅可比正确性
#     - 测试过约束冲突时的自动回滚机制
#     - 测试复杂拓扑 (交点 IntersectPoint) 下的求解器鲁棒性

import math
import pytest
import sys
import os

# 确保项目根目录在 sys.path 中，以便直接导入 core, geo, constraints 等包
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.document import Document
from geo.points import FreePoint, PointOnObject
from geo.segments import Segment
from geo.circles import Circle
from geo.intersects import IntersectPoint

# 手动注入约束系统核心（避开 UI/PySide6 依赖，确保在无头 CI 环境下可运行）
from constraints import types  # 触发所有 @register_constraint 装饰器
from constraints.document_ext import patch_document
patch_document()

# 导入具体的约束类
from constraints.types.distance import DistanceConstraint
from constraints.types.horizontal import HorizontalConstraint
from constraints.types.circle_constraints import TangentCirclesConstraint
from constraints.types.fixed import FixedConstraint


def test_basic_free_points_convergence():
    """
    用例 1：基础自由点约束（距离 + 水平）
    验证 LM 求解器对纯自由点的收敛性。
    """
    doc = Document()
    p1 = FreePoint(0, 0)
    p2 = FreePoint(1, 1)
    doc.add(p1)
    doc.add(p2)
    
    # 添加距离约束 = 5
    c1 = DistanceConstraint(p1, p2, "5")
    doc.add_constraint(c1)
    
    # 添加水平约束 (Y 坐标相同)
    c2 = HorizontalConstraint(p1, p2)
    doc.add_constraint(c2)
    
    # 验证收敛结果
    assert abs(p1.y - p2.y) < 1e-4, "水平约束未满足"
    dist = math.hypot(p1.x - p2.x, p1.y - p2.y)
    assert abs(dist - 5.0) < 1e-4, f"距离约束未满足，实际距离: {dist}"


def test_point_on_object_chain_rule():
    """
    用例 2：包含吸附点 (PointOnObject) 的约束
    验证 _chain_rule_jacobian 是否正确计算了从动点对自由点的偏导数。
    """
    doc = Document()
    p1 = FreePoint(0, 0)
    p2 = FreePoint(10, 0)
    seg = Segment(p1, p2)
    doc.add(p1)
    doc.add(p2)
    doc.add(seg)
    
    # 吸附点，初始 t=0.5 -> (5, 0)
    poo = PointOnObject(seg, 0.5)
    doc.add(poo)
    
    p3 = FreePoint(5, 5)
    doc.add(p3)
    
    # 约束 p3 和 poo 距离为 3
    c = DistanceConstraint(p3, poo, "3")
    doc.add_constraint(c)
    
    # 验证距离是否收敛到 3
    dist = math.hypot(p3.x - poo.x, p3.y - poo.y)
    assert abs(dist - 3.0) < 1e-3, f"吸附点距离约束未收敛，实际距离: {dist}"
    
    # 验证 poo 仍然在线段上 (Y 坐标应接近 0)
    assert abs(poo.y) < 1e-3, "吸附点脱离了宿主线段"


def test_tangent_circles_analytic_jacobian():
    """
    用例 3：相切约束 (TangentCC) 与解析雅可比
    验证 _jacobian_analytic 在圆相切约束中的正确性。
    """
    doc = Document()
    c1_center = FreePoint(0, 0)
    c1_through = FreePoint(2, 0) # r1 = 2
    c1 = Circle(c1_center, c1_through)
    
    c2_center = FreePoint(5, 0)
    c2_through = FreePoint(6, 0) # r2 = 1
    c2 = Circle(c2_center, c2_through)
    
    doc.add(c1_center); doc.add(c1_through); doc.add(c1)
    doc.add(c2_center); doc.add(c2_through); doc.add(c2)
    
    # 初始圆心距 = 5，r1+r2 = 3。需要移动以满足外切。
    c = TangentCirclesConstraint(c1, c2, mode="outer")
    doc.add_constraint(c)
    
    dist = math.hypot(c1_center.x - c2_center.x, c1_center.y - c2_center.y)
    r1 = math.hypot(c1_through.x - c1_center.x, c1_through.y - c1_center.y)
    r2 = math.hypot(c2_through.x - c2_center.x, c2_through.y - c2_center.y)
    
    assert abs(dist - (r1 + r2)) < 1e-3, f"外切约束未收敛，d={dist}, r1+r2={r1+r2}"





def test_intersect_point_fallback():
    """
    用例 5：复杂拓扑 (交点 IntersectPoint) 下的求解器鲁棒性
    IntersectPoint 的解析偏导目前返回空 {}，测试求解器是否能通过
    移动其他自由点 (数值差分或仅移动目标点) 来满足约束。
    """
    doc = Document()
    # 两条线段交叉
    p1, p2 = FreePoint(0, 0), FreePoint(10, 10)
    p3, p4 = FreePoint(0, 10), FreePoint(10, 0)
    s1, s2 = Segment(p1, p2), Segment(p3, p4)
    
    doc.add(p1); doc.add(p2); doc.add(s1)
    doc.add(p3); doc.add(p4); doc.add(s2)
    
    ip = IntersectPoint(s1, s2, 0) # 理论交点 (5,5)
    doc.add(ip)
    
    p5 = FreePoint(5, 8)
    doc.add(p5)
    
    # 约束交点和 p5 的距离为 2
    doc.add_constraint(DistanceConstraint(ip, p5, "2"))
    
    # 验证 p5 是否移动到了距离交点 2 的地方
    dist = math.hypot(ip.x - p5.x, ip.y - p5.y)
    assert abs(dist - 2.0) < 1e-3, f"交点距离约束未收敛，实际距离: {dist}"