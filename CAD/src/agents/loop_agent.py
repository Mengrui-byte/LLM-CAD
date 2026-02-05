from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
import json

LOOP_PROMPT = """你是一个 Loop Agent，负责生成 OpenSCAD 的路径数据或点集变量。
1. 输出通常是一个向量数组变量定义，例如: `loop_path = [[0,0], [10,0], ...];`
2. 必须使用传入的参数名 (Available Variables)，禁止使用 Magic Numbers。
3. 只输出 OpenSCAD 代码。
"""

class LoopAgent:
    def __init__(self, model_name="gpt-3.5-turbo"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def generate(self, item: dict, all_params: dict) -> str:
        if item.get('layer') != 'loop':
            return ""

        msg = f"""
        生成 OpenSCAD Loop (路径/点集) 代码。
        ID: {item['id']}
        Type: {item['type']}
        Params: {json.dumps(item.get('params'))}
        Available Variables (Keys): {list(all_params.keys())}
        
        要求:
        - 定义一个名为 {item['id']} 的变量。
        - 使用几何函数或数学公式生成路径点。
        """
        
        messages = [SystemMessage(content=LOOP_PROMPT), HumanMessage(content=msg)]
        res = self.llm.invoke(messages)
        return res.content.replace("```openscad", "").replace("```", "").strip()
