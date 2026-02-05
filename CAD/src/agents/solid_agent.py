from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
import json

SOLID_PROMPT = """你是一个 Solid Agent，负责生成 OpenSCAD 的 3D 实体代码 (module)。
1. 输出一个 JSON 对象，包含 `code` (代码字符串) 和 `anchors` (锚点定义字典) 和 `bounding_box` (包围盒公式)。
2. 必须使用传入的参数名。
3. `anchors` 字典定义该部件的关键点坐标 (相对于部件局部坐标系)，例如: `{ "top": ["0", "0", "height"] }`。
4. `bounding_box` 定义局部坐标系的范围公式，例如: `{ "min": ["-r", "-r", "0"], "max": ["r", "r", "h"] }`。

JSON 格式示例:
{
  "code": "module solid_id() { ... }",
  "anchors": { ... },
  "bounding_box": { ... }
}
"""

class SolidAgent:
    def __init__(self, model_name="gpt-3.5-turbo"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def generate(self, item: dict, all_params: dict) -> dict:
        if item.get('layer') != 'solid':
            return {}

        msg = f"""
        生成 OpenSCAD Solid 代码及元数据。
        ID: {item['id']}
        Type: {item['type']}
        Params: {json.dumps(item.get('params'))}
        Source Profile: {item.get('source_profile')}
        Transform: {json.dumps(item.get('transform'))}
        Anchors Required: {json.dumps(item.get('anchors', {}))}
        Available Variables: {list(all_params.keys())}
        
        要求:
        1. 代码中定义 module {item['id']}。
        2. 返回 JSON，不要用 Markdown 包裹。
        """
        
        messages = [SystemMessage(content=SOLID_PROMPT), HumanMessage(content=msg)]
        res = self.llm.invoke(messages)
        try:
            content = res.content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except:
            # Fallback for plain text
            return {"code": res.content, "anchors": {}, "bounding_box": {}}
