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
# Color scheme
COLOR_BG = "#D1D1CA"          # 标题栏灰色
COLOR_ACCENT = "#FFCFCF"      # 粉色（底栏/tab激活）
COLOR_TEXT = "#333333"
COLOR_TEXT_SECONDARY = "#666666"
COLOR_WHITE_BG = "#FFFDF5"    # 内容区淡黄色
COLOR_BUTTON = "#E8E8E1"      # 按钮默认浅灰
COLOR_BUTTON_HOVER = "#D8D8D1"
COLOR_BUTTON_ACTIVE = "#C8C8C1"
COLOR_SUCCESS = "#4CAF50"
COLOR_ERROR = "#E53935"
COLOR_WARNING = "#FF9800"
COLOR_TAB_BLUE = "#B1E3DD"    # 蓝色tab
COLOR_TAB_GREEN = "#B7E3D1"   # 绿色tab
COLOR_MONKEY = "#B57D6C"      # 猴子褐色

# Provider configurations
PROVIDER_CONFIGS = {
    "OpenRouter": {
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "format": "openai",
        "models": [
            "google/gemini-2.5-flash",
            "google/gemini-2.5-flash-lite",
            "google/gemini-2.5-pro-preview",
            "openai/gpt-4.1-mini",
            "openai/gpt-4.1",
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-5",
            "anthropic/claude-haiku-4-5",
            "deepseek/deepseek-chat",
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
            "THUDM/GLM-5",
            "moonshotai/Kimi-K2.5",
            "Qwen/Qwen2.5-72B-Instruct",
            "Qwen/Qwen2.5-7B-Instruct",
            "meta-llama/Llama-3.1-8B-Instruct",
        ]
    },
    "Gemini (Google)": {
        "api_url": "gemini_sdk",
        "format": "gemini",
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
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
            "gpt-4.1-nano",
            "gpt-4o-mini",
            "gpt-4o",
            "o4-mini",
            "o3-mini",
        ]
    },
    "Claude (Anthropic)": {
        "api_url": "https://api.anthropic.com/v1/messages",
        "format": "claude",
        "models": [
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-5-20251101",
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
            "kimi-k2.5",
            "kimi-k2-turbo-preview",
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
            "qwq-plus",
            "qwen3-max",
        ]
    },
    "Grok (xAI)": {
        "api_url": "https://api.x.ai/v1/chat/completions",
        "format": "openai",
        "models": [
            "grok-3-mini-beta",
            "grok-3-beta",
            "grok-4-1-fast",
        ]
    },
    "智谱 (Zhipu)": {
        "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "format": "openai",
        "models": [
            "glm-4.7",
            "glm-4.5-flash",
            "glm-4-plus",
            "glm-4-flash",
        ]
    },
}

DEFAULT_PROMPT = """

【角色人设】
{profile}

【前情提要】
{memory}

【刚刚发生的事件】
{new_log}

你是一位现代小说的叙述者，正在连载一部以《模拟人生4》游戏事件为蓝本的家族故事。
你的读者是正在玩游戏的玩家——他们刚刚经历了这些事件，现在想看到文字把自己的游戏变成一段有血有肉的故事。

你的文字不是开头，也不是结尾，而是故事的「中间一页」。像翻开一本日记，直接进入正在发生的事。

【你会收到什么】
1. 角色人设 — 家庭成员的基本信息和关系
2. 前情提要 — 之前发生过的关键事
3. 事件日志 — 刚刚在游戏里发生的事

【日志怎么读】
-📋 家庭成员：姓名 (性别/年龄段) [特质]。性别M/F，年龄段ElderAdult/YA/Teen/Child。
-🔗 家庭关系：关系逗号后是家庭关系描述，用箭头指向可能有误，可根据年龄以及其他关系推断
-💕 浪漫：→后为关系描述（如Lovers, strained）。
-💫 吸引力：→后为吸引程度（VeryAttractedTo等）。
-💭 情感：→后为情感（如EnamoredBy）及括号内长期(LT)/短期(ST)原因。
-🔒 丑闻：人物: 秘密
- [HH:MM] 角色名(情绪[原因]) -> 动作 -> 目标 关系值
- [F98/R10] = 首次出现的友谊98/浪漫10总值
- F+5/R-3 = 友谊变化+5/浪漫变化-3（be affectionate不加值，如果在其后面发现了值变化，通常反映上一个互动的效果，有一条延迟。）
- "=== Travel ===" = 换了一个地点
-地段后面显示的是今天的节日或派对，如“BattleRoyale "，如果出现显示不全的问题，只显示了| Holiday" "| Party" = 也指正在过节或开派对
- [NPC] = 非玩家控制的角色快照
- 日志里名在前姓在后，写文时请用姓名（姓在前）
- 同名不同姓 = 不同的人，游戏里重名很常见

【写作原则】

选材：先通读全部日志，理解人物特点，关系动态，事件动态。挑出最有戏剧张力的1-3个核心事件来写。日常琐事（喝水、上厕所、闲聊）一笔带过或跳过，把笔墨留给冲突、情绪转折、关系变化。如果实在没有戏剧事件，再写日常的温馨细节。

视角：第三人称全知叙述，像一个隐形的摄影机跟拍这个家庭。

语气：现代小说的白描风格。句子干净利落，不堆砌形容词。用动作和对话展现人物，而不是直接说"他很生气"。
  好的例子：他把杯子重重放在桌上，水溅出来一些。
  不好的例子：他怒不可遏地将杯子狠狠摔在桌上，滚烫的液体如同他此刻翻涌的怒火。

对话：在合适的场景自然地写出人物会说的话，让角色活起来。不需要每个互动都配对话，只在关键时刻用。

克制：
  - 人设信息（特质、背景）不要主动提起，只在角色行为明显体现这个特质时，用行为而非标签来表现
  - 不要脑补日志里没有的事。比如A出轨了但日志里B没有伤心情绪，那B就是还不知道
  - 不要在结尾写总结性的抒情句。故事还在继续，这只是其中一页
  - 关系值数据不要出现在文中，但要用它来判断互动是正面还是负面的
篇幅：800字左右，简体中文。

【输出格式】
直接写剧情内容，不要加标题。然后：


||SPLIT||

新的前情提要（200字以内，概括本次关键事件和关系变化，供下次使用）...

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

def read_shared_config_path():
    """读取游戏内 Mod 保存的 JSON 配置路径（和游戏共享）"""
    mods = find_sims4_mods_folder()
    if not mods:
        return None
    json_path = os.path.join(mods, "AI_Storyteller_Settings.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            custom_path = data.get("save_path", "").strip()
            if custom_path and os.path.isdir(custom_path):
                return custom_path
        except Exception:
            pass
    return None

def get_default_output_dir():
    """Detect default output directory. Priority: config file -> desktop -> home."""
    # 优先读共享 JSON 配置
    shared = read_shared_config_path()
    if shared:
        return shared
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

def call_openai_compatible(api_url, api_key, model, prompt, system_prompt="", timeout=180):
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


def call_claude_api(api_key, model, prompt, system_prompt="", timeout=180, api_url=None):
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
        api_url or "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data["content"][0]["text"]


def call_gemini_sdk(api_key, model, prompt, timeout=180):
    """Call Google Gemini via the official SDK."""
    if not HAS_GENAI:
        raise ImportError(
            "google-generativeai 库未安装。请运行: pip install google-generativeai"
        )
    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(model)
    response = gen_model.generate_content(prompt, request_options={"timeout": timeout})
    return response.text


def call_ai(provider, api_key, model, prompt, system_prompt="", custom_api_url=""):
    """Unified AI call dispatcher."""

    # ========== 有自定义 URL → 智能模式 ==========
    if custom_api_url:
        url = custom_api_url.rstrip('/')

        # 自动补全 URL 尾巴
        if '/chat/completions' not in url and '/messages' not in url:
            url_openai = url + '/chat/completions'
        elif '/chat/completions' in url:
            url_openai = url
        else:
            url_openai = url.rsplit('/messages', 1)[0] + '/chat/completions'

        # 第一次尝试：OpenAI 格式（99% 的中转站都用这个）
        try:
            return call_openai_compatible(url_openai, api_key, model, prompt, system_prompt)
        except Exception as e1:
            error1 = str(e1)

            # 第二次尝试：Claude 格式（万一是真正的 Claude 代理）
            try:
                url_claude = custom_api_url.rstrip('/')
                if '/messages' not in url_claude:
                    url_claude = url_claude + '/messages'
                return call_claude_api(api_key, model, prompt, system_prompt, api_url=url_claude)
            except Exception as e2:
                error2 = str(e2)

                # 两种都失败了，给出详细错误
                raise ConnectionError(
                    f"自定义 URL 连接失败，已尝试两种格式:\n"
                    f"  OpenAI格式 ({url_openai}): {error1[:120]}\n"
                    f"  Claude格式: {error2[:120]}\n"
                    f"请检查: 1.URL是否正确 2.API Key是否匹配 3.模型名是否正确"
                )

    # ========== 没有自定义 URL → 走官方 ==========
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
            "custom_api_url": "",
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

                # Call AI（带重试机制）
                result = None
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        result = self.ai_callback(current_content, profile, memory)
                        if result:
                            break  # 成功了就跳出重试循环
                    except Exception as e:
                        error_msg = str(e)
                        if "429" in error_msg:
                            self.log_callback("触发频率限制 (429)，等待 60 秒后重试...")
                            time.sleep(60)
                            continue
                        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                            if attempt < max_retries - 1:
                                self.log_callback(f"⏱️ 调用超时，正在重试 ({attempt + 2}/{max_retries})...")
                                time.sleep(3)
                                continue
                            else:
                                self.log_callback("⏱️ 多次超时，跳过本次生成。")
                        else:
                            self.log_callback(f"AI 调用失败: {error_msg}")
                        result = None
                        break

                if not result:
                    if result is None:
                        self.log_callback("AI 返回空结果，跳过。")
                    continue

                # Parse result
                self._parse_and_write(result, memory)
                self._processed_count += 1
                self.log_callback(
                    f"剧情已发送给游戏！(累计处理 {self._processed_count} 条)"
                )

                # 检查是否有重新生成请求
                retry_signal = os.path.join(self.output_dir, "Retry_Request.signal")
                if os.path.exists(retry_signal):
                    try:
                        os.remove(retry_signal)
                        self.log_callback("收到重新生成请求，正在重新调用 AI...")
                        try:
                            result = self.ai_callback(current_content, profile, memory)
                            if result:
                                self._parse_and_write(result, memory)
                                self.log_callback("重新生成完成！")
                        except Exception as e:
                            self.log_callback(f"重新生成失败: {e}")
                    except:
                        pass

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
        """Parse AI response and write to appropriate files.
        Now with fallback: if ||SPLIT|| is missing, treat entire result as story
        and keep old memory. Writes a [MEMORY_MISSING] prefix so game can warn player.
        """
        story = ""
        new_mem = old_memory
        events = ""
        memory_missing = False

        if "||SPLIT||" not in result:
            # === 容错：没有分隔符，整段当剧情，保留旧 memory ===
            story = result.strip()
            new_mem = old_memory
            memory_missing = True
            self.log_callback("⚠️ AI 未返回 ||SPLIT||，已自动保留旧 memory。")
        elif "||EVENTS||" in result:
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

        # 如果解析后 story 为空，跳过
        if not story or len(story) < 10:
            self.log_callback("⚠️ AI 返回内容过短，跳过。")
            return

        # 如果 memory 为空，也用旧的
        if not new_mem or len(new_mem.strip()) < 5:
            new_mem = old_memory
            if not memory_missing:
                memory_missing = True
                self.log_callback("⚠️ AI 返回的 memory 为空，已自动保留旧 memory。")

        # Write story to Inbox（如果 memory 缺失，加前缀标记）
        inbox_content = f"[MEMORY_MISSING]\n{story}" if memory_missing else story
        with open(self.file_inbox, "w", encoding="utf-8") as f:
            f.write(inbox_content)

        # Write memory
        with open(self.file_memory, "w", encoding="utf-8") as f:
            f.write(new_mem)

        # Write pending events if any
        if events and events != "无" and len(events) > 5:
            with open(self.file_pending_events, "w", encoding="utf-8") as f:
                f.write(events)
            self.log_callback("发现重要事件，等待玩家在游戏内审核...")

        # Archive（归档不需要前缀标记）
        with open(self.file_archive, "a", encoding="utf-8") as f:
            f.write(f"\n{story}\n")

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
        ttk.Label(row0, text="API 提供商:", width=10).pack(side=tk.LEFT)
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
        ttk.Label(row1, text="API Key:", width=10).pack(side=tk.LEFT)
        self.apikey_var = tk.StringVar()
        self.apikey_entry = ttk.Entry(row1, textvariable=self.apikey_var, show="*", width=40)
        self.apikey_entry.pack(side=tk.LEFT, padx=(8, 4))
        self.show_key_var = tk.BooleanVar(value=False)
        self.show_key_btn = ttk.Button(row1, text="显示", width=5,
                                        command=self._toggle_key_visibility)
        self.show_key_btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(api_frame)
        row2.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(row2, text="模型:", width=10).pack(side=tk.LEFT)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            row2, textvariable=self.model_var,
            values=[], width=36
        )
        self.model_combo.pack(side=tk.LEFT, padx=(8, 0))

        row2b = ttk.Frame(api_frame)
        row2b.pack(fill=tk.X, padx=12, pady=(2, 4))
        ttk.Label(row2b, text="", width=10).pack(side=tk.LEFT)
        ttk.Label(row2b, text="(也可手动输入模型名称)",
                  foreground=COLOR_TEXT_SECONDARY,
                  font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT, padx=(8, 0))

        # Custom API URL
        row2c = ttk.Frame(api_frame)
        row2c.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(row2c, text="API URL:", width=10).pack(side=tk.LEFT)
        self.api_url_var = tk.StringVar()
        self.api_url_entry = ttk.Entry(row2c, textvariable=self.api_url_var, width=40)
        self.api_url_entry.pack(side=tk.LEFT, padx=(8, 0))

        row2d = ttk.Frame(api_frame)
        row2d.pack(fill=tk.X, padx=12, pady=(2, 4))
        ttk.Label(row2d, text="", width=10).pack(side=tk.LEFT)
        ttk.Label(row2d, text="(留空使用默认地址，填写则覆盖该提供商的地址)",
                  foreground=COLOR_TEXT_SECONDARY,
                  font=("Microsoft YaHei UI", 8)).pack(side=tk.LEFT, padx=(8, 0))

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
        ttk.Label(row4, text="输出目录:", width=10).pack(side=tk.LEFT)
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
            container, wrap=tk.WORD, font=("Microsoft YaHei UI", 10),
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
                custom_url = self.api_url_var.get().strip()
                result = call_ai(provider, api_key, model, "请回复'连接成功'这四个字。", "", custom_url)
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
        self.config.set("custom_api_url", self.api_url_var.get().strip())
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
        self.api_url_var.set(self.config.get("custom_api_url", ""))

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
        custom_url = self.api_url_var.get().strip()

        def ai_callback(new_log, profile, memory):
            filled = prompt_template.replace("{profile}", profile)
            filled = filled.replace("{memory}", memory)
            filled = filled.replace("{new_log}", new_log)
            return call_ai(provider, api_key, model, filled, "", custom_url)

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
