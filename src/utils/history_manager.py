"""
历史记录管理器
支持会话保存、加载、搜索
"""
import json
import os
import time
import glob
from datetime import datetime
from typing import List, Dict, Optional, Any


class HistoryManager:
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.history: List[Dict[str, Any]] = []
        self.title = "New Session"
        self.session_id = f"session_{int(time.time())}"
        self.metadata: Dict[str, Any] = {}
    
    def set_title(self, title: str):
        """设置会话标题"""
        self.title = title
        self.save_session()
    
    def set_metadata(self, key: str, value: Any):
        """设置元数据"""
        self.metadata[key] = value
        
    def add_interaction(
        self, 
        role: str, 
        content: str, 
        code: str = None,
        plan: List[Dict] = None,
        extra: Dict = None
    ):
        """添加交互记录"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        }
        if code:
            entry["code"] = code
        if plan:
            entry["plan"] = plan
        if extra:
            entry.update(extra)
            
        self.history.append(entry)
        self.save_session()
    
    def save_session(self):
        """保存当前会话"""
        if not self.history and self.title == "New Session":
            return
            
        filepath = os.path.join(self.cache_dir, f"{self.session_id}.json")
        data = {
            "title": self.title,
            "created_at": self.history[0]["timestamp"] if self.history else datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": self.metadata,
            "history": self.history
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[History] Save failed: {e}")
    
    def clear(self):
        """清空并开始新会话"""
        self.start_new_session()
    
    def start_new_session(self):
        """开始新会话"""
        self.history = []
        self.title = "New Session"
        self.session_id = f"session_{int(time.time())}"
        self.metadata = {}
    
    def list_sessions(self) -> List[Dict[str, str]]:
        """列出所有会话"""
        files = glob.glob(os.path.join(self.cache_dir, "*.json"))
        files.sort(key=os.path.getmtime, reverse=True)
        
        sessions = []
        for f in files:
            filename = os.path.basename(f)
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    if isinstance(data, dict):
                        sessions.append({
                            "filename": filename,
                            "title": data.get("title", filename),
                            "updated_at": data.get("updated_at", ""),
                            "preview": self._get_preview(data)
                        })
                    else:
                        # 兼容旧格式
                        sessions.append({
                            "filename": filename,
                            "title": filename,
                            "updated_at": "",
                            "preview": ""
                        })
            except Exception:
                sessions.append({
                    "filename": filename,
                    "title": filename,
                    "updated_at": "",
                    "preview": ""
                })
        
        return sessions
    
    def _get_preview(self, data: Dict) -> str:
        """获取会话预览文本"""
        history = data.get("history", [])
        for entry in history:
            if entry.get("role") == "User":
                content = entry.get("content", "")
                return content[:50] + "..." if len(content) > 50 else content
        return ""
    
    def load_session(self, filename: str) -> List[Dict]:
        """加载会话"""
        filepath = os.path.join(self.cache_dir, filename)
        if not os.path.exists(filepath):
            return []
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                self.history = data.get("history", [])
                self.title = data.get("title", "Untitled")
                self.metadata = data.get("metadata", {})
            else:
                # 兼容旧格式
                self.history = data
                self.title = filename
                
            self.session_id = os.path.splitext(filename)[0]
            return self.history
        except Exception as e:
            print(f"[History] Load failed: {e}")
            return []
    
    def delete_session(self, filename: str) -> bool:
        """删除会话"""
        filepath = os.path.join(self.cache_dir, filename)
        if not os.path.exists(filepath):
            return False
            
        try:
            os.remove(filepath)
            if self.session_id == os.path.splitext(filename)[0]:
                self.start_new_session()
            return True
        except Exception as e:
            print(f"[History] Delete failed: {e}")
            return False
    
    def get_last_code(self) -> Optional[str]:
        """获取最后一次生成的代码"""
        for entry in reversed(self.history):
            if entry.get("code"):
                return entry["code"]
        return None
    
    def get_conversation_context(self, max_turns: int = 5) -> str:
        """获取对话上下文用于 AI"""
        context_parts = []
        count = 0
        
        for entry in reversed(self.history):
            if count >= max_turns:
                break
            role = entry.get("role", "")
            content = entry.get("content", "")
            if role in ["User", "AI"]:
                context_parts.insert(0, f"{role}: {content}")
                count += 1
        
        return "\n".join(context_parts)
