"""
差异守护 - 保护用户手动编辑的代码不被 AI 覆盖
"""
import difflib
from typing import List, Tuple, Set, Dict, Optional
import re


class DiffGuard:
    """
    代码差异守护
    
    功能:
    1. 追踪用户手动编辑的行
    2. 在 AI 重新生成时保护这些行
    3. 智能合并 AI 生成的代码和用户编辑
    """
    
    def __init__(self):
        self.original_code: str = ""
        self.user_edits: Dict[int, str] = {}  # 行号 -> 用户编辑的内容
        self.protected_regions: List[Tuple[int, int]] = []  # [(start_line, end_line), ...]
        self.protected_variables: Set[str] = set()  # 受保护的变量名
    
    def set_original(self, code: str):
        """设置原始代码 (AI 生成的)"""
        self.original_code = code
        self.user_edits.clear()
        self.protected_regions.clear()
    
    def track_edit(self, edited_code: str):
        """
        追踪用户编辑
        比较原始代码和编辑后的代码，记录变化的行
        """
        original_lines = self.original_code.splitlines()
        edited_lines = edited_code.splitlines()
        
        # 使用 difflib 找出差异
        differ = difflib.Differ()
        diff = list(differ.compare(original_lines, edited_lines))
        
        line_num = 0
        for item in diff:
            if item.startswith('  '):  # 未变化
                line_num += 1
            elif item.startswith('+ '):  # 新增或修改
                self.user_edits[line_num] = item[2:]
                line_num += 1
            elif item.startswith('- '):  # 删除
                pass  # 删除的行不影响行号
        
        # 更新保护区域
        self._update_protected_regions()
    
    def _update_protected_regions(self):
        """更新受保护的区域"""
        self.protected_regions.clear()
        
        if not self.user_edits:
            return
        
        sorted_lines = sorted(self.user_edits.keys())
        start = sorted_lines[0]
        end = sorted_lines[0]
        
        for line in sorted_lines[1:]:
            if line <= end + 2:  # 合并相邻的编辑
                end = line
            else:
                self.protected_regions.append((start, end))
                start = line
                end = line
        
        self.protected_regions.append((start, end))
    
    def protect_variable(self, var_name: str):
        """保护特定变量不被修改"""
        self.protected_variables.add(var_name)
    
    def unprotect_variable(self, var_name: str):
        """取消保护变量"""
        self.protected_variables.discard(var_name)
    
    def merge_code(self, new_code: str) -> str:
        """
        合并 AI 新生成的代码和用户编辑
        
        策略:
        1. 保护用户编辑的行
        2. 保护指定的变量值
        3. 其他部分使用新代码
        """
        if not self.user_edits and not self.protected_variables:
            return new_code
        
        new_lines = new_code.splitlines()
        result_lines = new_lines.copy()
        
        # 1. 恢复用户编辑的行
        for line_num, content in self.user_edits.items():
            if line_num < len(result_lines):
                # 检查是否是参数行
                if self._is_parameter_line(content):
                    # 保留用户设置的参数值
                    result_lines[line_num] = content
        
        # 2. 保护指定的变量
        if self.protected_variables:
            result_lines = self._protect_variables(result_lines)
        
        return '\n'.join(result_lines)
    
    def _is_parameter_line(self, line: str) -> bool:
        """检查是否是参数定义行"""
        pattern = r'^\s*[a-zA-Z_]\w*\s*=\s*[\d.]+\s*$'
        return bool(re.match(pattern, line))
    
    def _protect_variables(self, lines: List[str]) -> List[str]:
        """保护指定变量的值"""
        result = []
        
        for line in lines:
            protected = False
            
            for var_name in self.protected_variables:
                pattern = rf'^\s*({re.escape(var_name)})\s*=\s*[\d.]+\s*$'
                if re.match(pattern, line):
                    # 从用户编辑中找到该变量的值
                    for edit_line in self.user_edits.values():
                        if re.match(pattern, edit_line):
                            result.append(edit_line)
                            protected = True
                            break
                    break
            
            if not protected:
                result.append(line)
        
        return result
    
    def get_edit_summary(self) -> str:
        """获取编辑摘要"""
        if not self.user_edits:
            return "No user edits tracked"
        
        summary = f"User edited {len(self.user_edits)} lines:\n"
        for line_num, content in sorted(self.user_edits.items())[:5]:
            summary += f"  Line {line_num}: {content[:50]}...\n"
        
        if len(self.user_edits) > 5:
            summary += f"  ... and {len(self.user_edits) - 5} more\n"
        
        return summary
    
    def get_protected_info(self) -> Dict:
        """获取保护信息"""
        return {
            "protected_regions": self.protected_regions,
            "protected_variables": list(self.protected_variables),
            "user_edit_count": len(self.user_edits)
        }
    
    def clear(self):
        """清除所有追踪"""
        self.original_code = ""
        self.user_edits.clear()
        self.protected_regions.clear()
        self.protected_variables.clear()
