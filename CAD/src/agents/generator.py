from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState

GENERATOR_PROMPT = """你是一个 OpenSCAD 代码汇编器。
你的任务是将各个部件的代码片段组合成一个完整的、可编译的 .scad 文件。

规则：
1. 确保所有部件都被正确调用。
2. 处理布尔运算 (union, difference)。通常第一个部件是主体，后续标为 'difference' 的部件应从主体中减去。
3. 添加 $fn=100 以保证平滑度。
4. 只输出最终的 SCAD 代码，不要包含 Markdown 格式。
"""

class GeneratorAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def assemble(self, state: AgentState) -> dict:
        print("--- Generator Agent Assembling ---")
        plan = state.get("plan")
        worker_outputs = state.get("worker_outputs")
        
        context = f"规划方案: {plan}\n\n生成的部件代码片段:\n"
        for pid, code in worker_outputs.items():
            context += f"--- Part ID: {pid} ---\n{code}\n"
            
        messages = [
            SystemMessage(content=GENERATOR_PROMPT),
            HumanMessage(content=context)
        ]
        
        response = self.llm.invoke(messages)
        full_code = response.content.replace("```openscad", "").replace("```", "").strip()
        
        # 保存到文件
        with open("model.scad", "w") as f:
            f.write(full_code)
            
        return {"full_code": full_code, "messages": ["Generator: SCAD code generated and saved to model.scad"]}
