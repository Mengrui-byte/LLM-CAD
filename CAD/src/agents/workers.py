from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.state import AgentState
import json

# 定义各个 Agent 的 Prompt
LOOP_PROMPT = """你是一个 Loop Agent，负责生成 OpenSCAD 的路径或 2D 轮廓代码 (polygon, circle, square)。
只输出代码片段，不要解释。
"""

SOLID_PROMPT = """你是一个 Solid Agent，负责生成 OpenSCAD 的 3D 实体代码 (cylinder, cube, sphere, linear_extrude, rotate_extrude)。
根据提供的参数生成代码。只输出代码片段。
"""

class WorkerNode:
    def __init__(self, model_name="gpt-3.5-turbo"): # Worker 可以用轻量级模型
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def generate_part_code(self, part: dict) -> str:
        # 这里简化处理：根据类型选择 Prompt
        p_type = part.get('type', '').lower()
        
        prompt = SOLID_PROMPT if any(x in p_type for x in ['cylinder', 'cube', 'sphere', 'extrude']) else LOOP_PROMPT
        
        msg = f"""
        生成 OpenSCAD 代码片段。
        部件名称: {part['name']}
        类型: {part['type']}
        参数: {json.dumps(part.get('params'))}
        变换 (Transform): {json.dumps(part.get('transform'))}
        
        要求：
        1. 包含对应的 translate/rotate 操作。
        2. 代码应自包含，定义一个 module 或者直接是一段几何体代码。
        3. 如果是 module，请命名为 {part['id']}。
        """
        
        messages = [SystemMessage(content=prompt), HumanMessage(content=msg)]
        response = self.llm.invoke(messages)
        return response.content.replace("```openscad", "").replace("```", "").strip()

    def process(self, state: AgentState) -> dict:
        print("--- Workers Processing Parts ---")
        plan = state.get("plan")
        if not plan or "parts" not in plan:
            return {"messages": ["Workers: No plan found"]}

        worker_outputs = {}
        for part in plan["parts"]:
            # 在实际复杂系统中，这里可以并行分发给不同的 Loop/Profile/Solid Agents
            # 这里我们串行模拟
            code = self.generate_part_code(part)
            worker_outputs[part['id']] = code
            
        return {"worker_outputs": worker_outputs}
