from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Annotated
import operator

class AgentState(TypedDict):
    user_request: str
    plan: Optional[Dict[str, Any]]  # 规划的部件列表
    worker_outputs: Dict[str, str]  # 各个部件生成的代码片段
    full_code: Optional[str]        # 汇编后的完整 OpenSCAD 代码
    render_image_path: Optional[str] # 渲染图片路径
    inspector_feedback: Optional[str] # 检查员反馈
    anchor_registry: Dict[str, Any]   # 锚点注册表 { "solid_id": { "anchor_name": [x,y,z] } }
    debug_metadata: Dict[str, Any]    # 调试元数据 (e.g. Bounding Boxes)
    iteration_count: int            # 迭代次数
    messages: List[str]             # 日志/消息历史
