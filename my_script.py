import sims4.commands
import services
import os
import alarms
import clock
import ui.ui_dialog
from interactions.base.interaction import Interaction
from sims4.localization import LocalizationHelperTuning



# =======================================================
# 💾 全局配置 & 变量
# =======================================================
MOD_VERSION = "V25.0"
AUTHOR = "kekell"
_log_buffer = []
_last_zone_id = None
_sim_mood_cache = {}
_monitor_alarm = None
_sim_last_action_cache = {}
_output_dir = None  # 缓存输出目录，避免每次都重新查找

# =======================================================
# 1. 核心工具箱
# =======================================================

# ============ 新的路径系统（替换旧的 get_desktop_path） ============

def _find_sims4_mods_folder():
    """
    智能查找 Sims 4 Mods 文件夹
    尝试多种常见路径，兼容 OneDrive、中文系统等
    """
    home = os.path.expanduser("~")

    # 所有可能的路径（按优先级排序）
    candidates = [
        # 标准路径
        os.path.join(home, "Documents", "Electronic Arts", "The Sims 4", "Mods"),
        # OneDrive 同步的 Documents
        os.path.join(home, "OneDrive", "Documents", "Electronic Arts", "The Sims 4", "Mods"),
        os.path.join(home, "OneDrive - Personal", "Documents", "Electronic Arts", "The Sims 4", "Mods"),
        # 中文 Windows（文档 = Documents 的中文别名，但实际路径还是 Documents）
        os.path.join(home, "文档", "Electronic Arts", "The Sims 4", "Mods"),
        # 韩文/日文等其他语言
        os.path.join(home, "Documents", "Electronic Arts", "The Sims 4", "Mods"),
    ]

    # 额外：用 USERPROFILE 环境变量（有些系统 ~ 展开不一样）
    userprofile = os.environ.get('USERPROFILE', '')
    if userprofile and userprofile != home:
        candidates.append(os.path.join(userprofile, "Documents", "Electronic Arts", "The Sims 4", "Mods"))

    for path in candidates:
        if os.path.isdir(path):
            return path

    return None


def _read_config_path():
    """
    从配置文件读取用户自定义的保存路径
    配置文件位置：Mods/AI_Storyteller_Config.txt
    """
    mods_folder = _find_sims4_mods_folder()
    if not mods_folder:
        return None

    config_path = os.path.join(mods_folder, "AI_Storyteller_Config.txt")

    if not os.path.exists(config_path):
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith("#") or line.startswith("//"):
                    continue
                if line.startswith("save_path="):
                    custom_path = line.split("=", 1)[1].strip()
                    # 去掉引号
                    custom_path = custom_path.strip('"').strip("'")
                    if custom_path and os.path.isdir(custom_path):
                        return custom_path
                    elif custom_path:
                        # 路径不存在，尝试创建
                        try:
                            os.makedirs(custom_path, exist_ok=True)
                            return custom_path
                        except:
                            pass
    except:
        pass

    return None


def _create_default_config():
    """
    在 Mods 文件夹创建默认配置文件（第一次运行时自动创建）
    用户可以用记事本编辑这个文件来自定义保存路径
    """
    mods_folder = _find_sims4_mods_folder()
    if not mods_folder:
        return

    config_path = os.path.join(mods_folder, "AI_Storyteller_Config.txt")
    if os.path.exists(config_path):
        return  # 已经存在，不覆盖

    try:
        default_output = os.path.join(os.path.expanduser("~"), "Desktop")
        config_content = f"""# =============================================
# AI Storyteller Config / AI故事讲述者 配置文件
# =============================================
#
# To change where log files are saved:
# 修改日志保存位置：
#
# 1. Change the path after "save_path=" below
#    修改下面 save_path= 后面的路径
#
# 2. Use FULL path, for example:
#    使用完整路径，例如：
#    save_path=C:\\Users\\YourName\\Desktop
#    save_path=D:\\MyFiles\\Sims4Logs
#
# 3. Save this file and restart the game
#    保存此文件并重启游戏
#
# Current setting / 当前设置:
save_path={default_output}
"""
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
    except:
        pass


def get_output_directory():
    """
    获取输出目录（替代旧的 get_desktop_path）
    优先级：1.配置文件 → 2.桌面 → 3.Mods文件夹 → 4.用户主目录
    """
    global _output_dir

    # 如果已经缓存了，直接返回
    if _output_dir and os.path.isdir(_output_dir):
        return _output_dir

    # 1. 先检查配置文件
    config_path = _read_config_path()
    if config_path:
        _output_dir = config_path
        return _output_dir

    # 2. 尝试桌面（多种方式）
    home = os.path.expanduser("~")
    desktop_candidates = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "桌面"),  # 中文
    ]

    for desktop in desktop_candidates:
        if os.path.isdir(desktop):
            _output_dir = desktop
            # 顺便创建配置文件
            _create_default_config()
            return _output_dir

    # 3. 回退到 Mods 文件夹
    mods = _find_sims4_mods_folder()
    if mods:
        _output_dir = mods
        return _output_dir

    # 4. 最后的最后：用户主目录
    _output_dir = home
    return _output_dir


def get_inbox_path():
    return os.path.join(get_output_directory(), "Sims4_Inbox.txt")


def log_error(error_msg, context=""):
    """ 记录错误到输出目录的 error.txt """
    try:
        error_path = os.path.join(get_output_directory(), "Sims4_Error_Log.txt")
        timestamp = get_log_time()
        with open(error_path, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} [{context}] {error_msg}\n")
    except:
        pass  # 如果连错误日志都写不了，那就只能放弃了

def get_header_context():
    """ 生成标题上下文: [时间] 星期|天气 @地点(真实名字) """
    try:
        now = services.game_clock_service().now()
        time_str = f"[{now.hour():02d}:{now.minute():02d}]"

        # 1. 星期
        days_map = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        day_str = days_map[now.day() % 7]

        # 2. 天气（使用 .name 属性）
        weather_str = "Clear"
        try:
            ws = services.weather_service()
            if ws and hasattr(ws, 'get_current_weather_types'):
                weather_types = ws.get_current_weather_types()

                if weather_types and len(weather_types) >= 1:
                    weather_names = []

                    for i, wt in enumerate(weather_types):
                        if i >= 2:
                            break

                        try:
                            name = ""
                            if hasattr(wt, 'name'):
                                raw_name = wt.name
                                name = str(raw_name) if raw_name else ""

                            if not name and hasattr(wt, '__name__'):
                                name = wt.__name__

                            if name:
                                name = name.replace('WeatherType.', '').replace('WeatherType_', '')
                                name = name.replace('Weather_', '').replace('_', ' ').strip()

                                if name and name != 'WeatherType':
                                    weather_names.append(name)
                        except:
                            pass

                    if weather_names:
                        weather_str = '+'.join(weather_names)

        except Exception as e:
            log_error(f"Weather error: {str(e)}", "get_header_context")

        # 3. 地点 (优先抓取真实名字，抓不到则抓类型)
        venue_str = "Home"
        try:
            zone = services.current_zone()
            if zone:
                if hasattr(zone, 'description') and zone.description:
                    venue_str = str(zone.description)
                elif hasattr(zone, 'name') and zone.name:
                    venue_str = str(zone.name)
                else:
                    venue_service = services.venue_service()
                    if venue_service and venue_service.active_venue:
                        raw_name = type(venue_service.active_venue).__name__
                        venue_str = raw_name.replace('Venue_', '').replace('_', ' ')
        except Exception as e:
            log_error(f"Venue error: {str(e)}", "get_header_context")

        return f"{time_str} {day_str}|{weather_str} @{venue_str}"
    except:
        return "[--:--]"

def get_log_time():
    """ 单行日志极简时间 """
    try:
        now = services.game_clock_service().now()
        return f"[{now.hour():02d}:{now.minute():02d}]"
    except:
        return "[--:--]"


def clean_string(text):
    """ 清洗代码名，使其更像人类语言 """
    if not text: return ""
    # 去掉常见前缀
    text = text.replace('object_', '').replace('Venue_', '').replace('si_', '').replace('interaction_', '')
    # 去掉杂音词
    trash_list = ['SI', 'Action', 'Mixer', 'OneShot', 'Passive', 'Looping', 'Touch', 'Social', 'Adjustment', 'Super','Active']
    for trash in trash_list:
        text = text.replace(trash, '')

    # 替换下划线并首字母大写
    text = text.replace('_', ' ').strip()
    return text.title()


def get_sim_name_robust(sim):
    """ 安全获取 Sim 名字 """
    name = ""
    try:
        if hasattr(sim, 'sim_info') and sim.sim_info.full_name:
            name = sim.sim_info.full_name
        elif hasattr(sim, 'full_name') and sim.full_name:
            name = sim.full_name
        elif hasattr(sim, 'first_name') and hasattr(sim, 'last_name'):
            name = f"{sim.first_name} {sim.last_name}"
    except:
        pass

    if not name or name.strip() == "":
        sim_id = str(sim.id) if hasattr(sim, 'id') else "?"
        return f"Sim({sim_id})"
    return name


def get_target_name_smart(target):
    """ 获取交互对象的名字 """
    if not target: return ""
    try:
        # 如果是 Sim
        if hasattr(target, 'is_sim') and target.is_sim:
            return get_sim_name_robust(target)
        # 如果是物品部件 (比如床的左边/右边)
        if hasattr(target, 'is_part') and target.is_part:
            if hasattr(target, 'part_owner'):
                target = target.part_owner

        # 获取物品类名
        raw_name = type(target).__name__

        # 过滤无意义的内存地址名
        if "0x" in raw_name or raw_name == "NoneType":
            return "Object"

        return clean_string(raw_name)
    except:
        return "Object"


def get_mood_delta(sim):
    """
    智能情绪抓取：
    只抓取 '可见' 的 Buff，并优先展示造成当前主导情绪的 Buff。
    """
    try:
        current_mood_obj = sim.get_mood()
        mood_name = current_mood_obj.__name__.replace('Mood_', '')

        primary_buffs = []
        secondary_buffs = []

        if hasattr(sim, 'get_active_buff_types'):
            raw_buffs = sim.get_active_buff_types()
            blacklist = ['Hidden', 'System', 'Controller', 'Autonomy', 'Cooldown', 'Role']

            for b in raw_buffs:
                # 只看可见的
                if hasattr(b, 'visible') and not b.visible: continue
                # 过滤黑名单关键词
                b_name = b.__name__
                if any(bad in b_name for bad in blacklist): continue

                clean_name = b_name.replace('buff_', '').replace('Buff_', '')
                clean_name = clean_name.replace('Sim_', '').replace('Reason_', '')

                try:
                    # 如果这个 Buff 的类型和当前主导情绪一致，优先展示
                    if hasattr(b, 'mood_type') and b.mood_type == current_mood_obj:
                        primary_buffs.append(clean_name)
                    else:
                        secondary_buffs.append(clean_name)
                except:
                    secondary_buffs.append(clean_name)

        # 排序：主导情绪的 Buff 排前面
        sorted_buffs = primary_buffs + secondary_buffs
        # 只取前 3 个，避免刷屏
        top_buffs = sorted_buffs[:3]

        current_mood_full = f"{mood_name}"
        if top_buffs:
            current_mood_full += f"[{','.join(top_buffs)}]"

        # 缓存机制：如果情绪没变，就不重复记录
        sim_id = str(sim.id)
        last_known = _sim_mood_cache.get(sim_id, "")

        if current_mood_full == last_known:
            return ""  # 情绪没变，返回空字符串
        else:
            _sim_mood_cache[sim_id] = current_mood_full
            return f" ({current_mood_full})"
    except:
        return ""


def is_meaningful(action_name):
    """
    过滤垃圾动作
    修复：idle_chat 类动作不再因为白名单中的 chat 而误放行
    """
    action = action_name.lower()

    # 黑名单：这些动作太琐碎，不需要记录
    blacklist = [
        'stand', 'idle', 'route', 'monitor', 'situation', 'dream', 'sleep_rose',
        'nap', 'listen', 'watch', 'wait', 'check', 'carry', 'putdown',
        'picker', 'chooser', 'si_touching', 'create_and_use', 'passive',
        'posture', 'adjustment', 'generic', 'autonomy', 'reaction',
        'job_performance', 'buff_', 'mixer', 'flush', 'washhands', 'moveaway',
        'idle chatting', 'stc'
    ]

    # 白名单：这些动作很重要，即使包含黑名单词也要记录
    whitelist = ['kiss', 'flirt', 'fight', 'woohoo', 'dance', 'propose',
                 'wedding', 'hug', 'express']

    # 先检查白名单（最高优先级）
    if any(w in action for w in whitelist):
        return True

    # 再检查黑名单
    if any(x in action for x in blacklist):
        return False

    return True


def is_active_sim(sim):
    """ 判断是否是当前家庭的 Sim """
    try:
        client = services.client_manager().get_first_client()
        if client and sim.sim_info in client.selectable_sims:
            return True
    except:
        pass
    return False


# ========== 角色特征抓取 ==========

def get_active_characters_summary():
    """
    获取当前活跃角色的特征摘要
    包括：1) 所有家庭成员, 2) 日志中频繁出现的 NPC
    """
    try:
        client = services.client_manager().get_first_client()
        if not client:
            return ""

        summary_lines = ["📋 Characters:"]
        captured_sims = set()

        selectable = list(client.selectable_sims)

        # === 第一部分：所有家庭成员 ===
        for sim_info in selectable:
            sim_name = ""
            try:
                if hasattr(sim_info, 'full_name') and sim_info.full_name:
                    sim_name = sim_info.full_name
                elif hasattr(sim_info, 'first_name') and hasattr(sim_info, 'last_name'):
                    sim_name = f"{sim_info.first_name} {sim_info.last_name}"

                if not sim_name or sim_name.strip() == "":
                    if hasattr(sim_info, 'get_sim_instance'):
                        sim = sim_info.get_sim_instance()
                        if sim and hasattr(sim, 'sim_info'):
                            sim_name = sim.sim_info.full_name
            except:
                pass

            if not sim_name:
                sim_name = f"Sim_{sim_info.id if hasattr(sim_info, 'id') else '?'}"

            traits_str = _get_sim_traits(sim_info)

            if traits_str:
                summary_lines.append(f"  • {sim_name}: {traits_str}")
            else:
                summary_lines.append(f"  • {sim_name}: (no traits)")

            captured_sims.add(sim_name)

        # === 第二部分：日志中频繁出现的 NPC ===
        npc_counts = _count_npcs_in_log()

        for npc_name, count in npc_counts.items():
            if count >= 3 and npc_name not in captured_sims:
                npc_sim_info = _find_sim_info_by_name(npc_name)

                if npc_sim_info:
                    traits_str = _get_sim_traits(npc_sim_info)

                    if traits_str:
                        summary_lines.append(f"  • {npc_name} (NPC): {traits_str}")
                    else:
                        summary_lines.append(f"  • {npc_name} (NPC): (no traits)")

        return "\n".join(summary_lines) if len(summary_lines) > 1 else ""
    except Exception as e:
        log_error(f"get_active_characters_summary error: {str(e)}", "summary")
        return ""


def _get_sim_traits(sim_info):
    """
    提取 Sim 的性格特征
    注意：Sims 4 每个 Sim 只有 3 个性格特征，这是游戏设定
    如果安装了 mod 添加了额外特征槽，可能会有更多
    """
    traits = []
    try:
        tracker = None

        if hasattr(sim_info, 'trait_tracker'):
            tracker = sim_info.trait_tracker

        if tracker is None or not hasattr(tracker, 'personality_traits'):
            if hasattr(sim_info, 'get_sim_instance'):
                sim = sim_info.get_sim_instance()
                if sim and hasattr(sim, 'trait_tracker'):
                    tracker = sim.trait_tracker

        if tracker and hasattr(tracker, 'personality_traits'):
            for trait in tracker.personality_traits:
                try:
                    trait_name = trait.__name__ if hasattr(trait, '__name__') else str(trait)
                    trait_name = trait_name.replace('trait_', '').replace('Trait_', '')

                    if trait_name.startswith('Hidden'):
                        continue

                    # 智能清理
                    parts = trait_name.split('_')

                    clean_parts = []
                    for p in parts:
                        if len(p) <= 2:
                            continue
                        if p.lower() in ['traitsbundle', 'trait', 'kawaiistacie', 'bundle']:
                            continue
                        if len(p) > 6 and any(c.isdigit() for c in p):
                            continue
                        clean_parts.append(p)

                    if clean_parts:
                        display_name = ' '.join(clean_parts)
                    else:
                        display_name = trait_name.replace('_', ' ').strip()

                    if display_name and len(display_name) < 50:
                        traits.append(display_name)
                except:
                    pass
    except Exception as e:
        log_error(f"_get_sim_traits error: {str(e)}", "traits")

    return ', '.join(traits[:8]) if traits else ""


def _count_npcs_in_log():
    """ 统计当前日志中每个 Sim 出现的次数 """
    counts = {}
    try:
        client = services.client_manager().get_first_client()
        if not client:
            return counts

        family_names = {sim_info.full_name for sim_info in client.selectable_sims}

        for entry in _log_buffer:
            if '->' in entry:
                parts = entry.split('->')
                if len(parts) >= 2:
                    name_part = parts[0].strip()
                    if ']' in name_part:
                        name = name_part.split(']')[-1].strip()
                        if '(' in name:
                            name = name.split('(')[0].strip()

                        if name and name not in family_names:
                            counts[name] = counts.get(name, 0) + 1
    except:
        pass

    return counts


def _find_sim_info_by_name(name):
    """ 通过名字查找 Sim 的 sim_info """
    try:
        sim_info_manager = services.sim_info_manager()
        if sim_info_manager:
            for sim_info in sim_info_manager.objects:
                if sim_info.full_name == name:
                    return sim_info
    except:
        pass
    return None

# =======================================================
# 2. 监听核心 (Inject)
# =======================================================
if not hasattr(Interaction, '_original_trigger_backup'):
    Interaction._original_trigger_backup = Interaction._trigger_interaction_start_event


def _new_trigger_start(self, *args, **kwargs):
    global _last_zone_id
    try:
        # --- 场景切换检测 ---
        current_zone = services.current_zone_id()
        if _last_zone_id is not None and current_zone != _last_zone_id:
            header = get_header_context()
            _log_buffer.append(f"\n=== ✈️ Travel: {header} ===\n")
            _sim_mood_cache.clear()
            _sim_last_action_cache.clear()
        _last_zone_id = current_zone
        # ------------------

        sim = getattr(self, 'sim', None)
        if sim:
            actor_is_family = is_active_sim(sim)
            target = getattr(self, 'target', None)
            target_is_family = False
            if target and hasattr(target, 'is_sim') and target.is_sim:
                target_is_family = is_active_sim(target)

            if actor_is_family or target_is_family:
                raw_action = type(self).__name__
                if hasattr(self, 'affordance') and self.affordance:
                    raw_action = self.affordance.__name__

                action = clean_string(raw_action)

                if is_meaningful(action) and action:
                    sim_id = str(sim.id)
                    last_action = _sim_last_action_cache.get(sim_id, "")

                    target = getattr(self, 'target', None)
                    target_name = get_target_name_smart(target) if target else ""

                    action_key = f"{action}-{target_name}"

                    # 社交互动添加时间戳，防止被误判为重复
                    if any(keyword in action.lower() for keyword in
                           ['social', 'romance', 'kiss', 'flirt', 'hug', 'chat']):
                        action_key += f"-{get_log_time()}"

                    if action_key == last_action:
                        return Interaction._original_trigger_backup(self, *args, **kwargs)

                    _sim_last_action_cache[sim_id] = action_key

                    display_name = get_sim_name_robust(sim)
                    time_str = get_log_time()

                    target_str = ""
                    if target:
                        t_name = get_target_name_smart(target)
                        if t_name != display_name:
                            target_str = f" -> {t_name}"

                    current_mood_str = ""
                    if actor_is_family:
                        current_mood_str = get_mood_delta(sim)

                    entry = f"{time_str} {display_name}{current_mood_str} -> {action}{target_str}"

                    if not _log_buffer or _log_buffer[-1] != entry:
                        _log_buffer.append(entry)

                        if len(_log_buffer) > 500:
                            _log_buffer.pop(0)

    except Exception as e:
        pass

    return Interaction._original_trigger_backup(self, *args, **kwargs)


Interaction._trigger_interaction_start_event = _new_trigger_start


# =======================================================
# 3. 自动监测核心 (Inbox Monitoring)
# =======================================================

def show_story_dialog(text):
    """ 弹窗显示剧情 """
    client = services.client_manager().get_first_client()
    if not client: return

    dialog = ui.ui_dialog.UiDialogOkCancel.TunableFactory().default(
        client.active_sim,
        text=lambda *args: LocalizationHelperTuning.get_raw_text(text),
        title=lambda *args: LocalizationHelperTuning.get_raw_text(f"📖 AI Storyteller ({MOD_VERSION})")
    )
    dialog.show_dialog()


def check_inbox_logic(_):
    """ 定时检查信箱 """
    path = get_inbox_path()
    if not os.path.exists(path): return

    try:
        content = ""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if content:
            show_story_dialog(content)
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
    except:
        pass


# =======================================================
# 4. 保存核心（带验证）
# =======================================================

def do_save_log():
    """
    核心保存逻辑（被菜单按钮和命令共用）
    返回 (success: bool, message: str)
    """
    output_dir = get_output_directory()

    path_full = os.path.join(output_dir, "Sims4_Story_Log_Full.txt")
    path_latest = os.path.join(output_dir, "Sims4_Story_Log_Latest.txt")

    try:
        if not _log_buffer:
            return (False, f"📝 No new logs to save.\n({MOD_VERSION})")

        # 生成标题和角色信息
        header = f"\n--- Save {get_header_context()} ---\n"
        characters_info = get_active_characters_summary()

        # 组装内容
        content_lines = [header]
        if characters_info:
            content_lines.append(characters_info + "\n")

        for line in _log_buffer:
            content_lines.append(line + "\n")

        full_content = "".join(content_lines)
        count = len(_log_buffer)

        # 文件1：累积版（追加模式 "a"）
        with open(path_full, "a", encoding="utf-8") as f:
            f.write(full_content)

        # 文件2：最新版（覆盖模式 "w"）
        with open(path_latest, "w", encoding="utf-8") as f:
            f.write(full_content)

        # ====== 写入验证 ======
        verify_ok = False
        try:
            with open(path_latest, "r", encoding="utf-8") as f:
                check = f.read()
                if len(check) > 10:
                    verify_ok = True
        except:
            pass

        _log_buffer.clear()

        if verify_ok:
            return (True,
                    f"✅ Saved {count} entries!\n\n"
                    f"📁 Full log:\n{path_full}\n\n"
                    f"📄 Latest:\n{path_latest}")
        else:
            return (False,
                    f"⚠️ File created but may be empty!\n\n"
                    f"Path: {path_latest}\n\n"
                    f"Try creating a config file in your Mods folder:\n"
                    f"AI_Storyteller_Config.txt")

    except Exception as e:
        return (False, f"❌ Save failed: {e}\n\nOutput dir: {output_dir}")


# =======================================================
# 5. 命令区 (Commands)
# =======================================================

@sims4.commands.Command('save_now', command_type=sims4.commands.CommandType.Live)
def save_now_command(_connection=None):
    """ 手动存档指令 """
    output = sims4.commands.CheatOutput(_connection)
    success, message = do_save_log()
    output(message)


@sims4.commands.Command('start_ai', command_type=sims4.commands.CommandType.Live)
def start_ai_monitor(_connection=None):
    """ 开启弹窗监测 """
    global _monitor_alarm
    output = sims4.commands.CheatOutput(_connection)

    if _monitor_alarm is not None:
        output(f"⚠️ AI monitoring is already running! ({MOD_VERSION})")
        return

    client = services.client_manager().get_first_client()
    if not client:
        output("❌ Please enter Live Mode first")
        return

    _monitor_alarm = alarms.add_alarm_real_time(
        client,
        clock.interval_in_real_seconds(5),
        check_inbox_logic,
        repeating=True
    )
    output(f"🚀 AI inbox monitoring started! ({MOD_VERSION})")


@sims4.commands.Command('stop_ai', command_type=sims4.commands.CommandType.Live)
def stop_ai_monitor(_connection=None):
    """ 停止弹窗监测 """
    global _monitor_alarm
    output = sims4.commands.CheatOutput(_connection)

    if _monitor_alarm is not None:
        alarms.cancel_alarm(_monitor_alarm)
        _monitor_alarm = None
        output("🛑 Monitoring stopped.")
    else:
        output("⚠️ No monitoring is currently running.")


@sims4.commands.Command('ai_path', command_type=sims4.commands.CommandType.Live)
def show_path_command(_connection=None):
    """ 显示当前保存路径（调试用） """
    output = sims4.commands.CheatOutput(_connection)
    output(f"📁 Output directory: {get_output_directory()}")
    output(f"📄 Inbox path: {get_inbox_path()}")

    mods = _find_sims4_mods_folder()
    if mods:
        config = os.path.join(mods, "AI_Storyteller_Config.txt")
        output(f"⚙️ Config file: {config}")
        output(f"   Config exists: {os.path.exists(config)}")
    else:
        output("⚠️ Could not find Mods folder!")


# =======================================================
# 6. 菜单交互类 (Pie Menu Interactions)
# =======================================================

from interactions.base.immediate_interaction import ImmediateSuperInteraction
from sims4.utils import flexmethod


class SaveLogInteraction(ImmediateSuperInteraction):
    """ 保存日志交互 """

    @flexmethod
    def _run_interaction_gen(cls, inst, timeline):
        try:
            success, message = do_save_log()
            show_story_dialog(message)
        except Exception as e:
            show_story_dialog(f"❌ Save failed: {e}")

        return True


class StartAIInteraction(ImmediateSuperInteraction):
    """ 启动 AI 监听交互 """

    @flexmethod
    def _run_interaction_gen(cls, inst, timeline):
        global _monitor_alarm

        if _monitor_alarm is not None:
            show_story_dialog(f"⚠️ AI monitoring is already running! ({MOD_VERSION})")
            return True

        client = services.client_manager().get_first_client()
        if not client:
            show_story_dialog("❌ Please enter Live Mode first")
            return True

        _monitor_alarm = alarms.add_alarm_real_time(
            client,
            clock.interval_in_real_seconds(5),
            check_inbox_logic,
            repeating=True
        )
        inbox = get_inbox_path()
        show_story_dialog(
            f"🚀 AI inbox monitoring started!\n\n"
            f"📬 Inbox location:\n{inbox}\n\n"
            f"({MOD_VERSION})")
        return True


class StopAIInteraction(ImmediateSuperInteraction):
    """ 停止 AI 监听交互 """

    @flexmethod
    def _run_interaction_gen(cls, inst, timeline):
        global _monitor_alarm

        if _monitor_alarm is not None:
            alarms.cancel_alarm(_monitor_alarm)
            _monitor_alarm = None
            show_story_dialog("🛑 Monitoring stopped.")
        else:
            show_story_dialog("⚠️ No monitoring is currently running.")

        return True
