"""
完整生成器 - 协调所有生成器完成完整的 CAD 代码生成
支持可控生成、增量生成、历史管理
"""
import os
from typing import Optional, List, Dict, Any, Callable
from src.generators.planner import Planner
from src.generators.gen_loop import LoopGenerator
from src.generators.gen_profile import ProfileGenerator
from src.generators.gen_solid import SolidGenerator
from src.generators.refiner import Refiner
from src.generators.renderer import render_code, render_code_safe
from src.utils.history_manager import HistoryManager
from src.utils.code_utils import clean_code, fix_common_errors, validate_build123d_code
from src.app.llm_client import default_client


class FullGenerator:
    """
    完整的 CAD 代码生成器
    
    工作流程:
    1. Planner: 用户请求 -> 部件规划
    2. 对每个部件:
       - LoopGenerator: 生成轮廓边界
       - ProfileGenerator: 生成 2D 草图
       - SolidGenerator: 生成 3D 实体
    3. 组装所有部件
    4. 渲染输出
    """
    
    def __init__(self, cache_dir: str = None):
        self.planner = Planner()
        self.loop_gen = LoopGenerator()
        self.profile_gen = ProfileGenerator()
        self.solid_gen = SolidGenerator()
        self.refiner = Refiner()
        self.client = default_client
        
        # 历史管理
        cache_dir = cache_dir or os.path.join(os.getcwd(), "cache")
        self.history_manager = HistoryManager(cache_dir)
        
        # 状态
        self.last_plan: List[Dict] = []
        self.last_code: str = ""
        self.generation_log: List[str] = []
        
        # 回调
        self.on_progress: Optional[Callable[[str, float], None]] = None
        self.on_part_generated: Optional[Callable[[str, str], None]] = None
        self.on_plan_ready: Optional[Callable[[List[Dict]], None]] = None
    
    def generate_full_code(
        self, 
        user_request: str,
        constraints: Dict[str, Any] = None,
        selected_parts: List[str] = None
    ) -> str:
        """
        生成完整的 CAD 代码
        
        Args:
            user_request: 用户请求
            constraints: 约束条件 (尺寸限制等)
            selected_parts: 只生成指定的部件 (用于增量生成)
        
        Returns:
            完整的 build123d Python 代码
        """
        self.generation_log = []
        self._log("User Request", user_request)
        
        # 记录到历史
        self.history_manager.add_interaction("User", user_request)
        
        # 生成标题
        if self.history_manager.title == "New Session":
            title = self._generate_title(user_request)
            self.history_manager.set_title(title)
        
        # Step 1: 规划
        self._report_progress("🔍 正在规划部件结构...", 0.1)
        plan = self.planner.plan(user_request, constraints)
        if not plan:
            raise Exception("Planning failed")
        
        self.last_plan = plan
        self._log("Plan", str(plan))
        self._report_progress(f"📋 规划完成: {len(plan)} 个部件", 0.15)
        
        # 通知 UI 规划完成，可以预填参数
        if self.on_plan_ready:
            self.on_plan_ready(plan)
        
        # 过滤选中的部件
        if selected_parts:
            plan = [p for p in plan if p["name"] in selected_parts]
        
        # Step 2: 生成代码
        full_script = self._build_imports()
        final_parts = []
        
        total_parts = len(plan)
        for i, item in enumerate(plan):
            progress = 0.1 + (0.8 * (i / total_parts))
            part_name = item.get("name", "part")
            desc = item.get("description", "")
            location = item.get("location", [0, 0, 0])
            operation = item.get("operation", "extrude")
            safe_name = part_name.replace(" ", "_").replace("-", "_")
            
            self._report_progress(f"🔧 [{i+1}/{total_parts}] 生成 {part_name}...", progress)
            self._log(f"Part {i+1}", f"{part_name} at {location}")
            
            # 生成 Loop
            self._report_progress(f"   ├─ 生成轮廓 (Loop)...", progress + 0.02)
            loop_code = self.loop_gen.generate_loop_code(part_name, desc)
            loop_code = clean_code(loop_code)
            
            # 生成 Profile
            self._report_progress(f"   ├─ 生成草图 (Profile)...", progress + 0.04)
            profile_code = self.profile_gen.generate_profile_code(part_name, desc, loop_code)
            profile_code = clean_code(profile_code)
            
            # 生成 Solid
            self._report_progress(f"   └─ 生成实体 (Solid)...", progress + 0.06)
            solid_code = self.solid_gen.generate_solid_code(
                part_name, desc, profile_code, location, operation
            )
            solid_code = clean_code(solid_code)
            solid_code = fix_common_errors(solid_code)  # 修复常见错误
            
            # 组装代码 (重命名变量避免冲突)
            full_script += self._assemble_part_code(
                safe_name, loop_code, profile_code, solid_code
            )
            
            final_parts.append(f"{safe_name}_part")
            
            if self.on_part_generated:
                self.on_part_generated(part_name, solid_code)
        
        # Step 3: 组装和导出
        self._report_progress("📦 组装部件...", 0.9)
        full_script += self._build_assembly(final_parts)
        full_script += self._build_export()
        
        # 最终修复检查
        full_script = fix_common_errors(full_script)
        
        self.last_code = full_script
        
        # 记录生成的代码
        self.history_manager.add_interaction(
            "AI", 
            "Generated initial code", 
            code=full_script,
            plan=plan
        )
        
        self._report_progress(f"✅ 代码生成完成 ({len(full_script)} 字符)", 1.0)
        return full_script
    
    def refine_code(self, current_code: str, user_feedback: str) -> str:
        """根据用户反馈修改代码"""
        self.history_manager.add_interaction("User", user_feedback)
        self._log("Refine Request", user_feedback)
        
        # 获取上下文
        context = self.history_manager.get_conversation_context(max_turns=3)
        
        new_code = self.refiner.refine(current_code, user_feedback, context=context)
        new_code = clean_code(new_code)
        
        self.last_code = new_code
        self.history_manager.add_interaction("AI", "Refined code", code=new_code)
        
        return new_code
    
    def quick_fix(self, code: str, error: str) -> str:
        """快速修复代码错误"""
        fixed = self.refiner.quick_fix(code, error)
        if fixed:
            fixed = clean_code(fixed)
            self.history_manager.add_interaction(
                "AI", 
                f"Quick fix for: {error[:50]}...", 
                code=fixed
            )
        return fixed
    
    def regenerate_part(
        self, 
        part_name: str, 
        new_description: str = None
    ) -> str:
        """重新生成单个部件"""
        if not self.last_plan:
            raise Exception("No existing plan")
        
        # 找到该部件
        part = None
        for p in self.last_plan:
            if p["name"] == part_name:
                part = p
                break
        
        if not part:
            raise Exception(f"Part {part_name} not found in plan")
        
        if new_description:
            part["description"] = new_description
        
        # 重新生成该部件的代码
        safe_name = part_name.replace(" ", "_").replace("-", "_")
        desc = part.get("description", "")
        location = part.get("location", [0, 0, 0])
        operation = part.get("operation", "extrude")
        
        loop_code = self.loop_gen.generate_loop_code(part_name, desc)
        loop_code = clean_code(loop_code)
        
        profile_code = self.profile_gen.generate_profile_code(part_name, desc, loop_code)
        profile_code = clean_code(profile_code)
        
        solid_code = self.solid_gen.generate_solid_code(
            part_name, desc, profile_code, location, operation
        )
        solid_code = clean_code(solid_code)
        solid_code = fix_common_errors(solid_code)  # 修复常见错误
        
        # TODO: 替换现有代码中该部件的部分
        # 目前返回部件代码，由调用者处理
        return self._assemble_part_code(safe_name, loop_code, profile_code, solid_code)
    
    def _generate_title(self, user_request: str) -> str:
        """使用 LLM 生成简短标题"""
        system_prompt = "Summarize the user's request into a short title (3-5 words). Output ONLY the title."
        prompt = f"User request: {user_request}\nTitle:"
        try:
            title = self.client.generate(prompt, system_prompt)
            if title:
                return title.strip().replace('"', '').replace("'", "")
        except Exception:
            pass
        return "New Session"
    
    def _build_imports(self) -> str:
        """构建导入语句"""
        return """from build123d import *
from math import *
try:
    from build123d import export_stl, export_step
except ImportError:
    pass

"""
    
    def _assemble_part_code(
        self, 
        safe_name: str, 
        loop_code: str, 
        profile_code: str, 
        solid_code: str
    ) -> str:
        """组装单个部件的代码"""
        code = ""
        
        # Loop
        code += loop_code.replace("loop_edges", f"{safe_name}_edges") + "\n\n"
        
        # Profile
        p_code = profile_code.replace("profile_obj", f"{safe_name}_profile")
        p_code = p_code.replace("loop_edges", f"{safe_name}_edges")
        code += p_code + "\n\n"
        
        # Solid
        s_code = solid_code.replace("part_obj", f"{safe_name}_part")
        s_code = s_code.replace("profile_obj", f"{safe_name}_profile")
        code += s_code + "\n\n"
        
        return code
    
    def _build_assembly(self, parts: List[str]) -> str:
        """构建组装代码"""
        if not parts:
            return ""
        
        parts_expr = ", ".join([f"{p}.part" for p in parts])
        return f"compound = Compound(children=[{parts_expr}])\n\n"
    
    def _build_export(self) -> str:
        """构建导出代码"""
        return """try:
    if 'export_stl' in dir():
        export_stl(compound, 'output/model.stl')
    else:
        compound.export_stl('output/model.stl')
except Exception as e:
    print(f'Export failed: {e}')
    try:
        if 'export_step' in dir():
            export_step(compound, 'output/model.step')
        else:
            compound.export_step('output/model.step')
    except Exception as e2:
        print(f'STEP export failed: {e2}')
"""
    
    def _report_progress(self, message: str, progress: float):
        """报告进度"""
        if self.on_progress:
            self.on_progress(message, progress)
        print(f"[Generator] {message} ({progress*100:.0f}%)")
    
    def _log(self, category: str, message: str):
        """记录日志"""
        self.generation_log.append(f"[{category}] {message}")
    
    # 历史管理代理方法
    def save_history(self):
        self.history_manager.save_session()
    
    def clear_history(self):
        self.history_manager.clear()
    
    def get_history_list(self):
        return self.history_manager.list_sessions()
    
    def load_history(self, filename: str):
        return self.history_manager.load_session(filename)
    
    def delete_history(self, filename: str):
        return self.history_manager.delete_session(filename)
    
    def log_manual_edit(self, code: str):
        """记录手动编辑"""
        self.history_manager.add_interaction("User", "Manual parameter update", code=code)
