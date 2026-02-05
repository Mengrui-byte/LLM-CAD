import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.state import AgentState

# 模拟的 Planner 系统提示词
PLANNER_PROMPT = """你是一个专业的 CAD 建模规划师。
你的任务是根据用户请求，将模型分解为具体的部件 (Parts)。
你需要定义全局坐标系，并为每个部件分配位置和类型。

输出格式必须是 JSON：
{
    "parts": [
        {
            "id": "part_1",
            "name": "描述名称",
            "type": "geometry_type (e.g., cylinder, cube, sphere, extrusion)",
            "params": { ...几何参数... },
            "transform": { ...位置/旋转... },
            "operation": "union/difference/intersection" (与主体的布尔运算关系)
        }
    ],
    "explanation": "简要说明设计思路"
}

如果收到 Feedback，请根据反馈调整参数或结构。
"""

class PlannerAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0.2)

    def plan(self, state: AgentState) -> dict:
        print("--- Planner Agent Working ---")
        messages = [SystemMessage(content=PLANNER_PROMPT)]
        
        user_req = state['user_request']
        feedback = state.get('inspector_feedback')
        
        if feedback:
            content = f"原始需求: {user_req}\n\n上一次迭代的反馈: {feedback}\n请修正规划。"
        else:
            content = f"用户需求: {user_req}"
            
        messages.append(HumanMessage(content=content))
        
        response = self.llm.invoke(messages)
        try:
            # 简单的 JSON 解析，实际项目中可能需要更健壮的 Parser
            content = response.content.replace("```json", "").replace("```", "")
            plan = json.loads(content)
            return {"plan": plan, "iteration_count": state["iteration_count"] + 1, "messages": [f"Planner: Generated plan with {len(plan.get('parts', []))} parts"]}
        except Exception as e:
            return {"messages": [f"Planner Error: {str(e)}"]}
