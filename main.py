# -*- coding: utf-8 -*-
"""
Yamice - Sims 4 AI Storyteller Desktop App
A companion desktop application for the Sims 4 AI Storyteller mod.
Monitors game logs, sends them to AI APIs, and writes story content back.
"""

import os
import sys
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import requests

# Optional: Gemini SDK
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# ============================================================
# Constants & Configuration
# ============================================================

APP_NAME = "Yamice"
APP_VERSION = "1.0.0"
CONFIG_FILENAME = "Yamice_Settings.json"

# Color scheme
COLOR_BG = "#CCCCC5"
COLOR_ACCENT = "#FFCFCF"
COLOR_TEXT = "#333333"
COLOR_TEXT_SECONDARY = "#666666"
COLOR_WHITE_BG = "#F5F5F3"
COLOR_BUTTON_HOVER = "#FFB8B8"
COLOR_BUTTON_ACTIVE = "#FFA8A8"
COLOR_SUCCESS = "#4CAF50"
COLOR_ERROR = "#E53935"
COLOR_WARNING = "#FF9800"

# Provider configurations
PROVIDER_CONFIGS = {
    "OpenRouter": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "format": "openai",
        "models": [
            "google/gemini-2.5-flash-preview",
            "google/gemini-2.5-pro-preview",
            "google/gemini-2.0-flash-001",
            "openai/gpt-4.1-mini",
            "openai/gpt-4.1",
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4",
            "anthropic/claude-haiku-4",
            "deepseek/deepseek-chat-v3-0324",
            "qwen/qwen-2.5-72b-instruct",
            "x-ai/grok-3-mini-beta",
        ]
    },
    "硅基流动 (SiliconFlow)": {
        "api_url": "https://api.siliconflow.cn/v1/chat/completions",
        "format": "openai",
        "models": [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen2.5-72B-Instruct",
            "Qwen/Qwen2.5-7B-Instruct",
            "THUDM/glm-4-9b-chat",
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
        ]
    },
    "Gemini (Google)": {
        "api_url": "gemini_sdk",
        "format": "gemini",
        "models": [
            "gemini-2.5-flash-preview-05-20",
            "gemini-2.5-pro-preview-05-06",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
        ]
    },
    "OpenAI": {
        "api_url": "https://api.openai.com/v1/chat/completions",
        "format": "openai",
        "models": [
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-4o-mini",
            "gpt-4o",
            "o4-mini",
        ]
    },
    "Claude (Anthropic)": {
        "api_url": "https://api.anthropic.com/v1/messages",
        "format": "claude",
        "models": [
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
        ]
    },
    "DeepSeek": {
        "api_url": "https://api.deepseek.com/v1/chat/completions",
        "format": "openai",
        "models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ]
    },
    "Kimi (Moonshot)": {
        "api_url": "https://api.moonshot.cn/v1/chat/completions",
        "format": "openai",
        "models": [
            "moonshot-v1-auto",
            "moonshot-v1-128k",
        ]
    },
    "Qwen (通义千问)": {
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "format": "openai",
        "models": [
            "qwen-max",
            "qwen-plus",
            "qwen-turbo",
        ]
    },
    "Grok (xAI)": {
        "api_url": "https://api.x.ai/v1/chat/completions",
        "format": "openai",
        "models": [
            "grok-3-mini-beta",
            "grok-3-beta",
        ]
    },
    "智谱 (Zhipu)": {
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "format": "openai",
        "models": [
            "glm-4-plus",
            "glm-4-flash",
            "glm-4-long",
        ]
    },
}

DEFAULT_PROMPT = """你是一个《模拟人生4》的剧情导演。请根据以下信息生成一段简短的剧情更新。

【角色人设】
{profile}

【前情提要】
{memory}

【刚刚发生的事件】
{new_log}

【日志格式说明】
- 时间格式: [HH:MM] 角色名(情绪[Buff原因]) -> 动作 -> 目标 关系值
- 关系值 [F98/R10] 表示首次出现的友谊/浪漫总值
- 关系值 F+5/R-3 表示友谊变化+5/浪漫变化-3
- 注意：关系值变化有延迟，显示的是上一个互动造成的结果
- "=== Travel ===" 表示场景切换
- "| Holiday" 或 "| Party" 表示当前有节日或派对

【任务要求】
1. 先完整阅读所有日志，找出最核心的情绪转折或事件冲突
2. 写作风格：现代小说家，笔触克制，风格典雅
3. 禁止出现游戏特质名称、系统术语、括号注释
4. 禁止脑补日志内没有的内容
5. 禁止在结尾总结
6. 800字左右，简体中文

【输出格式】
请严格按照以下格式输出：

剧情内容...

||SPLIT||

新的前情提要（200字以内，概括关键事件和人物关系变化）...

||EVENTS||

重要事件（如果本次日志中有重大事件如：结婚、离婚、出生、分手、出轨被发现、死亡、怀孕、生子、搬家、升职、被开除、关系发生质变、表白、求婚等，用1-3句话记录关键事实，格式如："[角色A]与[角色B]正式结婚" 或 "[角色A]在工作中获得晋升"。如果没有重大事件，只写"无"）"""


# ============================================================
# Smart Path Detection (reused from existing run_ai.py)
# ============================================================

def find_sims4_mods_folder():
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Documents", "Electronic Arts", "The Sims 4", "Mods"),
        os.path.join(home, "OneDrive", "Documents", "Electronic Arts", "The Sims 4", "Mods"),
        os.path.join(home, "OneDrive - Personal", "Documents", "Electronic Arts", "The Sims 4", "Mods"),
        os.path.join(home, "文档", "Electronic Arts", "The Sims 4", "Mods"),
    ]
    userprofile = os.environ.get('USERPROFILE', '')
    if userprofile and userprofile != home:
        candidates.append(os.path.join(userprofile, "Documents", "Electronic Arts", "The Sims 4", "Mods"))
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


def get_default_output_dir():
    """Detect default output directory. Priority: config file -> desktop -> home."""
    mods = find_sims4_mods_folder()
    if mods:
        config_path = os.path.join(mods, "AI_Storyteller_Config.txt")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or line.startswith("//"):
                            continue
                        if line.startswith("save_path="):
                            custom = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if custom and os.path.isdir(custom):
                                return custom
            except Exception:
                pass

    home = os.path.expanduser("~")
    for desktop in [
        os.path.join(home, "Desktop"),
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "桌面"),
    ]:
        if os.path.isdir(desktop):
            return desktop
    return home


# ============================================================
# AI API Callers
# ============================================================

def call_openai_compatible(api_url, api_key, model, prompt, system_prompt="", timeout=120):
    """Call OpenAI-compatible API (covers OpenRouter, OpenAI, DeepSeek, Kimi, Qwen, Grok, SiliconFlow, Zhipu)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter" in api_url.lower():
        headers["HTTP-Referer"] = "https://github.com/yamice-storyteller"
        headers["X-Title"] = "Yamice Storyteller"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.8,
    }

    response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def call_claude_api(api_key, model, prompt, system_prompt="", timeout=120):
    """Call Anthropic Claude API (uses different format)."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        payload["system"] = system_prompt

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data["content"][0]["text"]


def call_gemini_sdk(api_key, model, prompt, timeout=120):
    """Call Google Gemini via the official SDK."""
    if not HAS_GENAI:
        raise ImportError(
            "google-generativeai 库未安装。请运行: pip install google-generativeai"
        )
    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(model)
    response = gen_model.generate_content(prompt, request_options={"timeout": timeout})
    return response.text


def call_ai(provider, api_key, model, prompt, system_prompt=""):
    """Unified AI call dispatcher."""
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        raise ValueError(f"未知的 API 提供商: {provider}")

    fmt = config["format"]
    api_url = config["api_url"]

    if fmt == "gemini":
        full_prompt = prompt
        if system_prompt:
            full_prompt = system_prompt + "\n\n" + prompt
        return call_gemini_sdk(api_key, model, full_prompt)
    elif fmt == "claude":
        return call_claude_api(api_key, model, prompt, system_prompt)
    else:
        return call_openai_compatible(api_url, api_key, model, prompt, system_prompt)


# ============================================================
# Config Manager
# ============================================================

class ConfigManager:
    def __init__(self, config_dir=None):
        self.config_dir = config_dir or get_default_output_dir()
        self.config_path = os.path.join(self.config_dir, CONFIG_FILENAME)
        self.data = self._defaults()
        self.load()

    def _defaults(self):
        return {
            "provider": "OpenRouter",
            "api_key": "",
            "model": "",
            "custom_prompt": "",
            "output_dir": get_default_output_dir(),
            "auto_start": False,
            "custom_model": "",
        }

    def load(self):
        """Load config from JSON file."""
        # Try loading from the output directory first
        for path in [self.config_path, os.path.join(get_default_output_dir(), CONFIG_FILENAME)]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                    for k, v in saved.items():
                        if k in self.data:
                            self.data[k] = v
                    # Update config dir if output_dir changed
                    if self.data.get("output_dir") and os.path.isdir(self.data["output_dir"]):
                        self.config_dir = self.data["output_dir"]
                        self.config_path = os.path.join(self.config_dir, CONFIG_FILENAME)
                    return
                except Exception:
                    pass

    def save(self):
        """Save config to JSON file."""
        if self.data.get("output_dir") and os.path.isdir(self.data["output_dir"]):
            self.config_dir = self.data["output_dir"]
            self.config_path = os.path.join(self.config_dir, CONFIG_FILENAME)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise IOError(f"无法保存配置文件: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def get_prompt(self):
        custom = self.data.get("custom_prompt", "").strip()
        return custom if custom else DEFAULT_PROMPT


# ============================================================
# File Monitor (Background Thread)
# ============================================================

class FileMonitor:
    def __init__(self, output_dir, ai_callback, log_callback):
        self.output_dir = output_dir
        self.ai_callback = ai_callback
        self.log_callback = log_callback
        self._running = False
        self._thread = None
        self._last_hash = ""
        self._processed_count = 0

    @property
    def file_log(self):
        return os.path.join(self.output_dir, "Sims4_Story_Log_Latest.txt")

    @property
    def file_profile(self):
        return os.path.join(self.output_dir, "Character_Profile.txt")

    @property
    def file_memory(self):
        return os.path.join(self.output_dir, "Story_Memory.txt")

    @property
    def file_inbox(self):
        return os.path.join(self.output_dir, "Sims4_Inbox.txt")

    @property
    def file_archive(self):
        return os.path.join(self.output_dir, "Story_Archive.txt")

    @property
    def file_pending_events(self):
        return os.path.join(self.output_dir, "Sims4_PendingEvents.txt")

    def start(self):
        if self._running:
            return
        self._running = True

        # Initialize file hash
        if os.path.exists(self.file_log):
            try:
                with open(self.file_log, "r", encoding="utf-8") as f:
                    self._last_hash = str(hash(f.read()))
            except Exception:
                pass

        # Ensure required files exist
        for fpath in [self.file_profile, self.file_memory, self.file_archive]:
            if not os.path.exists(fpath):
                try:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write("")
                except Exception:
                    pass

        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.log_callback("监控已启动，正在监控日志文件变化...")

    def stop(self):
        self._running = False
        self.log_callback("监控已停止。")

    @property
    def is_running(self):
        return self._running

    @property
    def processed_count(self):
        return self._processed_count

    def _monitor_loop(self):
        while self._running:
            try:
                time.sleep(5)
                if not self._running:
                    break

                if not os.path.exists(self.file_log):
                    continue

                try:
                    with open(self.file_log, "r", encoding="utf-8") as f:
                        current_content = f.read().strip()
                except Exception:
                    continue

                if not current_content:
                    continue

                current_hash = str(hash(current_content))
                if current_hash == self._last_hash:
                    continue

                self._last_hash = current_hash
                self.log_callback("检测到新日志，正在调用 AI...")

                # Read context files
                profile = self._read_file(self.file_profile)
                memory = self._read_file(self.file_memory)

                # Call AI
                try:
                    result = self.ai_callback(current_content, profile, memory)
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg:
                        self.log_callback("触发频率限制 (429)，等待 60 秒后重试...")
                        time.sleep(60)
                        continue
                    else:
                        self.log_callback(f"AI 调用失败: {error_msg}")
                        continue

                if not result:
                    self.log_callback("AI 返回空结果，跳过。")
                    continue

                # Parse result
                self._parse_and_write(result, memory)
                self._processed_count += 1
                self.log_callback(
                    f"剧情已发送给游戏！(累计处理 {self._processed_count} 条)"
                )

            except Exception as e:
                self.log_callback(f"监控循环错误: {e}")
                time.sleep(5)

    def _read_file(self, path):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return ""

    def _parse_and_write(self, result, old_memory):
        """Parse AI response and write to appropriate files."""
        if "||SPLIT||" not in result:
            self.log_callback("AI 返回格式异常（缺少 ||SPLIT||），跳过。")
            return

        story = ""
        new_mem = old_memory
        events = ""

        if "||EVENTS||" in result:
            parts = result.split("||SPLIT||")
            story = parts[0].strip()
            rest = parts[1] if len(parts) > 1 else ""

            if "||EVENTS||" in rest:
                event_parts = rest.split("||EVENTS||")
                new_mem = event_parts[0].strip()
                events = event_parts[1].strip() if len(event_parts) > 1 else ""
            else:
                new_mem = rest.strip()
        else:
            parts = result.split("||SPLIT||")
            story = parts[0].strip()
            new_mem = parts[1].strip() if len(parts) > 1 else old_memory

        # Write story to Inbox
        with open(self.file_inbox, "w", encoding="utf-8") as f:
            f.write(story)

        # Write memory
        with open(self.file_memory, "w", encoding="utf-8") as f:
            f.write(new_mem)

        # Write pending events if any
        if events and events != "无" and len(events) > 5:
            with open(self.file_pending_events, "w", encoding="utf-8") as f:
                f.write(events)
            self.log_callback("发现重要事件，等待玩家在游戏内审核...")

        # Archive
        with open(self.file_archive, "a", encoding="utf-8") as f:
            f.write(f"\n{story}\n")


# ============================================================
# GUI Application
# ============================================================

class YamiceApp:
    def __init__(self):
        self.config = ConfigManager()
        self.monitor = None

        # Build root window
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("680x580")
        self.root.minsize(600, 500)
        self.root.configure(bg=COLOR_BG)

        # Try to set icon (optional)
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        self._setup_styles()
        self._build_ui()
        self._load_config_to_ui()

        # Auto-start monitoring if configured
        if self.config.get("auto_start"):
            self.root.after(500, self._start_monitoring)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT, font=("Microsoft YaHei UI", 10))
        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=COLOR_BG, foreground=COLOR_TEXT,
                         padding=[16, 6], font=("Microsoft YaHei UI", 10))
        style.map("TNotebook.Tab",
                   background=[("selected", COLOR_ACCENT)],
                   foreground=[("selected", COLOR_TEXT)])
        style.configure("TFrame", background=COLOR_BG)
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT,
                         font=("Microsoft YaHei UI", 10))
        style.configure("TLabelframe", background=COLOR_BG, foreground=COLOR_TEXT,
                         font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TLabelframe.Label", background=COLOR_BG, foreground=COLOR_TEXT,
                         font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TButton", background=COLOR_ACCENT, foreground=COLOR_TEXT,
                         font=("Microsoft YaHei UI", 10), padding=[12, 4])
        style.map("TButton",
                   background=[("active", COLOR_BUTTON_HOVER), ("pressed", COLOR_BUTTON_ACTIVE)])
        style.configure("TCombobox", fieldbackground=COLOR_WHITE_BG, background=COLOR_WHITE_BG,
                         foreground=COLOR_TEXT, font=("Microsoft YaHei UI", 10))
        style.configure("TEntry", fieldbackground=COLOR_WHITE_BG, foreground=COLOR_TEXT,
                         font=("Microsoft YaHei UI", 10))

        style.configure("Status.TLabel", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Success.TLabel", foreground=COLOR_SUCCESS, background=COLOR_BG,
                         font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Error.TLabel", foreground=COLOR_ERROR, background=COLOR_BG,
                         font=("Microsoft YaHei UI", 10, "bold"))

    def _build_ui(self):
        # Title bar
        title_frame = tk.Frame(self.root, bg=COLOR_ACCENT, height=40)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text=f"  {APP_NAME}  v{APP_VERSION}",
                 bg=COLOR_ACCENT, fg=COLOR_TEXT,
                 font=("Microsoft YaHei UI", 13, "bold")).pack(side=tk.LEFT, padx=8, pady=6)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))

        # Tab 1: Connection Settings
        self.tab_connect = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_connect, text="  连接设置  ")
        self._build_connect_tab()

        # Tab 2: Prompt Editor
        self.tab_prompt = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_prompt, text="  Prompt  ")
        self._build_prompt_tab()

        # Tab 3: Status / Log
        self.tab_status = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_status, text="  状态  ")
        self._build_status_tab()

        # Bottom status bar
        self._build_status_bar()

    # ----- Tab 1: Connection Settings -----
    def _build_connect_tab(self):
        container = ttk.Frame(self.tab_connect)
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # API Provider
        api_frame = ttk.LabelFrame(container, text="API 设置")
        api_frame.pack(fill=tk.X, pady=(0, 8))

        row0 = ttk.Frame(api_frame)
        row0.pack(fill=tk.X, padx=12, pady=(10, 4))
        ttk.Label(row0, text="API 提供商:").pack(side=tk.LEFT)
        self.provider_var = tk.StringVar()
        self.provider_combo = ttk.Combobox(
            row0, textvariable=self.provider_var,
            values=list(PROVIDER_CONFIGS.keys()),
            state="readonly", width=28
        )
        self.provider_combo.pack(side=tk.LEFT, padx=(8, 0))
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_changed)

        row1 = ttk.Frame(api_frame)
        row1.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(row1, text="API Key:     ").pack(side=tk.LEFT)
        self.apikey_var = tk.StringVar()
        self.apikey_entry = ttk.Entry(row1, textvariable=self.apikey_var, show="*", width=40)
        self.apikey_entry.pack(side=tk.LEFT, padx=(8, 4))
        self.show_key_var = tk.BooleanVar(value=False)
        self.show_key_btn = ttk.Button(row1, text="显示", width=5,
                                        command=self._toggle_key_visibility)
        self.show_key_btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(api_frame)
        row2.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(row2, text="模型:          ").pack(side=tk.LEFT)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            row2, textvariable=self.model_var,
            values=[], width=36
        )
        self.model_combo.pack(side=tk.LEFT, padx=(8, 0))

        row2b = ttk.Frame(api_frame)
        row2b.pack(fill=tk.X, padx=12, pady=(2, 4))
        ttk.Label(row2b, text="", foreground=COLOR_TEXT_SECONDARY,
                   font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT)
        ttk.Label(row2b, text="(也可手动输入模型名称)",
                   foreground=COLOR_TEXT_SECONDARY,
                   font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT, padx=(74, 0))

        row3 = ttk.Frame(api_frame)
        row3.pack(fill=tk.X, padx=12, pady=(4, 12))
        self.test_btn = ttk.Button(row3, text="测试连接", command=self._test_connection)
        self.test_btn.pack(side=tk.LEFT)
        self.test_result_label = ttk.Label(row3, text="")
        self.test_result_label.pack(side=tk.LEFT, padx=(12, 0))

        # File paths
        path_frame = ttk.LabelFrame(container, text="文件路径")
        path_frame.pack(fill=tk.X, pady=(0, 8))

        row4 = ttk.Frame(path_frame)
        row4.pack(fill=tk.X, padx=12, pady=(10, 4))
        ttk.Label(row4, text="输出目录:").pack(side=tk.LEFT)
        self.output_dir_var = tk.StringVar()
        self.dir_entry = ttk.Entry(row4, textvariable=self.output_dir_var, width=38)
        self.dir_entry.pack(side=tk.LEFT, padx=(8, 0))

        row5 = ttk.Frame(path_frame)
        row5.pack(fill=tk.X, padx=12, pady=(4, 12))
        ttk.Button(row5, text="自动检测", command=self._auto_detect_path).pack(side=tk.LEFT)
        ttk.Button(row5, text="手动选择", command=self._manual_select_path).pack(side=tk.LEFT, padx=(8, 0))

        # Save button
        row6 = ttk.Frame(container)
        row6.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(row6, text="保存设置", command=self._save_settings).pack(side=tk.LEFT)
        self.save_result_label = ttk.Label(row6, text="")
        self.save_result_label.pack(side=tk.LEFT, padx=(12, 0))

    # ----- Tab 2: Prompt Editor -----
    def _build_prompt_tab(self):
        container = ttk.Frame(self.tab_prompt)
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        ttk.Label(container, text="编辑 AI 剧情生成 Prompt（支持 {profile}、{memory}、{new_log} 变量）：",
                   foreground=COLOR_TEXT_SECONDARY,
                   font=("Microsoft YaHei UI", 9)).pack(anchor=tk.W, pady=(0, 6))

        self.prompt_text = scrolledtext.ScrolledText(
            container, wrap=tk.WORD, font=("Consolas", 10),
            bg=COLOR_WHITE_BG, fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            relief=tk.FLAT, borderwidth=1,
            highlightbackground="#999999", highlightthickness=1,
        )
        self.prompt_text.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(container)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="恢复默认 Prompt", command=self._reset_prompt).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="保存 Prompt", command=self._save_prompt).pack(side=tk.LEFT, padx=(8, 0))
        self.prompt_save_label = ttk.Label(btn_row, text="")
        self.prompt_save_label.pack(side=tk.LEFT, padx=(12, 0))

    # ----- Tab 3: Status / Log -----
    def _build_status_tab(self):
        container = ttk.Frame(self.tab_status)
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Control buttons
        ctrl_frame = ttk.Frame(container)
        ctrl_frame.pack(fill=tk.X, pady=(0, 8))

        self.start_btn = ttk.Button(ctrl_frame, text="▶ 开始监控", command=self._start_monitoring)
        self.start_btn.pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(ctrl_frame, text="⏹ 停止", command=self._stop_monitoring,
                                    state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.monitor_status_label = ttk.Label(ctrl_frame, text="● 未启动",
                                                style="Status.TLabel")
        self.monitor_status_label.pack(side=tk.LEFT, padx=(16, 0))

        # Log display
        ttk.Label(container, text="运行日志：",
                   font=("Microsoft YaHei UI", 9)).pack(anchor=tk.W, pady=(0, 4))

        self.log_text = scrolledtext.ScrolledText(
            container, wrap=tk.WORD, font=("Consolas", 9),
            bg=COLOR_WHITE_BG, fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            relief=tk.FLAT, borderwidth=1,
            highlightbackground="#999999", highlightthickness=1,
            state=tk.DISABLED,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Clear button
        clear_frame = ttk.Frame(container)
        clear_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(clear_frame, text="清空日志", command=self._clear_log).pack(side=tk.LEFT)

    # ----- Bottom status bar -----
    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=COLOR_ACCENT, height=28)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        self.statusbar_label = tk.Label(
            bar, text="就绪", bg=COLOR_ACCENT, fg=COLOR_TEXT,
            font=("Microsoft YaHei UI", 9), anchor=tk.W
        )
        self.statusbar_label.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

    # ============================================================
    # UI Callbacks
    # ============================================================

    def _on_provider_changed(self, event=None):
        provider = self.provider_var.get()
        config = PROVIDER_CONFIGS.get(provider, {})
        models = config.get("models", [])
        self.model_combo["values"] = models
        if models:
            self.model_combo.set(models[0])
        else:
            self.model_combo.set("")
        self.test_result_label.config(text="")

    def _toggle_key_visibility(self):
        if self.show_key_var.get():
            self.apikey_entry.config(show="*")
            self.show_key_btn.config(text="显示")
            self.show_key_var.set(False)
        else:
            self.apikey_entry.config(show="")
            self.show_key_btn.config(text="隐藏")
            self.show_key_var.set(True)

    def _auto_detect_path(self):
        detected = get_default_output_dir()
        self.output_dir_var.set(detected)

    def _manual_select_path(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir_var.set(path)

    def _test_connection(self):
        provider = self.provider_var.get()
        api_key = self.apikey_var.get().strip()
        model = self.model_var.get().strip()

        if not provider:
            self.test_result_label.config(text="请选择提供商", style="Error.TLabel")
            return
        if not api_key:
            self.test_result_label.config(text="请输入 API Key", style="Error.TLabel")
            return
        if not model:
            self.test_result_label.config(text="请选择或输入模型", style="Error.TLabel")
            return

        self.test_result_label.config(text="测试中...", style="Status.TLabel")
        self.test_btn.config(state=tk.DISABLED)

        def do_test():
            try:
                result = call_ai(provider, api_key, model, "请回复'连接成功'这四个字。", "")
                self.root.after(0, lambda: self._show_test_result(True, result[:80]))
            except Exception as e:
                self.root.after(0, lambda: self._show_test_result(False, str(e)[:100]))

        threading.Thread(target=do_test, daemon=True).start()

    def _show_test_result(self, success, msg):
        self.test_btn.config(state=tk.NORMAL)
        if success:
            self.test_result_label.config(text=f"连接成功: {msg}", style="Success.TLabel")
        else:
            self.test_result_label.config(text=f"失败: {msg}", style="Error.TLabel")

    def _save_settings(self):
        self.config.set("provider", self.provider_var.get())
        self.config.set("api_key", self.apikey_var.get().strip())
        self.config.set("model", self.model_var.get().strip())
        self.config.set("output_dir", self.output_dir_var.get().strip())
        try:
            self.config.save()
            self.save_result_label.config(text="设置已保存", style="Success.TLabel")
        except Exception as e:
            self.save_result_label.config(text=f"保存失败: {e}", style="Error.TLabel")

    def _reset_prompt(self):
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", DEFAULT_PROMPT)
        self.prompt_save_label.config(text="已恢复默认", style="Success.TLabel")

    def _save_prompt(self):
        text = self.prompt_text.get("1.0", tk.END).strip()
        self.config.set("custom_prompt", text)
        try:
            self.config.save()
            self.prompt_save_label.config(text="Prompt 已保存", style="Success.TLabel")
        except Exception as e:
            self.prompt_save_label.config(text=f"保存失败: {e}", style="Error.TLabel")

    def _load_config_to_ui(self):
        provider = self.config.get("provider", "OpenRouter")
        self.provider_var.set(provider)
        self._on_provider_changed()

        model = self.config.get("model", "")
        if model:
            self.model_var.set(model)

        self.apikey_var.set(self.config.get("api_key", ""))
        self.output_dir_var.set(self.config.get("output_dir", get_default_output_dir()))

        prompt = self.config.get_prompt()
        self.prompt_text.insert("1.0", prompt)

    def _start_monitoring(self):
        provider = self.provider_var.get()
        api_key = self.apikey_var.get().strip()
        model = self.model_var.get().strip()
        output_dir = self.output_dir_var.get().strip()

        if not provider:
            messagebox.showwarning("提示", "请先选择 API 提供商。")
            return
        if not api_key:
            messagebox.showwarning("提示", "请先输入 API Key。")
            return
        if not model:
            messagebox.showwarning("提示", "请先选择或输入模型名称。")
            return
        if not output_dir or not os.path.isdir(output_dir):
            messagebox.showwarning("提示", "输出目录无效，请检查路径。")
            return

        # Save current settings
        self._save_settings()

        # Create AI callback
        prompt_template = self.config.get_prompt()

        def ai_callback(new_log, profile, memory):
            filled = prompt_template.replace("{profile}", profile)
            filled = filled.replace("{memory}", memory)
            filled = filled.replace("{new_log}", new_log)
            return call_ai(provider, api_key, model, filled)

        # Create and start monitor
        self.monitor = FileMonitor(output_dir, ai_callback, self._append_log)
        self.monitor.start()

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.monitor_status_label.config(text="● 监控中...", style="Success.TLabel")
        self.statusbar_label.config(text=f"监控中 - {output_dir}")

    def _stop_monitoring(self):
        if self.monitor:
            self.monitor.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.monitor_status_label.config(text="● 已停止", style="Error.TLabel")
        self.statusbar_label.config(text="已停止")

    def _append_log(self, message):
        """Thread-safe log append."""
        timestamp = time.strftime("%H:%M:%S")

        def do_append():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

            # Update status bar with processed count
            if self.monitor:
                count = self.monitor.processed_count
                self.statusbar_label.config(text=f"监控中 - 已处理 {count} 条日志")

        self.root.after(0, do_append)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def run(self):
        self.root.mainloop()


# ============================================================
# Entry Point
# ============================================================

def main():
    app = YamiceApp()
    app.run()


if __name__ == "__main__":
    main()
