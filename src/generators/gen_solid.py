"""
Solid 生成器 - 生成 3D 实体
"""
from typing import List
from src.app.llm_client import default_client


class SolidGenerator:
    def __init__(self, client=None):
        self.client = client or default_client

    def generate_solid_code(
        self, 
        part_name: str, 
        solid_desc: str, 
        profile_code: str,
        location: List[float],
        operation: str = "extrude"
    ) -> str:
        """
        生成 part_obj 对象代码
        
        Args:
            part_name: 部件名称
            solid_desc: 实体描述
            profile_code: Profile 代码
            location: [x, y, z] 位置坐标
            operation: 操作类型 (extrude/revolve/loft)
        
        Returns:
            build123d 代码片段
        """
        safe_name = part_name.replace(" ", "_").replace("-", "_")
        loc_str = f"({location[0]}, {location[1]}, {location[2]})"
        
        system_prompt = f"""你是一个 build123d Python 代码生成器。

任务：生成 `part_obj` 对象（3D 实体）。

## 关键要求

1. **参数化**：所有数值定义为变量，变量名以 `{safe_name}_` 开头
2. **位置参数化**：
   - `{safe_name}_loc_x = {location[0]}`
   - `{safe_name}_loc_y = {location[1]}`
   - `{safe_name}_loc_z = {location[2]}`

## 严禁使用（会导致错误）

- ❌ `BuildSketch(path @ 0)` - path @ 0 返回 Vector，不是 Plane
- ❌ `BuildSketch(line @ 0)` - 同上
- ❌ `Pos()` - 已弃用
- ❌ `BuildLine` 内部嵌套 `BuildSketch`
- ❌ `revolve` 时草图与旋转轴相交 - 草图必须完全在轴的一侧

## 正确的代码模式

### Extrude（拉伸）- 最常用
```python
{safe_name}_loc_x = {location[0]}
{safe_name}_loc_y = {location[1]}
{safe_name}_loc_z = {location[2]}
{safe_name}_height = 50
with BuildPart() as part_obj:
    with BuildSketch(Plane.XY.offset({safe_name}_loc_z)):
        with Locations(({safe_name}_loc_x, {safe_name}_loc_y)):
            Circle(radius=10)
    extrude(amount={safe_name}_height)
```

### Loft（放样）- 两个截面
```python
{safe_name}_loc_x = {location[0]}
{safe_name}_loc_y = {location[1]}
{safe_name}_loc_z = {location[2]}
{safe_name}_height = 50
{safe_name}_radius_bottom = 10
{safe_name}_radius_top = 5
with BuildPart() as part_obj:
    with BuildSketch(Plane.XY.offset({safe_name}_loc_z)):
        with Locations(({safe_name}_loc_x, {safe_name}_loc_y)):
            Circle(radius={safe_name}_radius_bottom)
    with BuildSketch(Plane.XY.offset({safe_name}_loc_z + {safe_name}_height)):
        with Locations(({safe_name}_loc_x, {safe_name}_loc_y)):
            Circle(radius={safe_name}_radius_top)
    loft()
```

### Revolve（旋转）- 生成圆环/球体
**重要**: 草图必须完全在旋转轴的一侧，不能与轴相交！

```python
{safe_name}_loc_x = {location[0]}
{safe_name}_loc_y = {location[1]}
{safe_name}_loc_z = {location[2]}
{safe_name}_major_radius = 30  # 圆环大半径（草图中心到旋转轴的距离）
{safe_name}_minor_radius = 10  # 圆环小半径（草图本身的半径）
with BuildPart() as part_obj:
    with BuildSketch(Plane.XZ.offset({safe_name}_loc_y)):
        # 草图中心在 X={safe_name}_major_radius，确保不与 Z 轴相交
        with Locations(({safe_name}_major_radius, {safe_name}_loc_z)):
            Circle(radius={safe_name}_minor_radius)
    revolve(axis=Axis.Z, revolution_arc=360)
```

### Revolve 错误示例（会报错）
```python
# ❌ 错误：椭圆中心在 X=0，会穿过 Z 轴
with BuildSketch(Plane.XZ):
    with Locations((0, 20)):
        Ellipse(x_radius=30, y_radius=20)  # 从 X=-30 到 X=30，穿过 Z 轴！
revolve(axis=Axis.Z)  # ERROR: 草图与旋转轴相交
```

只输出代码，不要任何解释。使用上述正确的模式。
如果是球体/椭球体，考虑用 extrude + 布尔运算代替 revolve。"""

        input_context = f"""部件: {part_name}
描述: {solid_desc}
位置: {loc_str}
操作类型: {operation}
Profile代码（参考，可能需要重写）:
{profile_code}
"""
        
        prompt = f"{input_context}\n生成代码。"
        return self.client.generate(prompt, system_prompt)
