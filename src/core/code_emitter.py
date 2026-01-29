"""
代码发射器 - 基于 PartGraph 生成完整的 build123d 代码
支持增量生成和部件选择
"""
from typing import List, Dict, Optional
from src.core.part_graph import PartGraph, Part


class CodeEmitter:
    """
    从 PartGraph 生成 build123d 代码
    
    功能:
    1. 按依赖顺序生成代码
    2. 支持选择性生成 (只生成部分部件)
    3. 支持增量更新 (只重新生成脏部件)
    """
    
    def __init__(self):
        self.indent = "    "
        self.output_dir = "output"
    
    def emit(
        self, 
        graph: PartGraph,
        only_dirty: bool = False,
        selected_parts: List[str] = None
    ) -> str:
        """
        生成完整代码
        
        Args:
            graph: 部件依赖图
            only_dirty: 是否只生成脏部件
            selected_parts: 只生成指定的部件
        
        Returns:
            完整的 build123d Python 代码
        """
        # 获取要生成的部件列表
        parts_to_generate = self._get_parts_to_generate(graph, only_dirty, selected_parts)
        
        if not parts_to_generate:
            return ""
        
        # 按拓扑顺序排序
        sorted_order = graph.topological_sort()
        parts_to_generate = [p for p in sorted_order if p in parts_to_generate]
        
        # 生成代码
        code = self._emit_imports()
        
        for part_name in parts_to_generate:
            part = graph.get_part(part_name)
            if part and part.code:
                code += f"# === {part.name} ===\n"
                code += part.code + "\n\n"
        
        # 组装
        code += self._emit_assembly(parts_to_generate)
        
        # 导出
        code += self._emit_export()
        
        return code
    
    def _get_parts_to_generate(
        self, 
        graph: PartGraph,
        only_dirty: bool,
        selected_parts: List[str]
    ) -> List[str]:
        """获取要生成的部件列表"""
        all_parts = list(graph.parts.keys())
        
        if selected_parts:
            return [p for p in selected_parts if p in all_parts]
        
        if only_dirty:
            return graph.get_dirty_parts()
        
        return all_parts
    
    def _emit_imports(self) -> str:
        """生成导入语句"""
        return """from build123d import *
from math import *

try:
    from build123d import export_stl, export_step
except ImportError:
    pass

"""
    
    def _emit_assembly(self, parts: List[str]) -> str:
        """生成组装代码"""
        if not parts:
            return ""
        
        parts_expr = ", ".join([f"{p.replace(' ', '_').replace('-', '_')}_part.part" for p in parts])
        return f"# === Assembly ===\ncompound = Compound(children=[{parts_expr}])\n\n"
    
    def _emit_export(self) -> str:
        """生成导出代码"""
        return f"""# === Export ===
import os
os.makedirs("{self.output_dir}", exist_ok=True)

try:
    export_stl(compound, "{self.output_dir}/model.stl")
    print("Exported to {self.output_dir}/model.stl")
except Exception as e:
    print(f"STL export failed: {{e}}")
    try:
        export_step(compound, "{self.output_dir}/model.step")
        print("Exported to {self.output_dir}/model.step")
    except Exception as e2:
        print(f"STEP export failed: {{e2}}")
"""
    
    def emit_part(self, part: Part) -> str:
        """
        生成单个部件的代码模板
        
        Args:
            part: Part 对象
        
        Returns:
            部件代码模板
        """
        safe_name = part.get_safe_name()
        loc = part.location
        
        if part.operation == "revolve":
            return self._emit_revolve_template(safe_name, loc, part.description)
        else:
            return self._emit_extrude_template(safe_name, loc, part.description)
    
    def _emit_extrude_template(self, name: str, location: List[float], desc: str) -> str:
        """Extrude 操作模板"""
        return f"""# {name}: {desc}
{name}_loc_x = {location[0]}
{name}_loc_y = {location[1]}
{name}_loc_z = {location[2]}
{name}_width = 100
{name}_depth = 100
{name}_height = 50

with BuildSketch() as {name}_profile:
    Rectangle({name}_width, {name}_depth)

with BuildPart() as {name}_part:
    with Locations(({name}_loc_x, {name}_loc_y, {name}_loc_z)):
        add({name}_profile.sketch)
    extrude(amount={name}_height)
"""
    
    def _emit_revolve_template(self, name: str, location: List[float], desc: str) -> str:
        """Revolve 操作模板"""
        return f"""# {name}: {desc}
{name}_loc_x = {location[0]}
{name}_loc_y = {location[1]}
{name}_loc_z = {location[2]}
{name}_radius = 50
{name}_angle = 360

with BuildSketch() as {name}_profile:
    Circle({name}_radius)

with BuildPart() as {name}_part:
    with Locations(({name}_loc_x, {name}_loc_y, {name}_loc_z)):
        add({name}_profile.sketch)
    revolve(axis=Axis.Y, revolution_arc={name}_angle)
"""
    
    def update_part_code(self, graph: PartGraph, part_name: str, new_code: str):
        """更新部件代码"""
        part = graph.get_part(part_name)
        if part:
            part.code = new_code
            part.is_dirty = False
    
    def format_code(self, code: str) -> str:
        """格式化代码"""
        # 简单的格式化：移除多余空行
        lines = code.splitlines()
        result = []
        prev_empty = False
        
        for line in lines:
            is_empty = not line.strip()
            if is_empty and prev_empty:
                continue
            result.append(line)
            prev_empty = is_empty
        
        return '\n'.join(result)
