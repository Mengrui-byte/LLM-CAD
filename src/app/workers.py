"""
后台工作线程
处理 AI 生成和渲染等耗时操作
"""
from PySide6.QtCore import QObject, Signal, QThread, QRunnable, Slot
from typing import Optional, Callable, Any


class GenerationWorker(QObject):
    """AI 代码生成工作线程"""
    
    # 信号
    started = Signal()
    progress = Signal(str, float)  # message, progress (0-1)
    finished = Signal(str, str, str)  # message, code, model_path
    error = Signal(str)
    
    def __init__(self, generator, request: str, current_code: str = None):
        super().__init__()
        self.generator = generator
        self.request = request
        self.current_code = current_code
        self._is_cancelled = False
    
    @Slot()
    def run(self):
        """执行生成任务"""
        self.started.emit()
        
        try:
            # 设置进度回调
            self.generator.on_progress = self._on_progress
            
            if not self.current_code:
                # 全新生成
                new_code = self.generator.generate_full_code(self.request)
                msg = "模型生成完毕！"
            else:
                # 修改现有代码
                new_code = self.generator.refine_code(self.current_code, self.request)
                msg = "模型已修改！"
            
            if self._is_cancelled:
                return
            
            # 渲染
            self.progress.emit("Rendering...", 0.95)
            from src.generators.renderer import render_code
            model_path = render_code(new_code)
            
            if model_path:
                self.finished.emit(msg, new_code, model_path)
            else:
                self.error.emit("代码生成成功，但渲染失败。请检查代码。")
                
        except Exception as e:
            self.error.emit(str(e))
    
    def _on_progress(self, message: str, progress: float):
        """进度回调"""
        self.progress.emit(message, progress)
    
    def cancel(self):
        """取消任务"""
        self._is_cancelled = True


class RenderWorker(QObject):
    """渲染工作线程"""
    
    started = Signal()
    finished = Signal(str)  # model_path
    error = Signal(str)
    
    def __init__(self, code: str):
        super().__init__()
        self.code = code
    
    @Slot()
    def run(self):
        """执行渲染"""
        self.started.emit()
        
        try:
            from src.generators.renderer import render_code_safe
            success, model_path, error_msg = render_code_safe(self.code)
            
            if success and model_path:
                self.finished.emit(model_path)
            else:
                self.error.emit(error_msg or "Render failed")
                
        except Exception as e:
            self.error.emit(str(e))


class QuickFixWorker(QObject):
    """快速修复工作线程"""
    
    finished = Signal(str)  # fixed_code
    error = Signal(str)
    
    def __init__(self, generator, code: str, error_msg: str):
        super().__init__()
        self.generator = generator
        self.code = code
        self.error_msg = error_msg
    
    @Slot()
    def run(self):
        try:
            fixed_code = self.generator.quick_fix(self.code, self.error_msg)
            if fixed_code:
                self.finished.emit(fixed_code)
            else:
                self.error.emit("Quick fix failed")
        except Exception as e:
            self.error.emit(str(e))


class WorkerThread:
    """工作线程管理器"""
    
    def __init__(self):
        self.thread: Optional[QThread] = None
        self.worker: Optional[QObject] = None
    
    def start(self, worker: QObject):
        """启动工作线程"""
        self.stop()  # 先停止之前的
        
        self.thread = QThread()
        self.worker = worker
        
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        
        # 自动清理
        if hasattr(worker, 'finished'):
            worker.finished.connect(self.thread.quit)
        if hasattr(worker, 'error'):
            worker.error.connect(self.thread.quit)
        
        self.thread.finished.connect(self._cleanup)
        
        self.thread.start()
    
    def stop(self):
        """停止工作线程"""
        if self.worker and hasattr(self.worker, 'cancel'):
            self.worker.cancel()
        
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(5000)  # 等待最多 5 秒
    
    def _cleanup(self):
        """清理"""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.thread:
            self.thread.deleteLater()
            self.thread = None
    
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.thread is not None and self.thread.isRunning()
