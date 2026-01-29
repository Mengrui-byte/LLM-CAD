"""
代码精炼器 - 根据用户反馈修改代码
支持局部修改和保护用户手动编辑
"""
from typing import Optional, Set
from src.app.llm_client import default_client


class Refiner:
    def __init__(self, client=None):
        self.client = client or default_client
        self.protected_lines: Set[int] = set()  # 受保护的行号

    def refine(
        self, 
        current_code: str, 
        user_request: str,
        protect_manual_edits: bool = True,
        context: str = None
    ) -> str:
        """
        基于现有代码和用户反馈进行修改
        
        Args:
            current_code: 当前代码
            user_request: 用户修改请求
            protect_manual_edits: 是否保护手动编辑的部分
            context: 额外上下文信息
        
        Returns:
            修改后的完整代码
        """
        context_text = ""
        if context:
            context_text = f"\n历史上下文:\n{context}\n"
        
        protection_text = ""
        if protect_manual_edits and self.protected_lines:
            protection_text = f"\n注意: 以下行号的代码是用户手动编辑的，请尽量保持不变: {sorted(self.protected_lines)}\n"
        
        system_prompt = f"""你是一个专业的 build123d Python 代码修正专家。

任务：基于用户的需求修改现有代码。

输入：
1. 现有的完整 Python 代码
2. 用户的修改请求

要求：
1. **完整输出**：必须输出修改后的**完整**代码
2. **保持结构**：保持原有代码的参数化结构
3. **必要导入**：确保包含 `from math import *` 和 `from build123d import *`
4. **严禁 Pos()**：Locations 中直接使用元组
5. **精准修改**：
   - 参数修改：找到对应变量修改数值
   - 结构修改：参照原有风格添加新的 BuildPart/BuildSketch 块
   - 删除部件：移除相关代码块和引用
6. **不使用 Markdown**：直接输出代码
7. **无注释/无中文标点**
{protection_text}{context_text}"""

        prompt = f"""现有代码:
{current_code}

用户修改请求:
{user_request}

请生成修改后的完整代码:"""

        response = self.client.generate(prompt, system_prompt)
        
        if response:
            # 清理响应
            response = response.replace("```python", "").replace("```", "")
            response = response.strip()
            
        return response
    
    def set_protected_lines(self, lines: Set[int]):
        """设置受保护的行号"""
        self.protected_lines = lines
    
    def add_protected_line(self, line: int):
        """添加受保护的行"""
        self.protected_lines.add(line)
    
    def clear_protection(self):
        """清除所有保护"""
        self.protected_lines.clear()
    
    def quick_fix(self, code: str, error_message: str) -> Optional[str]:
        """
        快速修复代码错误
        
        Args:
            code: 有错误的代码
            error_message: 错误信息
        
        Returns:
            修复后的代码
        """
        system_prompt = """你是一个 Python 代码调试专家。

任务：修复 build123d 代码中的错误。

常见错误类型：
1. SyntaxError: 语法错误，检查括号、缩进
2. NameError: 变量未定义，检查导入和变量名
3. TypeError: 类型错误，检查函数参数
4. AttributeError: 属性错误，检查 API 用法

输出修复后的完整代码，不要解释。"""

        prompt = f"""错误代码:
{code}

错误信息:
{error_message}

请修复:"""

        response = self.client.generate(prompt, system_prompt)
        
        if response:
            response = response.replace("```python", "").replace("```", "")
            response = response.strip()
            
        return response
    
    def optimize_code(self, code: str) -> str:
        """
        优化代码结构和性能
        
        Args:
            code: 原始代码
        
        Returns:
            优化后的代码
        """
        system_prompt = """你是一个 build123d 代码优化专家。

任务：优化代码，保持功能不变。

优化方向：
1. 合并可以合并的操作
2. 移除冗余代码
3. 改进变量命名
4. 优化几何运算顺序

输出优化后的完整代码，不要解释。"""

        prompt = f"""原始代码:
{code}

请优化:"""

        response = self.client.generate(prompt, system_prompt)
        
        if response:
            response = response.replace("```python", "").replace("```", "")
            response = response.strip()
            
        return response
