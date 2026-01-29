"""
AI CAD Architect - 主入口
类似 Cursor 的 AI 辅助 CAD 建模软件
"""
import sys
import os
import threading

# 确保项目根目录在 Python 路径中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    """主入口 - 直接使用 PyQt5 界面"""
    print("[Info] Starting AI CAD Architect...")
    
    # 后台预加载 build123d（加速首次渲染）
    def preload_task():
        try:
            from src.generators.renderer import preload
            preload()
        except Exception as e:
            print(f"[Warning] Preload failed: {e}")
    
    threading.Thread(target=preload_task, daemon=True).start()
    
    from src.app.window import start_pyqt5_app
    return start_pyqt5_app()


if __name__ == "__main__":
    # macOS 需要使用 spawn 方式启动子进程（必须在 main 之前设置）
    import multiprocessing as mp
    try:
        mp.set_start_method('spawn')
    except RuntimeError:
        pass  # 已经设置过了
    
    sys.exit(main())
