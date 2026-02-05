from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents.planner import PlannerAgent
from src.agents.loop_agent import LoopAgent
from src.agents.profile_agent import ProfileAgent
from src.agents.solid_agent import SolidAgent
from src.agents.generator import GeneratorAgent
from src.agents.inspector import InspectorAgent

# 初始化 Agents
planner = PlannerAgent()
loop_agent = LoopAgent()
profile_agent = ProfileAgent()
solid_agent = SolidAgent()
generator = GeneratorAgent()
inspector = InspectorAgent()

def planner_step(state: AgentState):
    return planner.plan(state)

def processing_step(state: AgentState):
    print("--- Processing Agents (Loop/Profile/Solid) ---")
    plan = state.get("plan")
    if not plan:
        return {"messages": ["Error: No plan found"]}
    
    # 兼容 structure 或 parts 字段
    structure = plan.get("structure", plan.get("parts", []))
    params = plan.get("parameters", {})
    
    anchor_registry = {}
    debug_metadata = {}
    
    for item in structure:
        # 默认为 solid 兼容旧逻辑
        layer = item.get("layer", "solid").lower()
        
        try:
            if layer == "loop":
                code = loop_agent.generate(item, params)
                outputs[item['id']] = code
            elif layer == "profile":
                code = profile_agent.generate(item, params)
                outputs[item['id']] = code
            elif layer == "solid":
                result = solid_agent.generate(item, params)
                if isinstance(result, dict):
                    outputs[item['id']] = result.get("code", "")
                    if "anchors" in result:
                        anchor_registry[item['id']] = result["anchors"]
                    if "bounding_box" in result:
                        debug_metadata[item['id']] = result["bounding_box"]
                else:
                     outputs[item['id']] = result
            else:
                # Fallback
                result = solid_agent.generate(item, params)
                if isinstance(result, dict):
                     outputs[item['id']] = result.get("code", "")
                else:
                     outputs[item['id']] = result
                
            print(f"Generated {layer}: {item['id']}")
        except Exception as e:
            print(f"Error generating {item['id']}: {e}")
            outputs[item['id']] = f"// Error generating {item['id']}: {e}"

    return {
        "worker_outputs": outputs, 
        "anchor_registry": anchor_registry, 
        "debug_metadata": debug_metadata
    }

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
workflow.add_node("processors", processing_step)
workflow.add_node("generator", generator_step)
workflow.add_node("inspector", inspector_step)

# 设置边
workflow.set_entry_point("planner")
workflow.add_edge("planner", "processors")
workflow.add_edge("processors", "generator")
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
