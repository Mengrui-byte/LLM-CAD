import subprocess
import os
import shutil

def render_scad(scad_file: str = "model.scad", output_file: str = "model.png") -> str:
    """
    调用 OpenSCAD 命令行渲染图片。
    如果未安装 OpenSCAD，返回 None。
    """
    if not shutil.which("openscad"):
        print("Warning: OpenSCAD binary not found. Skipping rendering.")
        return None
        
    try:
        # --imgsize=1024,1024 --camera=0,0,0,60,0,25,500
        # 简化参数
        cmd = ["openscad", "-o", output_file, "--imgsize=800,600", "--autocenter", "--viewall", scad_file]
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(output_file):
            return output_file
    except subprocess.CalledProcessError as e:
        print(f"Rendering failed: {e}")
        return None
    return None
