from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState

GENERATOR_PROMPT = """你是一个 OpenSCAD 代码汇编器。
你的任务是将全局参数定义、Loop 变量、Profile 模块和 Solid 模块组合成一个完整的 .scad 文件。

规则：
1. 首先定义所有全局参数 (Variables)。
2. 然后放置 Loop 定义。
3. 然后放置 Profile 模块。
4. 然后放置 Solid 模块。
5. 最后，在主层级调用所有的 Solid 模块 (应用 Operation，如 union/difference)。
   - 通常第一个 Solid 是主体。
   - 这里的 operation 逻辑需要你在 main 中处理：
     difference() {
        solid_main();
        solid_cut_1();
        solid_cut_2();
     }
6. 添加 $fn=100。
"""

class GeneratorAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def assemble(self, state: AgentState) -> dict:
        print("--- Generator Agent Assembling ---")
        plan = state.get("plan")
        worker_outputs = state.get("worker_outputs")
        
        # 提取参数
        params = plan.get("parameters", {})
        param_block = "// Parameters\n"
        for k, v in params.items():
            param_block += f"{k} = {v};\n"
            
        # 处理锚点连接逻辑 (简单的字符串替换或生成偏移量)
        # 注意: 这里的实现是简化的，复杂的锚点计算可能需要 Python 表达式求值
        # 我们假设 Planner 已经在 transform 中生成了 "attach" 指令，或者我们在这里生成偏移计算代码
        
        anchor_registry = state.get("anchor_registry", {})
        
        context = f"规划方案 (Structure): {json.dumps(plan.get('structure', plan.get('parts', [])))}\n\n"
        context += f"参数定义:\n{param_block}\n\n"
        context += f"锚点注册表:\n{json.dumps(anchor_registry)}\n\n"
        context += "生成的代码片段:\n"
        
        # 按类型分类以便 Prompt 理解
        for pid, code in worker_outputs.items():
            context += f"--- ID: {pid} ---\n{code}\n"
            
        messages = [
            SystemMessage(content=GENERATOR_PROMPT),
            HumanMessage(content=context)
        ]
        
        response = self.llm.invoke(messages)
        full_code = response.content.replace("```openscad", "").replace("```", "").strip()
        
        # 添加视觉辅助 (Grid & Axes)
        visual_helpers = """
// Visual Helpers
module draw_axes(len=100) {
    color("red") translate([len/2,0,0]) cube([len, 1, 1], center=true);
    color("green") translate([0,len/2,0]) cube([1, len, 1], center=true);
    color("blue") translate([0,0,len/2]) cube([1, 1, len], center=true);
}
module draw_grid(size=200, step=10) {
    color([0.5,0.5,0.5, 0.2]) 
    for(i=[-size/2:step:size/2]) {
        translate([i, 0, 0]) cube([0.5, size, 0.1], center=true);
        translate([0, i, 0]) cube([size, 0.5, 0.1], center=true);
    }
}
draw_axes();
draw_grid();
"""
        full_code += visual_helpers
        
        # 保存到文件
        with open("model.scad", "w") as f:
            f.write(full_code)
            
        return {"full_code": full_code, "messages": ["Generator: SCAD code generated and saved to model.scad"]}
