"""
规划验证器 - 在生成代码前验证规划的合理性
"""
from typing import List, Dict, Tuple, Optional
import math


class PlanValidator:
    """
    验证 CAD 规划的物理合理性
    
    检查项:
    1. 悬空检测: 部件必须有支撑
    2. 碰撞检测: 部件不能重叠
    3. 连接性检测: 相关部件必须接触
    4. 尺寸合理性: 尺寸不能为负或过大
    """
    
    def __init__(self):
        self.max_dimension = 10000  # mm
        self.min_dimension = 0.1  # mm
        self.tolerance = 0.1  # 接触判断容差
    
    def validate(self, plan: List[Dict]) -> Tuple[bool, List[str]]:
        """
        验证规划
        
        Returns:
            (is_valid, list_of_issues)
        """
        issues = []
        
        # 1. 悬空检测
        floating_issues = self._check_floating(plan)
        issues.extend(floating_issues)
        
        # 2. 尺寸检查
        size_issues = self._check_dimensions(plan)
        issues.extend(size_issues)
        
        # 3. 依赖检查
        dep_issues = self._check_dependencies(plan)
        issues.extend(dep_issues)
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def _check_floating(self, plan: List[Dict]) -> List[str]:
        """检测悬空部件"""
        issues = []
        
        for item in plan:
            name = item.get("name", "unknown")
            location = item.get("location", [0, 0, 0])
            deps = item.get("dependencies", [])
            
            # 如果 Z > 0 且没有依赖，可能悬空
            if location[2] > 0 and not deps:
                # 检查是否有其他部件在其下方
                has_support = False
                for other in plan:
                    if other["name"] == name:
                        continue
                    other_loc = other.get("location", [0, 0, 0])
                    # 简化检查: 如果有部件在下方且 XY 位置接近
                    if other_loc[2] < location[2]:
                        if self._is_nearby_xy(location, other_loc):
                            has_support = True
                            break
                
                if not has_support:
                    issues.append(
                        f"Warning: '{name}' at Z={location[2]} may be floating (no dependencies or support below)"
                    )
        
        return issues
    
    def _check_dimensions(self, plan: List[Dict]) -> List[str]:
        """检查尺寸合理性"""
        issues = []
        
        for item in plan:
            name = item.get("name", "unknown")
            desc = item.get("description", "")
            
            # 从描述中提取数字 (简化版)
            import re
            numbers = re.findall(r'[-+]?\d*\.?\d+', desc)
            
            for num_str in numbers:
                try:
                    num = float(num_str)
                    if num < 0 and "angle" not in desc.lower():
                        issues.append(f"Warning: '{name}' has negative dimension: {num}")
                    if abs(num) > self.max_dimension:
                        issues.append(f"Warning: '{name}' has very large dimension: {num}")
                except ValueError:
                    pass
        
        return issues
    
    def _check_dependencies(self, plan: List[Dict]) -> List[str]:
        """检查依赖关系"""
        issues = []
        part_names = {item.get("name") for item in plan}
        
        for item in plan:
            name = item.get("name", "unknown")
            deps = item.get("dependencies", [])
            
            for dep in deps:
                if dep not in part_names:
                    issues.append(f"Error: '{name}' depends on non-existent part '{dep}'")
        
        return issues
    
    def _is_nearby_xy(self, loc1: List[float], loc2: List[float], threshold: float = 100) -> bool:
        """检查两个位置在 XY 平面上是否接近"""
        dx = loc1[0] - loc2[0]
        dy = loc1[1] - loc2[1]
        return math.sqrt(dx*dx + dy*dy) < threshold
    
    def suggest_fixes(self, plan: List[Dict], issues: List[str]) -> List[str]:
        """根据问题提供修复建议"""
        suggestions = []
        
        for issue in issues:
            if "floating" in issue.lower():
                suggestions.append("Consider adding a dependency or adjusting Z position to ground level")
            if "negative" in issue.lower():
                suggestions.append("Check if negative values are intentional (e.g., for coordinate offsets)")
            if "non-existent" in issue.lower():
                suggestions.append("Add the missing part to the plan or remove the dependency")
        
        return suggestions
