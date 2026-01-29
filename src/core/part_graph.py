"""
部件依赖图 - 管理部件之间的依赖关系
用于可控生成：当修改一个部件时，自动识别需要重新生成的依赖部件
"""
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Part:
    """部件节点"""
    name: str
    description: str = ""
    location: List[float] = field(default_factory=lambda: [0, 0, 0])
    operation: str = "extrude"
    code: str = ""
    parameters: Dict[str, float] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)  # 依赖此部件的其他部件
    is_dirty: bool = False  # 是否需要重新生成
    is_locked: bool = False  # 是否被用户锁定 (不允许 AI 修改)
    
    def get_safe_name(self) -> str:
        return self.name.replace(" ", "_").replace("-", "_")


class PartGraph:
    """
    部件依赖图
    
    功能:
    1. 管理部件之间的依赖关系
    2. 识别受影响的部件 (当一个部件改变时)
    3. 提供拓扑排序用于按序生成
    4. 支持部件锁定 (保护用户手动编辑)
    """
    
    def __init__(self):
        self.parts: Dict[str, Part] = {}
        self._adj_list: Dict[str, Set[str]] = defaultdict(set)  # 依赖关系: A -> B 表示 A 依赖 B
        self._rev_adj_list: Dict[str, Set[str]] = defaultdict(set)  # 反向依赖: B -> A 表示 A 依赖 B
    
    def add_part(self, part: Part):
        """添加部件"""
        self.parts[part.name] = part
        
        # 建立依赖关系
        for dep in part.dependencies:
            self._adj_list[part.name].add(dep)
            self._rev_adj_list[dep].add(part.name)
            
            # 更新被依赖部件的 dependents 列表
            if dep in self.parts:
                self.parts[dep].dependents.append(part.name)
    
    def remove_part(self, name: str):
        """移除部件"""
        if name not in self.parts:
            return
        
        part = self.parts[name]
        
        # 清理依赖关系
        for dep in part.dependencies:
            self._rev_adj_list[dep].discard(name)
            if dep in self.parts:
                if name in self.parts[dep].dependents:
                    self.parts[dep].dependents.remove(name)
        
        # 清理被依赖关系
        for dependent in part.dependents:
            self._adj_list[dependent].discard(name)
            if dependent in self.parts:
                if name in self.parts[dependent].dependencies:
                    self.parts[dependent].dependencies.remove(name)
        
        del self._adj_list[name]
        del self._rev_adj_list[name]
        del self.parts[name]
    
    def update_part(self, name: str, **kwargs):
        """更新部件属性"""
        if name not in self.parts:
            return
        
        part = self.parts[name]
        
        for key, value in kwargs.items():
            if hasattr(part, key):
                setattr(part, key, value)
        
        # 标记为脏
        part.is_dirty = True
    
    def get_part(self, name: str) -> Optional[Part]:
        """获取部件"""
        return self.parts.get(name)
    
    def mark_dirty(self, name: str):
        """标记部件为脏 (需要重新生成)"""
        if name in self.parts:
            self.parts[name].is_dirty = True
    
    def mark_clean(self, name: str):
        """标记部件为干净"""
        if name in self.parts:
            self.parts[name].is_dirty = False
    
    def lock_part(self, name: str):
        """锁定部件 (保护不被 AI 修改)"""
        if name in self.parts:
            self.parts[name].is_locked = True
    
    def unlock_part(self, name: str):
        """解锁部件"""
        if name in self.parts:
            self.parts[name].is_locked = False
    
    def get_affected_parts(self, name: str) -> List[str]:
        """
        获取受影响的部件列表
        当部件 `name` 改变时，所有依赖它的部件都会受影响
        """
        affected = []
        visited = set()
        
        def dfs(n: str):
            if n in visited:
                return
            visited.add(n)
            
            for dependent in self._rev_adj_list[n]:
                affected.append(dependent)
                dfs(dependent)
        
        dfs(name)
        return affected
    
    def get_dependencies(self, name: str) -> List[str]:
        """获取部件的所有依赖 (递归)"""
        deps = []
        visited = set()
        
        def dfs(n: str):
            if n in visited:
                return
            visited.add(n)
            
            for dep in self._adj_list[n]:
                deps.append(dep)
                dfs(dep)
        
        dfs(name)
        return deps
    
    def topological_sort(self) -> List[str]:
        """
        拓扑排序
        返回按依赖顺序排列的部件名列表
        """
        in_degree = {name: 0 for name in self.parts}
        
        for name in self.parts:
            for dep in self._adj_list[name]:
                if dep in in_degree:
                    in_degree[name] += 1
        
        # 从入度为 0 的节点开始
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for dependent in self._rev_adj_list[node]:
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        return result
    
    def get_dirty_parts(self) -> List[str]:
        """获取所有需要重新生成的部件"""
        return [name for name, part in self.parts.items() if part.is_dirty]
    
    def get_unlocked_parts(self) -> List[str]:
        """获取所有未锁定的部件"""
        return [name for name, part in self.parts.items() if not part.is_locked]
    
    def from_plan(self, plan: List[Dict]) -> 'PartGraph':
        """从规划结果构建图"""
        self.parts.clear()
        self._adj_list.clear()
        self._rev_adj_list.clear()
        
        for item in plan:
            part = Part(
                name=item.get("name", "part"),
                description=item.get("description", ""),
                location=item.get("location", [0, 0, 0]),
                operation=item.get("operation", "extrude"),
                dependencies=item.get("dependencies", [])
            )
            self.add_part(part)
        
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典 (用于序列化)"""
        return {
            "parts": {
                name: {
                    "name": p.name,
                    "description": p.description,
                    "location": p.location,
                    "operation": p.operation,
                    "dependencies": p.dependencies,
                    "is_locked": p.is_locked,
                }
                for name, p in self.parts.items()
            }
        }
    
    def validate(self) -> List[str]:
        """验证图的一致性，返回问题列表"""
        issues = []
        
        # 检查循环依赖
        for name in self.parts:
            deps = self.get_dependencies(name)
            if name in deps:
                issues.append(f"Circular dependency detected for {name}")
        
        # 检查悬空依赖
        for name, part in self.parts.items():
            for dep in part.dependencies:
                if dep not in self.parts:
                    issues.append(f"{name} depends on non-existent part {dep}")
        
        return issues
