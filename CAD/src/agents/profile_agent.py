from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
import json

PROFILE_PROMPT = """你是一个 Profile Agent，负责生成 OpenSCAD 的 2D 截面代码 (module)。
1. 输出一个 module 定义，例如: `module profile_id() { circle(r=radius); }`
2. 必须使用传入的参数名，禁止 Magic Numbers。
3. 如果引用了 Loop (路径)，请使用 `polygon(points=loop_id);`。
4. 只输出 OpenSCAD 代码。
"""

class ProfileAgent:
    def __init__(self, model_name="gpt-3.5-turbo"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def generate(self, item: dict, all_params: dict) -> str:
        if item.get('layer') != 'profile':
            return ""

        msg = f"""
        生成 OpenSCAD Profile (2D 截面) 代码。
        ID: {item['id']}
        Type: {item['type']}
        Params: {json.dumps(item.get('params'))}
        Available Variables: {list(all_params.keys())}
        
        要求:
        - 定义一个 module {item['id']}() {{ ... }}。
        - 确保几何中心在原点，除非 params 另有指定。
        """
        
        messages = [SystemMessage(content=PROFILE_PROMPT), HumanMessage(content=msg)]
        res = self.llm.invoke(messages)
        return res.content.replace("```openscad", "").replace("```", "").strip()
