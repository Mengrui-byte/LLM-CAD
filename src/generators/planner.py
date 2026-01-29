"""
CAD 规划器 - 使用 CoT 方法将用户请求拆解为部件列表
支持可控生成：用户可以指定约束条件
"""
import json
import re
from typing import List, Dict, Optional, Any
from src.app.llm_client import default_client


class Planner:
    def __init__(self, client=None):
        self.client = client or default_client

    def plan(
        self, 
        user_request: str,
        constraints: Dict[str, Any] = None,
        existing_parts: List[str] = None
    ) -> List[Dict]:
        """
        将用户请求拆解为部件列表
        
        Args:
            user_request: 用户的自然语言描述
            constraints: 约束条件 (如尺寸限制、材料等)
            existing_parts: 已存在的部件列表 (用于增量生成)
        
        Returns:
            部件列表: [{"name": str, "description": str, "location": [x,y,z], "dependencies": []}]
        """
        constraint_text = ""
        if constraints:
            constraint_text = f"\n用户指定的约束条件:\n{json.dumps(constraints, ensure_ascii=False, indent=2)}\n"
        
        existing_text = ""
        if existing_parts:
            existing_text = f"\n已存在的部件 (不要重复生成):\n{', '.join(existing_parts)}\n"
        
        system_prompt = f"""你是一个专业的 CAD 建模规划师。使用 Chain of Thought 方法进行思考。

任务：将用户的自然语言描述拆解为具体的 3D 实体零部件列表。

关键任务：
1. **拆解部件**：识别所有独立的物理部件
2. **确定尺寸**：估算合理的几何尺寸 (单位: mm)
3. **计算坐标**：精确计算每个部件的中心点坐标
4. **依赖关系**：标注部件之间的连接关系

坐标系规则 (CRITICAL):
- 默认假设所有 2D 草图以原点 (0,0) 为中心绘制
- Z轴为垂直方向，地面 Z=0
- location 的 Z 值代表部件的起始高度 (Base Z)
- **连接性**: 部件之间必须有物理接触，绝对不能悬空
  - 示例：椅座厚5在Z=40，范围40~45，椅背必须从Z=45开始

输出格式 (JSON 数组):
[
    {{
        "name": "part_name",
        "description": "详细描述: 形状、尺寸 width=X depth=Y height=Z",
        "location": [x, y, z],
        "dependencies": ["依赖的部件名"],
        "operation": "extrude" | "revolve" | "loft"
    }}
]
{constraint_text}{existing_text}
思考过程示例：
1. 分析需求 -> 2. 拆解部件 -> 3. 尺寸估算 -> 4. 坐标计算 -> 5. 连接验证

注意：只输出 JSON 数组，不要输出其他内容。"""

        prompt = f"请详细规划这个对象的建模部件及位置: {user_request}"
        
        response = self.client.generate(prompt, system_prompt)
        
        try:
            # 尝试提取 JSON 部分
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                # 验证和规范化
                return self._normalize_plan(plan)
        except Exception as e:
            print(f"[Planner] JSON parsing failed: {e}\nResponse: {response}")
        
        # Fallback: 简单规划
        return [{"name": "main_body", "description": user_request, "location": [0, 0, 0], "dependencies": [], "operation": "extrude"}]
    
    def _normalize_plan(self, plan: List[Dict]) -> List[Dict]:
        """规范化规划结果"""
        normalized = []
        for item in plan:
            normalized.append({
                "name": item.get("name", "part").replace(" ", "_").replace("-", "_"),
                "description": item.get("description", ""),
                "location": item.get("location", [0, 0, 0]),
                "dependencies": item.get("dependencies", []),
                "operation": item.get("operation", "extrude")
            })
        return normalized
    
    def refine_plan(
        self, 
        current_plan: List[Dict], 
        feedback: str
    ) -> List[Dict]:
        """根据用户反馈调整规划"""
        system_prompt = """你是 CAD 规划师。根据用户反馈修改现有规划。

输入: 当前规划 JSON + 用户反馈
输出: 修改后的完整规划 JSON (同样的格式)

注意：只修改需要改变的部分，保持其他部分不变。"""

        prompt = f"""当前规划:
{json.dumps(current_plan, ensure_ascii=False, indent=2)}

用户反馈: {feedback}

请输出修改后的完整规划:"""

        response = self.client.generate(prompt, system_prompt)
        
        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return self._normalize_plan(json.loads(json_match.group()))
        except Exception as e:
            print(f"[Planner] Refine failed: {e}")
        
        return current_plan
    
    def suggest_improvements(self, plan: List[Dict]) -> List[str]:
        """分析规划并提出改进建议"""
        suggestions = []
        
        # 检查悬空部件
        for item in plan:
            loc = item.get("location", [0, 0, 0])
            deps = item.get("dependencies", [])
            
            if loc[2] > 0 and not deps:
                suggestions.append(f"部件 '{item['name']}' 在 Z={loc[2]} 但没有依赖，可能悬空")
        
        # 检查重叠
        # TODO: 更复杂的碰撞检测
        
        return suggestions
