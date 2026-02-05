from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.planner import PlannerAgent
from src.agents.workers import WorkerNode
from src.agents.generator import GeneratorAgent
from src.agents.inspector import InspectorAgent

# 初始化 Agents
planner = PlannerAgent()
workers = WorkerNode()
generator = GeneratorAgent()
inspector = InspectorAgent()

def planner_step(state: AgentState):
    return planner.plan(state)

def workers_step(state: AgentState):
    return workers.process(state)

def generator_step(state: AgentState):
    return generator.assemble(state)

def inspector_step(state: AgentState):
    return inspector.inspect(state)

def should_continue(state: AgentState):
    feedback = state.get("inspector_feedback", "")
    iteration = state.get("iteration_count", 0)
    
    # 简单的逻辑判断状态
    if "PASS" in feedback and "FAIL" not in feedback:
        return END
    
    if iteration >= 3:
        return END
        
    return "planner"

# 构建图
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("planner", planner_step)
workflow.add_node("workers", workers_step)
workflow.add_node("generator", generator_step)
workflow.add_node("inspector", inspector_step)

# 设置边
workflow.set_entry_point("planner")
workflow.add_edge("planner", "workers")
workflow.add_edge("workers", "generator")
workflow.add_edge("generator", "inspector")

# 条件边
workflow.add_conditional_edges(
    "inspector",
    should_continue,
    {
        "planner": "planner",
        END: END
    }
)

app = workflow.compile()
