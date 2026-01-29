"""
Loop 生成器 - 生成参数定义
"""
from src.app.llm_client import default_client


class LoopGenerator:
    def __init__(self, client=None):
        self.client = client or default_client

    def generate_loop_code(self, part_name: str, profile_desc: str) -> str:
        """
        生成参数定义代码
        
        Args:
            part_name: 部件名称
            profile_desc: 轮廓描述
        
        Returns:
            参数定义代码
        """
        safe_name = part_name.replace(" ", "_").replace("-", "_")
        
        system_prompt = f"""你是一个 build123d 参数生成器。

任务：根据部件描述，生成合理的尺寸参数变量定义。

关键要求：
1. 变量名必须以 `{safe_name}_` 开头
2. 只输出变量定义，格式: `变量名 = 数值`
3. 单位是毫米 (mm)
4. 估算合理的尺寸

示例输出（圆柱形部件）:
```
{safe_name}_radius = 20
{safe_name}_height = 50
```

示例输出（长方体部件）:
```
{safe_name}_width = 100
{safe_name}_depth = 60
{safe_name}_height = 30
```

只输出变量定义代码，不要任何解释或其他代码。"""

        prompt = f"部件: {part_name}\n描述: {profile_desc}\n生成参数。"
        return self.client.generate(prompt, system_prompt)
