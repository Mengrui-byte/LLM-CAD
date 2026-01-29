"""
PyQt5 回退窗口
当 QML 不可用时使用
"""
import sys
import os
import re
import time
import threading
import multiprocessing as mp
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QSplitter, QMessageBox,
    QProgressBar, QTabWidget, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
    QListWidget, QListWidgetItem, QFileDialog, QMenu, QAction, QCheckBox
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

# 尝试导入 3D 渲染库
HAS_PYVISTA = False
try:
    import pyvista as pv
    # 设置 pyvista 使用 PyQt5 后端
    pv.set_jupyter_backend(None)
    from pyvistaqt import QtInteractor
    HAS_PYVISTA = True
except ImportError as e:
    print(f"[Warning] PyVista not available: {e}")
except Exception as e:
    print(f"[Warning] PyVista init error: {e}")

# 确保项目路径正确
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.generators.gen_full import FullGenerator
from src.generators.renderer import render_code


def _render_in_process(code: str, preview_mode: bool, result_queue: mp.Queue):
    """
    在独立进程中执行渲染（可被 terminate）
    
    Args:
        code: build123d 代码
        preview_mode: 是否快速预览模式
        result_queue: 用于返回结果的队列
    """
    try:
        # 必须在进程内导入，避免 pickle 问题
        from src.generators.renderer import render_code_safe
        
        success, model_path, error_msg = render_code_safe(code, preview_mode=preview_mode)
        
        result_queue.put({
            'success': success,
            'model_path': model_path,
            'error': error_msg
        })
    except Exception as e:
        result_queue.put({
            'success': False,
            'model_path': None,
            'error': str(e)
        })


class AIWorker(QObject):
    """AI 代码生成工作线程（不含渲染）"""
    finished = pyqtSignal(str, str)  # msg, code
    error = pyqtSignal(str)
    progress = pyqtSignal(str, str)  # message, level (INFO/STEP/ERROR)
    plan_ready = pyqtSignal(list)    # plan data after planning phase
    
    def __init__(self, generator, text, current_code):
        super().__init__()
        self.generator = generator
        self.text = text
        self.current_code = current_code
    
    def run(self):
        try:
            # 设置进度回调
            def on_progress(msg, p):
                level = "STEP" if "Processing" in msg or "Generating" in msg else "INFO"
                self.progress.emit(msg, level)
            
            # 设置规划完成回调
            def on_plan_ready(plan):
                self.plan_ready.emit(plan)
            
            self.generator.on_progress = on_progress
            self.generator.on_plan_ready = on_plan_ready
            
            self.progress.emit(f"用户请求: {self.text[:50]}...", "INFO")
            
            if not self.current_code:
                self.progress.emit("开始规划部件...", "STEP")
                new_code = self.generator.generate_full_code(self.text)
                msg = "代码生成完毕！点击「渲染」查看模型。"
            else:
                self.progress.emit("开始修改代码...", "STEP")
                new_code = self.generator.refine_code(self.current_code, self.text)
                msg = "代码已修改！点击「渲染」更新模型。"
            
            self.progress.emit("代码生成完成", "SUCCESS")
            self.finished.emit(msg, new_code)
        except Exception as e:
            self.progress.emit(f"生成错误: {str(e)}", "ERROR")
            self.error.emit(str(e))


class CADWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI CAD Architect")
        self.resize(1600, 900)
        
        self.generator = FullGenerator()
        self.current_code = None
        self.current_model_path = None
        
        # 同步锁，防止循环触发
        self._syncing = False
        
        # 工作线程引用
        self._gen_thread = None
        self._render_thread = None
        
        self._setup_ui()
        self._setup_menu()
        
        self.append_chat("System", "欢迎使用 AI CAD Architect！请输入描述开始建模。")
        self.refresh_history()
    
    def _setup_ui(self):
        """设置 UI"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # 主垂直分割：上方内容 + 下方输出
        self.main_vsplitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(self.main_vsplitter)
        
        # 上方内容区域
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        top_layout.addWidget(self.splitter)
        
        # 左侧: 对话
        self._create_left_panel()
        
        # 中间: 代码和参数
        self._create_middle_panel()
        
        # 右侧: 3D 预览
        self._create_right_panel()
        
        # 最右: 历史
        self._create_history_panel()
        
        self.splitter.setSizes([300, 500, 700, 200])
        
        self.main_vsplitter.addWidget(top_widget)
        
        # 下方: 输出/日志面板 (像 IDE)
        self._create_output_panel()
        
        self.main_vsplitter.setSizes([700, 200])
    
    def _create_left_panel(self):
        """创建左侧面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        layout.addWidget(QLabel("对话记录:"))
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)
        
        layout.addWidget(QLabel("指令:"))
        
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("例如: 做一个圆桌...")
        self.input_box.returnPressed.connect(self.start_generation)
        layout.addWidget(self.input_box)
        
        btn_layout = QHBoxLayout()
        self.send_btn = QPushButton("发送 / 生成")
        self.send_btn.clicked.connect(self.start_generation)
        self.clear_btn = QPushButton("新建会话")
        self.clear_btn.clicked.connect(self.new_session)
        btn_layout.addWidget(self.send_btn)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)
        
        # 渲染选项
        options_layout = QHBoxLayout()
        self.auto_render_cb = QCheckBox("生成后自动渲染")
        self.auto_render_cb.setChecked(False)
        self.preview_mode_cb = QCheckBox("快速预览")
        self.preview_mode_cb.setChecked(True)  # 默认开启快速预览
        self.preview_mode_cb.setToolTip("降低渲染精度，提高速度 (约 3-5x)")
        options_layout.addWidget(self.auto_render_cb)
        options_layout.addWidget(self.preview_mode_cb)
        layout.addLayout(options_layout)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        self.splitter.addWidget(panel)
    
    def _create_middle_panel(self):
        """创建中间面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # 代码标签
        code_widget = QWidget()
        code_layout = QVBoxLayout(code_widget)
        
        self.code_display = QTextEdit()
        self.code_display.setFont(QFont("Courier New", 11))
        # 代码编辑 → 参数同步
        self.code_display.textChanged.connect(self._on_code_changed)
        code_layout.addWidget(self.code_display)
        
        code_btn_layout = QHBoxLayout()
        render_btn = QPushButton("渲染代码")
        render_btn.clicked.connect(self.render_code_manual)
        render_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.cancel_render_btn = QPushButton("取消")
        self.cancel_render_btn.clicked.connect(self.cancel_render)
        self.cancel_render_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.cancel_render_btn.setEnabled(False)
        copy_btn = QPushButton("复制代码")
        copy_btn.clicked.connect(self.copy_code)
        code_btn_layout.addWidget(render_btn)
        code_btn_layout.addWidget(self.cancel_render_btn)
        code_btn_layout.addWidget(copy_btn)
        code_layout.addLayout(code_btn_layout)
        
        self.tabs.addTab(code_widget, "代码编辑")
        
        # 参数标签
        param_widget = QWidget()
        param_layout = QVBoxLayout(param_widget)
        
        self.param_tree = QTreeWidget()
        self.param_tree.setHeaderLabels(["参数名", "数值"])
        self.param_tree.setColumnWidth(0, 200)
        # 参数编辑 → 代码同步
        self.param_tree.itemChanged.connect(self._on_param_changed)
        param_layout.addWidget(self.param_tree)
        
        apply_btn = QPushButton("渲染")
        apply_btn.clicked.connect(self.render_code_manual)
        apply_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        param_layout.addWidget(apply_btn)
        
        self.tabs.addTab(param_widget, "参数编辑")
        
        self.splitter.addWidget(panel)
    
    def _create_right_panel(self):
        """创建右侧 3D 面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        layout.addWidget(QLabel("3D 预览"))
        
        self.plotter = None
        if HAS_PYVISTA:
            try:
                self.plotter = QtInteractor(panel)
                self.plotter.set_background('white')
                self.plotter.add_axes()
                layout.addWidget(self.plotter.interactor)
            except Exception as e:
                print(f"[Warning] Failed to create 3D viewer: {e}")
                self.plotter = None
        
        if self.plotter is None:
            placeholder = QLabel("3D 预览不可用\n模型文件已保存到 output/model.stl")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("background-color: #f0f0f0; padding: 50px;")
            layout.addWidget(placeholder)
        
        export_btn = QPushButton("导出模型 (STL)")
        export_btn.clicked.connect(self.export_model)
        layout.addWidget(export_btn)
        
        self.splitter.addWidget(panel)
    
    def _create_history_panel(self):
        """创建历史面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        layout.addWidget(QLabel("历史记录"))
        
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.load_history_session)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._show_history_menu)
        layout.addWidget(self.history_list)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_history)
        layout.addWidget(refresh_btn)
        
        self.splitter.addWidget(panel)
    
    def _create_output_panel(self):
        """创建输出/日志面板 (类似 IDE 的终端)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题栏
        header = QHBoxLayout()
        header.addWidget(QLabel("📋 输出日志"))
        
        clear_btn = QPushButton("清空")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self.clear_output)
        header.addStretch()
        header.addWidget(clear_btn)
        layout.addLayout(header)
        
        # 输出文本框
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setFont(QFont("Courier New", 10))
        self.output_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
            }
        """)
        layout.addWidget(self.output_display)
        
        self.main_vsplitter.addWidget(panel)
    
    def log(self, message: str, level: str = "INFO"):
        """输出日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        colors = {
            "INFO": "#d4d4d4",
            "STEP": "#4ec9b0",
            "SUCCESS": "#6a9955",
            "ERROR": "#f14c4c",
            "WARN": "#cca700",
        }
        color = colors.get(level, "#d4d4d4")
        
        html = f'<span style="color:#666">[{timestamp}]</span> <span style="color:{color}">[{level}]</span> {message}'
        self.output_display.append(html)
        
        # 滚动到底部
        self.output_display.verticalScrollBar().setValue(
            self.output_display.verticalScrollBar().maximum()
        )
    
    def clear_output(self):
        """清空输出"""
        self.output_display.clear()
    
    def _setup_menu(self):
        """设置菜单"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        new_action = QAction("新建会话", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_session)
        file_menu.addAction(new_action)
        
        export_code_action = QAction("导出代码...", self)
        export_code_action.triggered.connect(self.export_code)
        file_menu.addAction(export_code_action)
        
        export_model_action = QAction("导出模型...", self)
        export_model_action.triggered.connect(self.export_model)
        file_menu.addAction(export_model_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction("退出", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
    
    def _show_history_menu(self, pos):
        """显示历史右键菜单"""
        item = self.history_list.itemAt(pos)
        if not item:
            return
        
        menu = QMenu()
        load_action = menu.addAction("加载")
        delete_action = menu.addAction("删除")
        
        action = menu.exec_(self.history_list.mapToGlobal(pos))
        
        if action == load_action:
            self.load_history_session(item)
        elif action == delete_action:
            self.delete_history_session(item)
    
    # === Actions ===
    
    def start_generation(self):
        """开始生成"""
        text = self.input_box.text().strip()
        if not text:
            return
        
        self.input_box.clear()
        self._set_busy(True)
        
        self.append_chat("User", text)
        self.log(f"开始生成: {text}", "INFO")
        
        self.worker = AIWorker(self.generator, text, self.current_code)
        self.worker.finished.connect(self._on_generation_finished)
        self.worker.error.connect(self._on_generation_error)
        self.worker.progress.connect(self._on_generation_progress)
        self.worker.plan_ready.connect(self._on_plan_ready)
        
        self._gen_thread = threading.Thread(target=self.worker.run, daemon=True)
        self._gen_thread.start()
    
    def _on_generation_progress(self, msg, level):
        """生成进度回调"""
        self.status_label.setText(msg)
        self.log(msg, level)
    
    def _on_plan_ready(self, plan):
        """规划完成，预填参数面板"""
        self._syncing = True
        self.param_tree.blockSignals(True)
        
        try:
            self.param_tree.clear()
            
            for part in plan:
                part_name = part.get("name", "part")
                desc = part.get("description", "")
                location = part.get("location", [0, 0, 0])
                
                # 创建部件分组
                part_item = QTreeWidgetItem([part_name, ""])
                part_item.setFlags(part_item.flags() & ~Qt.ItemIsEditable)
                
                # 从 description 中提取尺寸参数
                import re
                # 匹配 width=X, height=Y, depth=Z, radius=R 等模式
                size_pattern = re.compile(r'(width|height|depth|radius|diameter|thickness|length)\s*[=:]\s*([\d.]+)', re.IGNORECASE)
                matches = size_pattern.findall(desc)
                
                for param_name, value in matches:
                    safe_name = f"{part_name}_{param_name.lower()}"
                    child = QTreeWidgetItem([safe_name, value])
                    child.setFlags(child.flags() | Qt.ItemIsEditable)
                    part_item.addChild(child)
                
                # 添加位置参数
                loc_x = QTreeWidgetItem([f"{part_name}_loc_x", str(location[0])])
                loc_y = QTreeWidgetItem([f"{part_name}_loc_y", str(location[1])])
                loc_z = QTreeWidgetItem([f"{part_name}_loc_z", str(location[2])])
                for loc_item in [loc_x, loc_y, loc_z]:
                    loc_item.setFlags(loc_item.flags() | Qt.ItemIsEditable)
                    part_item.addChild(loc_item)
                
                self.param_tree.addTopLevelItem(part_item)
                part_item.setExpanded(True)
            
            self.log(f"规划完成，预填 {len(plan)} 个部件参数", "INFO")
            
        finally:
            self.param_tree.blockSignals(False)
            self._syncing = False
    
    def _on_generation_finished(self, msg, code):
        """代码生成完成"""
        self._set_busy(False)
        
        self.current_code = code
        
        # 阻止同步循环
        self._syncing = True
        self.code_display.blockSignals(True)
        try:
            self.code_display.setPlainText(code)
        finally:
            self.code_display.blockSignals(False)
            self._syncing = False
        
        self.extract_params(code)
        
        self.append_chat("AI", msg)
        self.refresh_history()
        
        # 切换到代码标签页
        self.tabs.setCurrentIndex(0)
        
        # 如果勾选了自动渲染，则自动渲染
        if self.auto_render_cb.isChecked():
            self.render_code_manual()
    
    def _on_generation_error(self, error):
        """生成错误"""
        self._set_busy(False)
        self.append_chat("Error", error)
    
    def render_code_manual(self):
        """手动渲染代码"""
        code = self.code_display.toPlainText()
        if not code:
            return
        
        # 如果已有渲染进程在运行，先取消
        if hasattr(self, '_render_process') and self._render_process and self._render_process.is_alive():
            self.cancel_render()
            return
        
        self._set_busy(True)
        preview_mode = self.preview_mode_cb.isChecked()
        mode_str = "快速预览" if preview_mode else "高精度"
        self.status_label.setText(f"渲染中 ({mode_str})... [点击取消]")
        self.log(f"开始渲染 ({mode_str})...", "INFO")
        
        # 使用 multiprocessing 实现可中断渲染
        import multiprocessing as mp
        
        # 创建结果队列
        self._render_queue = mp.Queue()
        self._render_start_time = time.time()
        self._render_code = code  # 保存用于成功后更新
        
        # 启动渲染进程
        self._render_process = mp.Process(
            target=_render_in_process,
            args=(code, preview_mode, self._render_queue),
            daemon=True
        )
        self._render_process.start()
        
        # 启动轮询定时器检查结果
        self._render_timer = QTimer()
        self._render_timer.timeout.connect(self._check_render_result)
        self._render_timer.start(100)  # 每 100ms 检查一次
    
    def cancel_render(self):
        """取消渲染"""
        if hasattr(self, '_render_process') and self._render_process and self._render_process.is_alive():
            self._render_process.terminate()
            self._render_process.join(timeout=1)
            if self._render_process.is_alive():
                self._render_process.kill()  # 强制杀死
            self.log("渲染已取消", "WARNING")
            self.status_label.setText("渲染已取消")
        
        if hasattr(self, '_render_timer') and self._render_timer:
            self._render_timer.stop()
        
        self._set_busy(False)
        self._render_process = None
    
    def _check_render_result(self):
        """检查渲染进程结果"""
        # 检查进程是否还活着
        if not self._render_process or not self._render_process.is_alive():
            self._render_timer.stop()
            
            # 获取结果
            elapsed = time.time() - self._render_start_time
            
            try:
                if not self._render_queue.empty():
                    result = self._render_queue.get_nowait()
                    success = result.get('success', False)
                    model_path = result.get('model_path')
                    error_msg = result.get('error')
                    
                    if success and model_path:
                        self.current_code = self._render_code
                        self.current_model_path = model_path
                        self._on_render_success(model_path, elapsed)
                    else:
                        self._on_render_error(error_msg or "渲染失败", elapsed)
                else:
                    # 进程结束但没有结果（可能被取消）
                    if self._render_process.exitcode != 0:
                        self._on_render_error("渲染进程异常退出", elapsed)
            except Exception as e:
                self._on_render_error(str(e), elapsed)
            
            self._render_process = None
    
    def _on_render_success(self, model_path, elapsed):
        """渲染成功"""
        self._set_busy(False)
        self.load_model(model_path)
        self.generator.log_manual_edit(self.current_code)
        self.status_label.setText(f"渲染完成！({elapsed:.2f}s)")
        self.log(f"渲染成功: {model_path} ({elapsed:.2f}s)", "SUCCESS")
    
    def _on_render_error(self, error, elapsed=0):
        """渲染错误"""
        self._set_busy(False)
        
        # 提取关键错误信息
        error_lines = str(error).split('\n')
        short_error = error_lines[0] if error_lines else str(error)
        
        self.append_chat("Error", f"渲染失败: {short_error}")
        self.status_label.setText("渲染失败")
        
        # 完整错误输出到日志
        self.log(f"渲染失败 ({elapsed:.2f}s)", "ERROR")
        
        # 格式化错误详情
        for line in error_lines:
            if line.strip():
                # 高亮关键错误类型
                if "Error:" in line or "Exception" in line:
                    self.log(f"  ❌ {line.strip()}", "ERROR")
                elif "File" in line and "line" in line:
                    self.log(f"  📍 {line.strip()}", "WARN")
                elif line.strip().startswith("^"):
                    self.log(f"  {line}", "ERROR")
                else:
                    self.log(f"  {line.strip()}", "INFO")
    
    def _on_code_changed(self):
        """代码编辑器内容变化 → 同步更新参数面板"""
        if self._syncing:
            return
        
        code = self.code_display.toPlainText()
        if not code:
            return
        
        self._syncing = True
        try:
            # 提取当前代码中的参数值
            pattern = re.compile(r'^\s*([a-zA-Z_]\w+)\s*=\s*([\d.]+)\s*$', re.MULTILINE)
            code_params = {name: value for name, value in pattern.findall(code)}
            
            # 更新参数树中的值（不重建树结构）
            iterator = QTreeWidgetItemIterator(self.param_tree)
            while iterator.value():
                item = iterator.value()
                if item.childCount() == 0:  # 叶子节点（参数）
                    full_name = item.data(0, Qt.UserRole)
                    if full_name and full_name in code_params:
                        current_val = item.text(1)
                        new_val = code_params[full_name]
                        if current_val != new_val:
                            item.setText(1, new_val)
                iterator += 1
        finally:
            self._syncing = False
    
    def _on_param_changed(self, item, column):
        """参数面板数值变化 → 同步更新代码编辑器"""
        if self._syncing:
            return
        
        # 只处理数值列的变化
        if column != 1:
            return
        
        # 只处理叶子节点（参数项）
        if item.childCount() > 0:
            return
        
        full_name = item.data(0, Qt.UserRole)
        if not full_name:
            return
        
        new_value = item.text(1)
        
        # 验证是否为有效数字
        try:
            float(new_value)
        except ValueError:
            return
        
        self._syncing = True
        try:
            code = self.code_display.toPlainText()
            if not code:
                return
            
            # 替换代码中对应的参数值
            pattern = re.compile(
                r'^(\s*' + re.escape(full_name) + r'\s*=\s*)([\d.]+)(\s*)$',
                re.MULTILINE
            )
            new_code = pattern.sub(rf'\g<1>{new_value}\g<3>', code)
            
            if new_code != code:
                # 保存光标位置
                cursor = self.code_display.textCursor()
                pos = cursor.position()
                
                self.code_display.setPlainText(new_code)
                self.current_code = new_code
                
                # 恢复光标位置
                cursor.setPosition(min(pos, len(new_code)))
                self.code_display.setTextCursor(cursor)
                
                self.status_label.setText(f"参数 {full_name} 已更新为 {new_value}")
        finally:
            self._syncing = False
    
    def apply_params(self):
        """应用参数修改并渲染（保留此方法用于兼容）"""
        self.render_code_manual()
    
    def extract_params(self, code):
        """提取参数"""
        # 阻止信号触发同步
        self._syncing = True
        self.param_tree.blockSignals(True)
        
        try:
            self.param_tree.clear()
            
            pattern = re.compile(r'^\s*([a-zA-Z_]\w+)\s*=\s*([\d.]+)\s*$', re.MULTILINE)
            matches = pattern.findall(code)
            
            # 按前缀分组
            groups = {}
            for name, value in matches:
                parts = name.rsplit('_', 1)
                if len(parts) > 1:
                    prefix = '_'.join(name.split('_')[:-1])
                    if prefix not in groups:
                        groups[prefix] = []
                    groups[prefix].append((name, value))
                else:
                    if 'global' not in groups:
                        groups['global'] = []
                    groups['global'].append((name, value))
            
            for group_name, params in groups.items():
                group_item = QTreeWidgetItem(self.param_tree)
                group_item.setText(0, group_name)
                group_item.setExpanded(True)
                font = group_item.font(0)
                font.setBold(True)
                group_item.setFont(0, font)
                
                for name, value in params:
                    child = QTreeWidgetItem(group_item)
                    child.setText(0, name.split('_')[-1])
                    child.setText(1, value)
                    child.setFlags(child.flags() | Qt.ItemIsEditable)
                    child.setData(0, Qt.UserRole, name)
        finally:
            self.param_tree.blockSignals(False)
            self._syncing = False
    
    def load_model(self, path):
        """加载 3D 模型"""
        print(f"[Window] load_model called: {path}")
        print(f"[Window] HAS_PYVISTA={HAS_PYVISTA}, plotter={self.plotter is not None}")
        
        if not HAS_PYVISTA or not self.plotter:
            print("[Window] PyVista not available, skipping 3D display")
            return
        
        try:
            self.plotter.clear()
            self.plotter.add_axes()
            mesh = pv.read(path)
            print(f"[Window] Mesh loaded: {mesh.n_points} points, {mesh.n_cells} cells")
            self.plotter.add_mesh(mesh, color='lightblue', show_edges=True)
            self.plotter.reset_camera()
            self.plotter.update()
            print("[Window] 3D model displayed successfully")
        except Exception as e:
            print(f"[Window] 3D load error: {e}")
            self.append_chat("Error", f"3D 加载失败: {e}")
    
    def copy_code(self):
        """复制代码"""
        QApplication.clipboard().setText(self.code_display.toPlainText())
        self.status_label.setText("代码已复制")
    
    def export_code(self):
        """导出代码"""
        if not self.current_code:
            QMessageBox.warning(self, "警告", "没有可导出的代码")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "导出代码", "model.py", "Python Files (*.py)"
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.current_code)
            self.status_label.setText(f"代码已导出到 {path}")
    
    def export_model(self):
        """导出模型"""
        if not self.current_model_path or not os.path.exists(self.current_model_path):
            QMessageBox.warning(self, "警告", "没有可导出的模型")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "导出模型", "model.stl", "STL Files (*.stl);;STEP Files (*.step)"
        )
        if path:
            import shutil
            shutil.copy2(self.current_model_path, path)
            self.status_label.setText(f"模型已导出到 {path}")
    
    def new_session(self):
        """新建会话"""
        self.generator.save_history()
        self.generator.clear_history()
        
        self.current_code = None
        self.current_model_path = None
        
        self.chat_display.clear()
        self.code_display.clear()
        self.param_tree.clear()
        
        if HAS_PYVISTA and self.plotter:
            self.plotter.clear()
            self.plotter.add_axes()
        
        self.append_chat("System", "新会话已创建。")
        self.refresh_history()
    
    def refresh_history(self):
        """刷新历史列表"""
        self.history_list.clear()
        sessions = self.generator.get_history_list()
        
        for s in sessions:
            title = s.get('title', 'Unknown')
            filename = s.get('filename', '')
            
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, filename)
            self.history_list.addItem(item)
    
    def load_history_session(self, item):
        """加载历史会话"""
        filename = item.data(Qt.UserRole)
        history = self.generator.load_history(filename)
        
        if not history:
            QMessageBox.warning(self, "错误", "无法加载历史记录")
            return
        
        self.chat_display.clear()
        self.code_display.clear()
        self.param_tree.clear()
        
        last_code = None
        for entry in history:
            role = entry.get('role', 'System')
            content = entry.get('content', '')
            code = entry.get('code')
            
            self.append_chat(role, content)
            if code:
                last_code = code
        
        if last_code:
            self.current_code = last_code
            
            # 阻止同步循环
            self._syncing = True
            self.code_display.blockSignals(True)
            try:
                self.code_display.setPlainText(last_code)
            finally:
                self.code_display.blockSignals(False)
                self._syncing = False
            
            self.extract_params(last_code)
            
            self.status_label.setText("正在渲染历史代码...")
            QTimer.singleShot(100, lambda: self._render_loaded_code(last_code))
    
    def _render_loaded_code(self, code):
        """渲染加载的代码"""
        try:
            model_path = render_code(code)
            if model_path and os.path.exists(model_path):
                self.current_model_path = model_path
                self.load_model(model_path)
                self.status_label.setText("渲染完成")
            else:
                self.status_label.setText("渲染失败")
        except Exception as e:
            self.status_label.setText(f"渲染异常: {e}")
    
    def delete_history_session(self, item):
        """删除历史"""
        filename = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, '确认删除',
            f'确定要删除 "{item.text()}" 吗？',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.generator.delete_history(filename):
                self.refresh_history()
            else:
                QMessageBox.warning(self, "错误", "删除失败")
    
    def append_chat(self, role, text):
        """添加聊天消息"""
        colors = {
            "User": "blue",
            "AI": "green",
            "System": "gray",
            "Error": "red"
        }
        color = colors.get(role, "black")
        self.chat_display.append(f"<b style='color:{color}'>{role}:</b> {text}<br>")
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )
    
    def _set_busy(self, busy):
        """设置忙碌状态"""
        self.input_box.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.progress.setVisible(busy)
        # 控制取消按钮
        if hasattr(self, 'cancel_render_btn'):
            self.cancel_render_btn.setEnabled(busy)
        if busy:
            self.progress.setRange(0, 0)
    
    def closeEvent(self, event):
        """关闭事件"""
        # 清理渲染进程
        if hasattr(self, '_render_process') and self._render_process and self._render_process.is_alive():
            self._render_process.terminate()
            self._render_process.join(timeout=1)
        if hasattr(self, '_render_timer') and self._render_timer:
            self._render_timer.stop()
        
        self.generator.save_history()
        event.accept()


def start_pyqt5_app():
    """启动 PyQt5 应用"""
    app = QApplication(sys.argv)
    app.setApplicationName("AI CAD Architect")
    
    window = CADWindow()
    window.show()
    
    return app.exec_()


if __name__ == "__main__":
    sys.exit(start_pyqt5_app())
