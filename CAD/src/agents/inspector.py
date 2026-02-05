import base64
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState
from src.utils.renderer import render_scad

INSPECTOR_PROMPT = """你是一个严格的模型检查员 (Inspector Agent)。
你的任务是检查生成的 3D 模型图片 (和代码) 是否符合用户的原始需求。

判断标准：
1. 结构完整性：是否缺少部件？连接是否正常？
2. 几何正确性：比例是否协调？
3. 需求匹配度：是否实现了用户的所有要求？

输出格式：
状态: [PASS/FAIL]
反馈: [详细的修改建议或通过理由]
"""

class InspectorAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0.1)

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def inspect(self, state: AgentState) -> dict:
        print("--- Inspector Agent Checking ---")
        
        # 1. 尝试渲染
        image_path = render_scad()
        
        messages = [SystemMessage(content=INSPECTOR_PROMPT)]
        user_req = state['user_request']
        full_code = state.get('full_code', '')
        
        content = [{"type": "text", "text": f"用户原始需求: {user_req}\n生成的 OpenSCAD 代码:\n{full_code}"}]
        
        if image_path:
            base64_image = self._encode_image(image_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
            })
        else:
            content[0]["text"] += "\n(注意：OpenSCAD 未安装，无法提供渲染图，请仅基于代码逻辑进行检查。)"

        messages.append(HumanMessage(content=content))
        
        response = self.llm.invoke(messages)
        feedback_text = response.content
        
        status = "FAIL"
        if "PASS" in feedback_text.upper() and "FAIL" not in feedback_text.upper():
            status = "PASS"
            
        # 强制设置迭代上限，防止无限循环
        if state["iteration_count"] >= 3:
            status = "PASS"
            feedback_text += " (已达到最大迭代次数，强制通过)"

        return {
            "inspector_feedback": feedback_text, 
            "messages": [f"Inspector: {status} - {feedback_text[:50]}..."]
        }
