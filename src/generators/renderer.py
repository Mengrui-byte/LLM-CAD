"""
渲染器 - 执行 build123d 代码并生成 3D 模型
优化：
- 预加载 build123d 避免重复导入
- 降低 STL 导出精度加速渲染
- 代码哈希缓存避免重复渲染
"""
import os
import sys
import time
import hashlib
import traceback
from typing import Optional, Tuple, Dict, Any

# ============ 渲染配置 ============
RENDER_CONFIG = {
    "linear_deflection": 0.1,    # STL 精度 (mm)，值越大越快，默认 0.01
    "angular_deflection": 0.2,   # 角度精度 (rad)，值越大越快，默认 0.1
    "use_cache": True,           # 启用缓存
    "preview_mode": False,       # 预览模式（更低精度）
}

# 代码哈希缓存
_CODE_CACHE: Dict[str, str] = {}  # hash -> model_path

# ============ 预加载 build123d (关键优化) ============
_PRELOADED_GLOBALS = None

def _get_preloaded_globals():
    """获取预加载的全局命名空间（含 build123d）"""
    global _PRELOADED_GLOBALS
    
    if _PRELOADED_GLOBALS is None:
        print("[Renderer] Preloading build123d (first time only)...")
        start = time.time()
        
        _PRELOADED_GLOBALS = {"__builtins__": __builtins__}
        
        try:
            # 预加载 build123d 和 math
            exec("from build123d import *", _PRELOADED_GLOBALS)
            exec("from math import *", _PRELOADED_GLOBALS)
            
            # 尝试导入导出函数
            try:
                exec("from build123d import export_stl, export_step", _PRELOADED_GLOBALS)
            except:
                pass
            
            print(f"[Renderer] Preload complete in {time.time() - start:.2f}s")
        except ImportError as e:
            print(f"[Renderer] Warning: build123d not available: {e}")
    
    # 返回副本避免污染
    return _PRELOADED_GLOBALS.copy()


def render_code(
    code_str: str, 
    output_dir: str = "output",
    timeout: int = 60,
    use_cache: bool = True,
    preview_mode: bool = False
) -> Optional[str]:
    """
    执行 CAD 脚本并返回输出文件路径
    
    Args:
        code_str: build123d Python 代码
        output_dir: 输出目录
        timeout: 超时时间 (秒)
        use_cache: 是否使用缓存（代码相同时跳过渲染）
        preview_mode: 预览模式（更低精度，更快）
    
    Returns:
        成功返回模型文件路径，失败返回 None
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)
    
    # 清理代码
    code_str = _clean_code_for_exec(code_str)
    code_str = _strip_imports(code_str)
    
    # 检查缓存
    code_hash = hashlib.md5(code_str.encode()).hexdigest()[:16]
    stl_path = os.path.join(output_dir, "model.stl")
    
    if use_cache and RENDER_CONFIG["use_cache"]:
        if code_hash in _CODE_CACHE and os.path.exists(_CODE_CACHE[code_hash]):
            print(f"[Renderer] Cache hit, skipping render")
            return _CODE_CACHE[code_hash]
    
    print("[Renderer] Executing CAD script...")
    
    # 保存脚本用于调试
    script_path = os.path.join(output_dir, "last_generated_script.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code_str)
    
    # 注入优化后的导出代码
    code_str = _inject_optimized_export(code_str, output_dir, preview_mode)
    
    # 使用预加载的命名空间
    exec_globals = _get_preloaded_globals()
    
    try:
        exec(code_str, exec_globals)
        
        # 检查输出文件
        step_path = os.path.join(output_dir, "model.step")
        
        elapsed = time.time() - start
        
        if os.path.exists(stl_path):
            print(f"[Renderer] Success in {elapsed:.2f}s: {stl_path}")
            _CODE_CACHE[code_hash] = stl_path
            return stl_path
        elif os.path.exists(step_path):
            print(f"[Renderer] Success in {elapsed:.2f}s: {step_path}")
            _CODE_CACHE[code_hash] = step_path
            return step_path
        else:
            print("[Renderer] Warning: No output file generated")
            return None
            
    except Exception as e:
        print(f"[Renderer] Execution error: {e}")
        traceback.print_exc()
        return None


def _inject_optimized_export(code: str, output_dir: str, preview_mode: bool = False) -> str:
    """注入优化后的导出代码（降低精度加速）"""
    # 移除现有的 export 相关代码块（包括 try-except）
    lines = code.splitlines()
    filtered = []
    skip_until_dedent = False
    skip_indent_level = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 检测 export 相关的 try 块开始
        if stripped == 'try:' and i + 1 < len(lines):
            # 向前看是否是 export 相关的 try 块
            next_lines = '\n'.join(lines[i:i+10])
            if 'export_stl' in next_lines or 'export_step' in next_lines:
                # 跳过整个 try-except 块
                indent_level = len(line) - len(line.lstrip())
                i += 1
                while i < len(lines):
                    curr_line = lines[i]
                    curr_stripped = curr_line.strip()
                    if curr_stripped and not curr_stripped.startswith('#'):
                        curr_indent = len(curr_line) - len(curr_line.lstrip())
                        # 回到同级或更低缩进，且不是 except/finally
                        if curr_indent <= indent_level and not curr_stripped.startswith(('except', 'finally')):
                            break
                    i += 1
                continue
        
        # 跳过单独的 export 调用
        if 'export_stl' in stripped or 'export_step' in stripped:
            i += 1
            continue
        
        filtered.append(line)
        i += 1
    
    code = '\n'.join(filtered)
    
    # 根据模式选择精度
    if preview_mode:
        linear = 0.5   # 预览模式：低精度
        angular = 0.5
    else:
        linear = RENDER_CONFIG["linear_deflection"]
        angular = RENDER_CONFIG["angular_deflection"]
    
    # 添加优化后的导出代码
    export_code = f'''
# === Optimized Export ===
import os as _os
_os.makedirs("{output_dir}", exist_ok=True)

# 查找要导出的对象
_export_obj = None
if 'compound' in dir() and compound is not None:
    _export_obj = compound
elif 'part_obj' in dir() and hasattr(part_obj, 'part'):
    _export_obj = part_obj.part
elif 'assembly' in dir() and assembly is not None:
    _export_obj = assembly

if _export_obj is not None:
    try:
        # 使用降低的精度加速导出
        export_stl(
            _export_obj, 
            "{output_dir}/model.stl",
            linear_deflection={linear},
            angular_deflection={angular}
        )
    except TypeError:
        # 旧版本 build123d 不支持 deflection 参数
        export_stl(_export_obj, "{output_dir}/model.stl")
'''
    return code + export_code


def _strip_imports(code: str) -> str:
    """移除已预加载的 import 语句，正确处理 try/except 块"""
    lines = code.splitlines()
    result = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 检测 try: 块开始
        if stripped == "try:":
            # 向前看是否整个 try 块只包含我们要移除的 import
            j = i + 1
            block_lines = []
            in_try_body = True
            indent_level = len(line) - len(line.lstrip())
            
            while j < len(lines):
                next_line = lines[j]
                next_stripped = next_line.strip()
                
                if not next_stripped:  # 空行
                    block_lines.append(next_line)
                    j += 1
                    continue
                
                next_indent = len(next_line) - len(next_line.lstrip())
                
                # except/finally 表示 try 块结束
                if next_indent == indent_level and (next_stripped.startswith("except") or next_stripped.startswith("finally")):
                    in_try_body = False
                    block_lines.append(next_line)
                    j += 1
                    continue
                
                # 回到同级或更低缩进表示整个 try/except 结束
                if next_indent <= indent_level and not in_try_body:
                    break
                
                block_lines.append(next_line)
                j += 1
            
            # 检查 try 块内容是否只有 import 和 pass
            try_content = "\n".join(block_lines)
            is_import_only = all(
                l.strip() == "" or
                l.strip().startswith("from build123d import") or
                l.strip().startswith("from math import") or
                l.strip().startswith("import ") or
                l.strip() == "pass" or
                l.strip().startswith("except") or
                l.strip().startswith("finally")
                for l in block_lines
            )
            
            if is_import_only:
                # 跳过整个 try/except 块
                i = j
                continue
            else:
                # 保留 try 块，但移除其中的 import
                result.append(line)
                i += 1
                continue
        
        # 跳过单独的 import 语句
        if stripped.startswith("from build123d import"):
            i += 1
            continue
        if stripped.startswith("from math import"):
            i += 1
            continue
        if stripped.startswith("import build123d"):
            i += 1
            continue
        if stripped.startswith("import math"):
            i += 1
            continue
        
        result.append(line)
        i += 1
    
    return "\n".join(result)


def render_code_safe(
    code_str: str,
    output_dir: str = "output",
    preview_mode: bool = False
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    安全执行代码，返回详细结果
    
    Returns:
        (success, model_path, error_message)
    """
    start = time.time()
    os.makedirs(output_dir, exist_ok=True)
    code_str = _clean_code_for_exec(code_str)
    code_str = _strip_imports(code_str)
    
    # 保存脚本
    script_path = os.path.join(output_dir, "last_generated_script.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code_str)
    
    try:
        # 首先进行语法检查
        compile(code_str, '<cad_script>', 'exec')
    except SyntaxError as e:
        return False, None, f"SyntaxError at line {e.lineno}: {e.msg}"
    
    # 注入优化后的导出
    code_str = _inject_optimized_export(code_str, output_dir, preview_mode)
    
    # 使用预加载的命名空间
    exec_globals = _get_preloaded_globals()
    
    try:
        exec(code_str, exec_globals)
        
        stl_path = os.path.join(output_dir, "model.stl")
        step_path = os.path.join(output_dir, "model.step")
        
        elapsed = time.time() - start
        
        if os.path.exists(stl_path):
            print(f"[Renderer] Done in {elapsed:.2f}s")
            return True, stl_path, None
        elif os.path.exists(step_path):
            print(f"[Renderer] Done in {elapsed:.2f}s")
            return True, step_path, None
        else:
            return False, None, "No output file generated"
            
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        return False, None, error_msg


def set_render_quality(quality: str = "normal"):
    """
    设置渲染质量
    
    Args:
        quality: "preview" (快速预览), "normal" (默认), "high" (高精度)
    """
    global RENDER_CONFIG
    
    presets = {
        "preview": {"linear_deflection": 0.5, "angular_deflection": 0.5},
        "normal":  {"linear_deflection": 0.1, "angular_deflection": 0.2},
        "high":    {"linear_deflection": 0.01, "angular_deflection": 0.05},
    }
    
    if quality in presets:
        RENDER_CONFIG.update(presets[quality])
        print(f"[Renderer] Quality set to: {quality}")
    else:
        print(f"[Renderer] Unknown quality: {quality}, use preview/normal/high")


def clear_cache():
    """清除渲染缓存"""
    global _CODE_CACHE
    _CODE_CACHE.clear()
    print("[Renderer] Cache cleared")


def preload():
    """
    应用启动时调用，提前预加载 build123d
    这样第一次渲染就不会等待导入
    """
    _get_preloaded_globals()


def validate_code(code_str: str) -> Tuple[bool, Optional[str]]:
    """
    验证代码语法 (不执行)
    
    Returns:
        (is_valid, error_message)
    """
    try:
        compile(code_str, '<validation>', 'exec')
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def _clean_code_for_exec(code: str) -> str:
    """清理代码用于执行"""
    # 修复特殊引号
    replacements = {
        '"': '"', '"': '"',
        ''': "'", ''': "'",
        '，': ',', '。': '.',
        '（': '(', '）': ')',
    }
    for old, new in replacements.items():
        code = code.replace(old, new)
    return code


def get_model_info(model_path: str) -> Dict[str, Any]:
    """
    获取模型文件信息
    
    Returns:
        包含文件大小、顶点数等信息的字典
    """
    info = {
        "path": model_path,
        "exists": os.path.exists(model_path),
        "size_bytes": 0,
        "format": "",
    }
    
    if not info["exists"]:
        return info
    
    info["size_bytes"] = os.path.getsize(model_path)
    info["format"] = os.path.splitext(model_path)[1].lower()
    
    # 如果安装了 trimesh，获取更多信息
    try:
        import trimesh
        mesh = trimesh.load(model_path)
        info["vertices"] = len(mesh.vertices)
        info["faces"] = len(mesh.faces)
        info["bounds"] = mesh.bounds.tolist()
    except ImportError:
        pass
    except Exception as e:
        info["mesh_error"] = str(e)
    
    return info
