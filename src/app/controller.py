"""
应用控制器 - MVC 架构的 Controller
处理业务逻辑，连接 UI 和后端
"""
import os
import re
from typing import Optional, List, Dict, Any
from PySide6.QtCore import QObject, Signal, Slot, Property, QUrl

from src.generators.gen_full import FullGenerator
from src.generators.renderer import render_code, render_code_safe
from src.core.part_graph import PartGraph, Part
from src.core.plan_validator import PlanValidator
from src.core.diff_guard import DiffGuard
from src.utils.code_utils import extract_parameters, update_parameters
from src.app.workers import GenerationWorker, RenderWorker, QuickFixWorker, WorkerThread


class CADController(QObject):
    """
    CAD 应用控制器
    
    职责:
    1. 管理 AI 生成流程
    2. 处理代码编辑和渲染
    3. 管理部件图和历史
    4. 提供 QML 绑定
    """
    
    # 信号
    codeChanged = Signal(str)
    modelChanged = Signal(str)  # model_path
    planChanged = Signal(list)
    parametersChanged = Signal(list)
    historyChanged = Signal(list)
    
    statusMessage = Signal(str)
    errorMessage = Signal(str)
    progressChanged = Signal(float)
    busyChanged = Signal(bool)
    
    chatMessageAdded = Signal(str, str)  # role, content
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.generator = FullGenerator()
        self.part_graph = PartGraph()
        self.plan_validator = PlanValidator()
        self.diff_guard = DiffGuard()
        
        self._current_code = ""
        self._current_model_path = ""
        self._current_plan = []
        self._is_busy = False
        
        self._worker_thread = WorkerThread()
    
    # === Properties ===
    
    @Property(str, notify=codeChanged)
    def currentCode(self):
        return self._current_code
    
    @currentCode.setter
    def currentCode(self, value: str):
        if self._current_code != value:
            self._current_code = value
            self.codeChanged.emit(value)
    
    @Property(str, notify=modelChanged)
    def currentModelPath(self):
        return self._current_model_path
    
    @Property(bool, notify=busyChanged)
    def isBusy(self):
        return self._is_busy
    
    @isBusy.setter
    def isBusy(self, value: bool):
        if self._is_busy != value:
            self._is_busy = value
            self.busyChanged.emit(value)
    
    # === AI Generation ===
    
    @Slot(str)
    def generateFromRequest(self, request: str):
        """从用户请求生成 CAD 代码"""
        if self._is_busy:
            return
        
        self.isBusy = True
        self.chatMessageAdded.emit("User", request)
        self.statusMessage.emit("正在生成中...")
        
        worker = GenerationWorker(self.generator, request, self._current_code if self._current_code else None)
        worker.progress.connect(self._on_generation_progress)
        worker.finished.connect(self._on_generation_finished)
        worker.error.connect(self._on_generation_error)
        
        self._worker_thread.start(worker)
    
    @Slot(str)
    def refineCode(self, feedback: str):
        """根据用户反馈修改代码"""
        if self._is_busy or not self._current_code:
            return
        
        self.isBusy = True
        self.chatMessageAdded.emit("User", feedback)
        self.statusMessage.emit("正在修改中...")
        
        worker = GenerationWorker(self.generator, feedback, self._current_code)
        worker.progress.connect(self._on_generation_progress)
        worker.finished.connect(self._on_generation_finished)
        worker.error.connect(self._on_generation_error)
        
        self._worker_thread.start(worker)
    
    def _on_generation_progress(self, message: str, progress: float):
        """生成进度回调"""
        self.statusMessage.emit(message)
        self.progressChanged.emit(progress)
    
    def _on_generation_finished(self, message: str, code: str, model_path: str):
        """生成完成回调"""
        self.isBusy = False
        
        self._current_code = code
        self._current_model_path = model_path
        self._current_plan = self.generator.last_plan
        
        self.codeChanged.emit(code)
        self.modelChanged.emit(model_path)
        self.planChanged.emit(self._current_plan)
        
        # 更新参数列表
        params = self._extract_parameters_for_ui()
        self.parametersChanged.emit(params)
        
        # 更新部件图
        self.part_graph.from_plan(self._current_plan)
        
        # 设置原始代码用于 diff 追踪
        self.diff_guard.set_original(code)
        
        self.chatMessageAdded.emit("AI", message)
        self.statusMessage.emit("完成！")
        self.progressChanged.emit(1.0)
        
        # 刷新历史
        self._refresh_history()
    
    def _on_generation_error(self, error: str):
        """生成错误回调"""
        self.isBusy = False
        self.errorMessage.emit(error)
        self.chatMessageAdded.emit("Error", error)
    
    # === Code Editing ===
    
    @Slot(str)
    def setCode(self, code: str):
        """设置代码 (手动编辑)"""
        if code != self._current_code:
            # 追踪编辑
            self.diff_guard.track_edit(code)
            self._current_code = code
            self.codeChanged.emit(code)
    
    @Slot()
    def renderCurrentCode(self):
        """渲染当前代码"""
        if self._is_busy or not self._current_code:
            return
        
        self.isBusy = True
        self.statusMessage.emit("正在渲染...")
        
        worker = RenderWorker(self._current_code)
        worker.finished.connect(self._on_render_finished)
        worker.error.connect(self._on_render_error)
        
        self._worker_thread.start(worker)
    
    def _on_render_finished(self, model_path: str):
        """渲染完成"""
        self.isBusy = False
        self._current_model_path = model_path
        self.modelChanged.emit(model_path)
        self.statusMessage.emit("渲染完成！")
        
        # 记录手动编辑
        self.generator.log_manual_edit(self._current_code)
    
    def _on_render_error(self, error: str):
        """渲染错误"""
        self.isBusy = False
        self.errorMessage.emit(f"渲染失败: {error}")
        
        # 提供快速修复选项
        self.statusMessage.emit("渲染失败，可尝试自动修复")
    
    @Slot()
    def quickFixCode(self):
        """快速修复代码"""
        if self._is_busy or not self._current_code:
            return
        
        # 获取最后的错误信息
        # TODO: 从渲染器获取错误
        error_msg = "Unknown error"
        
        self.isBusy = True
        self.statusMessage.emit("正在修复...")
        
        worker = QuickFixWorker(self.generator, self._current_code, error_msg)
        worker.finished.connect(self._on_quickfix_finished)
        worker.error.connect(self._on_quickfix_error)
        
        self._worker_thread.start(worker)
    
    def _on_quickfix_finished(self, fixed_code: str):
        """修复完成"""
        self.isBusy = False
        self._current_code = fixed_code
        self.codeChanged.emit(fixed_code)
        self.statusMessage.emit("修复完成，请重新渲染")
    
    def _on_quickfix_error(self, error: str):
        """修复失败"""
        self.isBusy = False
        self.errorMessage.emit(f"自动修复失败: {error}")
    
    # === Parameter Editing ===
    
    @Slot(str, float)
    def updateParameter(self, name: str, value: float):
        """更新单个参数"""
        self._current_code = update_parameters(self._current_code, {name: value})
        self.codeChanged.emit(self._current_code)
        
        # 标记变量为受保护
        self.diff_guard.protect_variable(name)
    
    @Slot(list)
    def updateParameters(self, updates: list):
        """批量更新参数 [{name, value}, ...]"""
        params_dict = {item['name']: item['value'] for item in updates}
        self._current_code = update_parameters(self._current_code, params_dict)
        self.codeChanged.emit(self._current_code)
    
    def _extract_parameters_for_ui(self) -> list:
        """提取参数用于 UI 显示"""
        if not self._current_code:
            return []
        
        params = extract_parameters(self._current_code)
        result = []
        
        # 按部件分组
        for part in self._current_plan:
            part_name = part.get("name", "").replace(" ", "_").replace("-", "_")
            group = {"name": part_name, "params": []}
            
            for name, value in params.items():
                if name.startswith(part_name):
                    short_name = name[len(part_name):].lstrip('_')
                    group["params"].append({
                        "fullName": name,
                        "shortName": short_name or "value",
                        "value": value
                    })
            
            if group["params"]:
                result.append(group)
        
        # 全局参数
        global_params = []
        used_names = set()
        for group in result:
            for p in group["params"]:
                used_names.add(p["fullName"])
        
        for name, value in params.items():
            if name not in used_names:
                global_params.append({
                    "fullName": name,
                    "shortName": name,
                    "value": value
                })
        
        if global_params:
            result.append({"name": "Global", "params": global_params})
        
        return result
    
    # === History Management ===
    
    @Slot()
    def newSession(self):
        """新建会话"""
        self.generator.save_history()
        self.generator.clear_history()
        
        self._current_code = ""
        self._current_model_path = ""
        self._current_plan = []
        
        self.codeChanged.emit("")
        self.modelChanged.emit("")
        self.planChanged.emit([])
        self.parametersChanged.emit([])
        
        self.diff_guard.clear()
        self.part_graph = PartGraph()
        
        self._refresh_history()
        self.statusMessage.emit("新会话已创建")
    
    @Slot(str)
    def loadSession(self, filename: str):
        """加载历史会话"""
        history = self.generator.load_history(filename)
        if not history:
            self.errorMessage.emit("无法加载历史记录")
            return
        
        # 重放历史
        last_code = None
        for entry in history:
            if entry.get("code"):
                last_code = entry["code"]
        
        if last_code:
            self._current_code = last_code
            self.codeChanged.emit(last_code)
            
            # 尝试渲染
            self.renderCurrentCode()
            
            # 更新参数
            params = self._extract_parameters_for_ui()
            self.parametersChanged.emit(params)
        
        self.statusMessage.emit("历史记录已加载")
    
    @Slot(str)
    def deleteSession(self, filename: str):
        """删除历史会话"""
        if self.generator.delete_history(filename):
            self._refresh_history()
            self.statusMessage.emit("历史记录已删除")
        else:
            self.errorMessage.emit("删除失败")
    
    def _refresh_history(self):
        """刷新历史列表"""
        sessions = self.generator.get_history_list()
        self.historyChanged.emit(sessions)
    
    @Slot(result=list)
    def getHistoryList(self) -> list:
        """获取历史列表"""
        return self.generator.get_history_list()
    
    # === Part Management ===
    
    @Slot(str)
    def lockPart(self, name: str):
        """锁定部件"""
        self.part_graph.lock_part(name)
    
    @Slot(str)
    def unlockPart(self, name: str):
        """解锁部件"""
        self.part_graph.unlock_part(name)
    
    @Slot(str)
    def regeneratePart(self, name: str):
        """重新生成部件"""
        if self._is_busy:
            return
        
        try:
            new_code = self.generator.regenerate_part(name)
            # TODO: 合并到现有代码
            self.statusMessage.emit(f"部件 {name} 已重新生成")
        except Exception as e:
            self.errorMessage.emit(str(e))
    
    # === Validation ===
    
    @Slot(result=list)
    def validateCurrentPlan(self) -> list:
        """验证当前规划"""
        if not self._current_plan:
            return []
        
        is_valid, issues = self.plan_validator.validate(self._current_plan)
        return issues
    
    # === Export ===
    
    @Slot(str)
    def exportModel(self, path: str):
        """导出模型"""
        if not self._current_model_path or not os.path.exists(self._current_model_path):
            self.errorMessage.emit("没有可导出的模型")
            return
        
        import shutil
        try:
            shutil.copy2(self._current_model_path, path)
            self.statusMessage.emit(f"模型已导出到: {path}")
        except Exception as e:
            self.errorMessage.emit(f"导出失败: {e}")
    
    @Slot(str)
    def exportCode(self, path: str):
        """导出代码"""
        if not self._current_code:
            self.errorMessage.emit("没有可导出的代码")
            return
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._current_code)
            self.statusMessage.emit(f"代码已导出到: {path}")
        except Exception as e:
            self.errorMessage.emit(f"导出失败: {e}")
    
    # === Cleanup ===
    
    def cleanup(self):
        """清理资源"""
        self._worker_thread.stop()
        self.generator.save_history()
