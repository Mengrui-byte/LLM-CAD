"""
代码处理工具
- 清洗代码
- 参数提取
- 代码验证
"""
import re
from typing import Dict, List, Tuple, Optional


def clean_code(code: str) -> str:
    """清洗代码：移除 Markdown、修正标点"""
    if not code:
        return ""
    
    # 移除 markdown 代码块标记
    code = re.sub(r'```python\s*', '', code)
    code = re.sub(r'```\s*', '', code)
    
    # 修正中文标点
    replacements = {
        '，': ',', '。': '.', '（': '(', '）': ')',
        '：': ':', '；': ';', '"': '"', '"': '"',
        ''': "'", ''': "'"
    }
    for cn, en in replacements.items():
        code = code.replace(cn, en)
    
    # 移除空行过多的情况
    code = re.sub(r'\n{3,}', '\n\n', code)
    
    return code.strip()


def extract_parameters(code: str) -> Dict[str, float]:
    """
    从代码中提取参数化变量
    格式: var_name = number
    """
    pattern = re.compile(r'^\s*([a-zA-Z_]\w*)\s*=\s*([\d.]+)\s*$', re.MULTILINE)
    matches = pattern.findall(code)
    return {name: float(value) for name, value in matches}


def extract_parameters_grouped(code: str) -> Dict[str, Dict[str, float]]:
    """
    提取参数并按部件分组
    假设变量命名规范: {part_name}_{param_name}
    """
    params = extract_parameters(code)
    grouped = {}
    
    for name, value in params.items():
        # 尝试按下划线分割找到部件前缀
        parts = name.rsplit('_', 1)
        if len(parts) == 2 and not parts[1].isdigit():
            # 检查是否是 xxx_loc_x 这样的三段式
            prefix_parts = name.rsplit('_', 2)
            if len(prefix_parts) == 3 and prefix_parts[1] == 'loc':
                group_name = prefix_parts[0]
                param_name = f"loc_{prefix_parts[2]}"
            else:
                group_name = parts[0]
                param_name = parts[1]
        else:
            group_name = "global"
            param_name = name
            
        if group_name not in grouped:
            grouped[group_name] = {}
        grouped[group_name][param_name] = value
    
    return grouped


def update_parameter(code: str, var_name: str, new_value: float) -> str:
    """更新代码中的单个参数值"""
    pattern = re.compile(
        r'^(\s*' + re.escape(var_name) + r'\s*=\s*)([\d.]+)(\s*)$',
        re.MULTILINE
    )
    return pattern.sub(rf'\g<1>{new_value}\g<3>', code)


def update_parameters(code: str, updates: Dict[str, float]) -> str:
    """批量更新参数"""
    for name, value in updates.items():
        code = update_parameter(code, name, value)
    return code


def validate_build123d_code(code: str) -> Tuple[bool, Optional[str]]:
    """
    验证 build123d 代码的基本语法
    返回: (is_valid, error_message)
    """
    # 检查必要的导入
    if 'from build123d import' not in code and 'import build123d' not in code:
        return False, "Missing build123d import"
    
    # 检查是否有 BuildPart/BuildSketch
    if 'BuildPart' not in code and 'BuildSketch' not in code:
        return False, "No BuildPart or BuildSketch found"
    
    # 检查禁用的模式
    if 'Pos(' in code:
        return False, "Pos() is deprecated, use Locations with tuple instead"
    
    # 尝试编译检查语法
    try:
        compile(code, '<string>', 'exec')
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    
    return True, None


def inject_exports(code: str, output_dir: str = "output") -> str:
    """确保代码包含导出逻辑"""
    if 'export_stl' in code or 'export_step' in code:
        return code
    
    export_code = f'''
# Export
import os
os.makedirs("{output_dir}", exist_ok=True)
try:
    from build123d import export_stl, export_step
    if 'compound' in dir():
        export_stl(compound, "{output_dir}/model.stl")
    elif 'part_obj' in dir():
        export_stl(part_obj.part, "{output_dir}/model.stl")
except Exception as e:
    print(f"Export failed: {{e}}")
'''
    return code + export_code


def extract_part_names(code: str) -> List[str]:
    """从代码中提取所有部件名称"""
    # 查找 BuildPart() as xxx_part 模式
    pattern = re.compile(r'BuildPart\(\)\s*as\s+(\w+)')
    return pattern.findall(code)


def fix_common_errors(code: str) -> str:
    """
    修复常见的 build123d 代码错误
    """
    if not code:
        return code
    
    lines = code.splitlines()
    fixed_lines = []
    
    for i, line in enumerate(lines):
        fixed_line = line
        
        # 修复: BuildSketch(path @ 0) -> BuildSketch(Plane.XY)
        # 这是一个常见错误，path @ 0 返回 Vector 而不是 Plane
        if 'BuildSketch(' in line and '@' in line:
            # 检测 BuildSketch(xxx @ 0) 或 BuildSketch(xxx @ 1) 模式
            match = re.search(r'BuildSketch\s*\(\s*(\w+)\s*@\s*(\d+)\s*\)', line)
            if match:
                var_name = match.group(1)
                position = match.group(2)
                # 替换为 Plane.XY 或 Plane.XY.offset()
                if position == '0':
                    fixed_line = re.sub(
                        r'BuildSketch\s*\(\s*\w+\s*@\s*0\s*\)',
                        'BuildSketch(Plane.XY)',
                        line
                    )
                else:
                    # 对于 @ 1，假设是在某个高度
                    fixed_line = re.sub(
                        r'BuildSketch\s*\(\s*\w+\s*@\s*1\s*\)',
                        'BuildSketch(Plane.XY.offset(50))',  # 默认偏移
                        line
                    )
        
        # 修复: Pos() -> Locations()
        if 'Pos(' in line:
            fixed_line = re.sub(r'Pos\s*\(', 'Locations((', line)
            # 确保括号闭合
            if fixed_line.count('(') > fixed_line.count(')'):
                fixed_line = fixed_line.rstrip() + ')'
        
        fixed_lines.append(fixed_line)
    
    return '\n'.join(fixed_lines)


def fix_and_clean_code(code: str) -> str:
    """清洗并修复代码"""
    code = clean_code(code)
    code = fix_common_errors(code)
    return code
