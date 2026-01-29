"""
Profile 生成器 - 生成 2D 草图
"""
from src.app.llm_client import default_client


class ProfileGenerator:
    def __init__(self, client=None):
        self.client = client or default_client

    def generate_profile_code(
        self, 
        part_name: str, 
        solid_desc: str, 
        loop_code: str = None
    ) -> str:
        """
        生成 profile_obj 对象代码
        
        Args:
            part_name: 部件名称
            solid_desc: 实体描述
            loop_code: 上游 loop 代码 (已弃用，保留兼容)
        
        Returns:
            build123d 代码片段
        """
        safe_name = part_name.replace(" ", "_").replace("-", "_")
        
        system_prompt = f"""你是一个 build123d Python 代码生成器。

任务：生成 `profile_obj` 对象（2D 草图）。

关键要求：
1. **参数化**：尺寸定义为变量，变量名以 `{safe_name}_` 开头
2. **几何中心对齐**：图形以 (0,0) 为中心
3. **只使用基础形状**：Circle, Rectangle, Ellipse, RegularPolygon

## 正确示例

圆形:
```python
{safe_name}_radius = 10
with BuildSketch() as profile_obj:
    Circle(radius={safe_name}_radius)
```

矩形:
```python
{safe_name}_width = 100
{safe_name}_height = 50
with BuildSketch() as profile_obj:
    Rectangle({safe_name}_width, {safe_name}_height)
```

椭圆:
```python
{safe_name}_rx = 30
{safe_name}_ry = 20
with BuildSketch() as profile_obj:
    Ellipse({safe_name}_rx, {safe_name}_ry)
```

只输出代码，不要任何解释。"""

        prompt = f"部件: {part_name}\n描述: {solid_desc}\n生成代码。"
        return self.client.generate(prompt, system_prompt)
