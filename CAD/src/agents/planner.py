import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.state import AgentState

# 模拟的 Planner 系统提示词
PLANNER_PROMPT = """你是一个专业的 CAD 建模规划师。
你的任务是根据用户请求，将模型分解为具体的部件 (Parts)。
必须遵循 **参数化建模** 原则：禁止使用 Magic Numbers (直接的数字)，必须定义参数变量。

你必须根据 "Solid -> Profile -> Loop" 的三层结构来思考：
1. **Loop**: 定义路径、轨迹、点集 (如 path_handle)。
2. **Profile**: 定义 2D 截面 (如 circle, square, polygon)，可能会用到 Loop。
3. **Solid**: 定义 3D 实体 (如 extrude, cylinder, difference)，可能会用到 Profile。

**锚点系统 (Anchor System)**:
你不需要计算绝对坐标。你可以使用 "attach" 指令将一个部件连接到另一个部件的锚点上。
语法: `transform: { "attach": "handle.base", "to": "cup.side" }`
这表示将 'handle' 部件的 'base' 锚点 对齐到 'cup' 部件的 'side' 锚点。

**思维链 (Spatial CoT)**:
在生成 JSON 之前，你必须先输出一段 `<thought>` 标签，进行空间推理：
1. 定义全局变量 (e.g. radius, height)。
2. 拆解部件。
3. 想象部件之间的相对位置关系。
4. 决定锚点连接策略。

输出格式必须是 JSON：
{
    "parameters": {
        "cup_radius": 20,
        "cup_height": 50,
        "handle_radius": 5
    },
    "structure": [
        {
            "id": "loop_handle",
            "layer": "loop",
            "type": "path_arc", 
            "params": { "radius": "cup_radius + 10", "start_angle": 0, "end_angle": 180 },
            "description": "手柄的扫描路径"
        },
        {
            "id": "profile_base",
            "layer": "profile",
            "type": "circle",
            "params": { "r": "cup_radius" },
            "description": "杯底截面"
        },
        {
            "id": "solid_cup",
            "layer": "solid",
            "type": "linear_extrude",
            "source_profile": "profile_base",
            "params": { "height": "cup_height" },
            "operation": "union",
            "transform": { "translate": [0,0,0] },
            "anchors": {
                 "top": ["0", "0", "cup_height"],
                 "side": ["cup_radius", "0", "cup_height/2"]
            }
        },
        {
            "id": "solid_handle",
            "layer": "solid",
            "type": "sweep",
            "source_profile": "profile_handle",
            "source_loop": "loop_handle",
            "transform": { "attach": "self.base", "to": "solid_cup.side" },
            "anchors": { "base": ["0", "0", "0"] }
        }
    ],
    "explanation": "简要说明设计思路"
}

注意：
- 所有 params 的值如果是数字，请尽量引用 definitions 中的 key，或者使用简单的数学表达式 (字符串形式)。
- `anchors` 定义了该部件自身的关键点坐标 (相对于该部件原点)。坐标值应为参数化表达式字符串。
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
            # 提取 Thought
            thought = ""
            if "<thought>" in response.content:
                thought = response.content.split("<thought>")[1].split("</thought>")[0]
            
            # 清理 JSON
            content = response.content
            if "</thought>" in content:
                content = content.split("</thought>")[1]
            
            content = content.replace("```json", "").replace("```", "").strip()
            plan = json.loads(content)
            
            # 兼容旧代码结构
            if "structure" in plan and "parts" not in plan:
                plan["parts"] = plan["structure"]
                
            return {
                "plan": plan, 
                "iteration_count": state["iteration_count"] + 1, 
                "messages": [f"Planner Thought: {thought[:100]}...", f"Planner: Generated plan with {len(plan.get('parts', []))} parts"]
            }
        except Exception as e:
            return {"messages": [f"Planner Error: {str(e)}"]}
