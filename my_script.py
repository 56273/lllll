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
MOD_VERSION = "V24.0"
AUTHOR = "kekell"
_log_buffer = []
_last_zone_id = None
_sim_mood_cache = {}
_monitor_alarm = None
_sim_last_action_cache = {}

# =======================================================
# 1. 核心工具箱
# =======================================================

def get_desktop_path():
    """ 尝试获取真实的桌面路径 """
    return os.path.join(os.path.expanduser("~"), "Desktop")
def log_error(error_msg, context=""):
    """ 记录错误到桌面的 error.txt """
    try:
        error_path = os.path.join(get_desktop_path(), "Sims4_Error_Log.txt")
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

        # 2. 天气
        # 2. 天气
        # 2. 天气（使用 .name 属性，测试证明有效）
        # 2. 天气（使用 .name 属性）
        weather_str = "Clear"
        try:
            ws = services.weather_service()
            if ws and hasattr(ws, 'get_current_weather_types'):
                weather_types = ws.get_current_weather_types()
                log_error(f"天气对象总数: {len(weather_types) if weather_types else 0}", "weather")

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
                                log_error(f"天气{i + 1} .name: '{name}'", "weather")

                            if not name and hasattr(wt, '__name__'):
                                name = wt.__name__
                                log_error(f"天气{i + 1} __name__: '{name}'", "weather")

                            if name:
                                name = name.replace('WeatherType.', '').replace('WeatherType_', '')
                                name = name.replace('Weather_', '').replace('_', ' ').strip()

                                if name and name != 'WeatherType':
                                    weather_names.append(name)
                                    log_error(f"天气{i + 1} 添加: '{name}'", "weather")
                        except Exception as e:
                            log_error(f"天气{i + 1} 报错: {str(e)}", "weather")

                    if weather_names:
                        weather_str = '+'.join(weather_names)

        except Exception as e:
            log_error(f"Weather error: {str(e)}", "get_header_context")

        # 3. 地点 (优先抓取真实名字，抓不到则抓类型)
        # 3. 地点 (优先抓取真实名字，抓不到则抓类型)
        venue_str = "Home"
        try:
            zone = services.current_zone()
            if zone:
                # 【尝试1】抓取区域描述文本
                if hasattr(zone, 'description') and zone.description:
                    venue_str = str(zone.description)
                    log_error(f"Got zone.description: {venue_str}", "get_header_context")
                # 【尝试2】抓取区域名字
                elif hasattr(zone, 'name') and zone.name:
                    venue_str = str(zone.name)
                    log_error(f"Got zone.name: {venue_str}", "get_header_context")
                # 【尝试3】抓取地段类型
                else:
                    venue_service = services.venue_service()
                    if venue_service and venue_service.active_venue:
                        raw_name = type(venue_service.active_venue).__name__
                        venue_str = raw_name.replace('Venue_', '').replace('_', ' ')
                        log_error(f"Got venue type: {venue_str}", "get_header_context")
                    else:
                        log_error("No venue info available", "get_header_context")
            else:
                log_error("current_zone is None", "get_header_context")
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
    """ 过滤垃圾动作 """
    action = action_name.lower()
    # 黑名单：这些动作太琐碎，不需要记录
    blacklist = [
        'stand', 'idle', 'route', 'monitor', 'situation', 'dream', 'sleep_rose',
        'nap', 'listen', 'watch', 'wait', 'check', 'carry', 'putdown',
        'picker', 'chooser', 'si_touching', 'create_and_use', 'passive',
        'posture', 'adjustment', 'generic', 'autonomy', 'reaction',
        'job_performance', 'buff_', 'mixer','flush', 'washhands','moveaway'
    ]
    if any(x in action for x in blacklist):
        # 白名单：虽然包含黑名单词，但这些很重要
        whitelist = ['chat', 'kiss', 'flirt', 'fight', 'woohoo', 'dance', 'propose', 'wedding', 'hug', 'express']
        if not any(w in action for w in whitelist):
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


# ========== 👇 在这里添加下面 4 个新函数 👇 ==========

def get_active_characters_summary():
    """
    获取当前活跃角色的特征摘要
    包括：1) 所有家庭成员, 2) 日志中频繁出现的 NPC
    """
    try:
        client = services.client_manager().get_first_client()
        if not client:
            log_error("get_active_characters_summary: client 为 None", "summary")
            return ""

        summary_lines = ["📋 Characters:"]
        captured_sims = set()  # 记录已处理的名字，避免重复

        selectable = list(client.selectable_sims)
        log_error(f"家庭成员数量: {len(selectable)}", "summary")

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

            log_error(f"处理家庭成员: {sim_name}", "summary")

            traits_str = _get_sim_traits(sim_info)

            if traits_str:
                summary_lines.append(f"  • {sim_name}: {traits_str}")
            else:
                summary_lines.append(f"  • {sim_name}: (无特征)")

            captured_sims.add(sim_name)

        # === 第二部分：日志中频繁出现的 NPC ===
        npc_counts = _count_npcs_in_log()
        log_error(f"NPC 统计结果: {npc_counts}", "summary")

        for npc_name, count in npc_counts.items():
            log_error(f"检查 NPC: {npc_name}, 出现 {count} 次", "summary")

            if count >= 3 and npc_name not in captured_sims:
                npc_sim_info = _find_sim_info_by_name(npc_name)

                if npc_sim_info:
                    log_error(f"找到 NPC sim_info: {npc_name}", "summary")
                    traits_str = _get_sim_traits(npc_sim_info)

                    if traits_str:
                        summary_lines.append(f"  • {npc_name} (NPC): {traits_str}")
                        log_error(f"NPC {npc_name} 特征: {traits_str}", "summary")
                    else:
                        summary_lines.append(f"  • {npc_name} (NPC): (无特征)")
                        log_error(f"NPC {npc_name} 无特征", "summary")
                else:
                    log_error(f"找不到 NPC sim_info: {npc_name}", "summary")

        return "\n".join(summary_lines) if len(summary_lines) > 1 else ""
    except Exception as e:
        log_error(f"get_active_characters_summary 报错: {str(e)}", "summary")
        return ""


def _get_sim_traits(sim_info):
    """ 提取 Sim 的性格特征（辅助函数）"""
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

                    # 智能清理：提取最后一个有意义的部分
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

                    log_error(f"特征处理: {trait_name} -> {display_name}", "traits")

                    if display_name and len(display_name) < 50:
                        traits.append(display_name)
                except:
                    pass
    except Exception as e:
        log_error(f"_get_sim_traits 报错: {str(e)}", "traits")

    return ', '.join(traits[:5]) if traits else ""


def _count_npcs_in_log():
    """ 统计当前日志中每个 Sim 出现的次数 """
    counts = {}
    try:
        client = services.client_manager().get_first_client()
        if not client:
            return counts

        # 获取家庭成员名字（用于排除）
        family_names = {sim_info.full_name for sim_info in client.selectable_sims}

        # 遍历日志
        for entry in _log_buffer:
            # 简单的名字提取（假设格式是 "[时间] 名字 -> ..."）
            if '->' in entry:
                parts = entry.split('->')
                if len(parts) >= 2:
                    # 提取第一个名字（动作发起者）
                    name_part = parts[0].strip()
                    # 去掉时间戳
                    if ']' in name_part:
                        name = name_part.split(']')[-1].strip()
                        # 去掉情绪部分（如果有）
                        if '(' in name:
                            name = name.split('(')[0].strip()

                        # 如果不是家庭成员，计数
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
            _sim_mood_cache.clear()  # 换地图清空情绪缓存
            _sim_last_action_cache.clear()  # 同时清空动作缓存，避免误判
        _last_zone_id = current_zone
        # ------------------

        sim = getattr(self, 'sim', None)
        if sim:
            # 只有当 主控Sim 或 目标是主控Sim 时才记录
            actor_is_family = is_active_sim(sim)
            target = getattr(self, 'target', None)
            target_is_family = False
            if target and hasattr(target, 'is_sim') and target.is_sim:
                target_is_family = is_active_sim(target)

            if actor_is_family or target_is_family:
                # 获取动作名
                raw_action = type(self).__name__
                if hasattr(self, 'affordance') and self.affordance:
                    raw_action = self.affordance.__name__

                action = clean_string(raw_action)

                if is_meaningful(action) and action:
                    # ===【智能防刷屏逻辑 - 方案B】===
                    sim_id = str(sim.id)
                    last_action = _sim_last_action_cache.get(sim_id, "")

                    # 获取目标物品名称
                    target = getattr(self, 'target', None)
                    target_name = get_target_name_smart(target) if target else ""

                    # 组合成"动作+物品"的键（比如 "Play Game-Motiongamerig"）
                    action_key = f"{action}-{target_name}"

                    # 【新增】如果是社交互动，添加时间戳，防止被误判为重复
                    if any(keyword in action.lower() for keyword in
                           ['social', 'romance', 'kiss', 'flirt', 'hug', 'chat']):
                        action_key += f"-{get_log_time()}"  # ✓ 用函数调用，不用变量

                    # 如果同一个Sim对同一个物品做类似动作（比如一直玩游戏），就跳过
                    if action_key == last_action:
                        return Interaction._original_trigger_backup(self, *args, **kwargs)

                    # 更新缓存
                    _sim_last_action_cache[sim_id] = action_key
                    # ===【防刷屏结束】===

                    display_name = get_sim_name_robust(sim)
                    # ... (后面的代码不用动)
                    display_name = get_sim_name_robust(sim)
                    time_str = get_log_time()

                    target_str = ""
                    if target:
                        t_name = get_target_name_smart(target)
                        if t_name != display_name:
                            target_str = f" -> {t_name}"

                    # 只有是主控自己在做动作时，才检查情绪变化
                    current_mood_str = ""
                    if actor_is_family:
                        current_mood_str = get_mood_delta(sim)

                    # 组装日志条目
                    entry = f"{time_str} {display_name}{current_mood_str} -> {action}{target_str}"

                    # 避免重复记录完全相同的动作
                    if not _log_buffer or _log_buffer[-1] != entry:
                        _log_buffer.append(entry)

                        # 内存保护：如果 buffer 太大，强制清理前面的，防止爆内存
                        if len(_log_buffer) > 500:
                            _log_buffer.pop(0)

    except Exception as e:
        # 不让报错影响游戏运行
        pass

    return Interaction._original_trigger_backup(self, *args, **kwargs)


Interaction._trigger_interaction_start_event = _new_trigger_start


# =======================================================
# 3. 自动监测核心 (Inbox Monitoring)
# =======================================================

def get_inbox_path():
    return os.path.join(get_desktop_path(), "Sims4_Inbox.txt")


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
        # 尝试读取
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if content:
            # 弹窗
            show_story_dialog(content)
            # 清空信箱
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
    except:
        pass


# =======================================================
# 4. 命令区 (Commands)
# =======================================================

@sims4.commands.Command('save_now', command_type=sims4.commands.CommandType.Live)
def save_now_command(_connection=None):
    """ 手动存档指令 - 保存到两个文件 """
    output = sims4.commands.CheatOutput(_connection)

    # 两个文件路径
    path_full = os.path.join(get_desktop_path(), "Sims4_Story_Log_Full.txt")
    path_latest = os.path.join(get_desktop_path(), "Sims4_Story_Log_Latest.txt")

    try:
        if not _log_buffer:
            output(f"📝 No new logs to save. ({MOD_VERSION})")
            return

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

        # 文件1：累积版（追加模式 "a"）
        with open(path_full, "a", encoding="utf-8") as f:
            f.write(full_content)

        # 文件2：最新版（覆盖模式 "w"）
        with open(path_latest, "w", encoding="utf-8") as f:
            f.write(full_content)

        count = len(_log_buffer)
        output(f"✅ Saved ({count} entries) - {MOD_VERSION}")
        output(f"📁 Full: Sims4_Story_Log_Full.txt")
        output(f"📄 Latest: Sims4_Story_Log_Latest.txt")

        _log_buffer.clear()

    except Exception as e:
        output(f"❌ Save failed: {e}")


@sims4.commands.Command('start_ai', command_type=sims4.commands.CommandType.Live)
def start_ai_monitor(_connection=None):
    """ 开启弹窗监测 """
    global _monitor_alarm
    output = sims4.commands.CheatOutput(_connection)

    if _monitor_alarm is not None:
        output(f"⚠️ AI监测已经在运行中了！ ({MOD_VERSION})")
        return

    client = services.client_manager().get_first_client()
    if not client:
        output("❌ 请先进入生活模式")
        return

    # 每 5 秒检查一次信箱
    _monitor_alarm = alarms.add_alarm_real_time(
        client,
        clock.interval_in_real_seconds(5),
        check_inbox_logic,
        repeating=True
    )
    output(f"🚀 AI信箱监测已启动！等待剧情投送... ({MOD_VERSION})")


@sims4.commands.Command('stop_ai', command_type=sims4.commands.CommandType.Live)
def stop_ai_monitor(_connection=None):
    """ 停止弹窗监测 """
    global _monitor_alarm
    output = sims4.commands.CheatOutput(_connection)

    if _monitor_alarm is not None:
        alarms.cancel_alarm(_monitor_alarm)
        _monitor_alarm = None
        output("🛑 监测已停止。")
    else:
        output("⚠️ 当前没有运行监测。")


# =======================================================
# 🧪 测试区 (Test Commands) - 用于调试天气和地段抓取
# =======================================================

def show_test_result(title, content):
    """ 弹窗显示测试结果 """
    client = services.client_manager().get_first_client()
    if not client: return

    dialog = ui.ui_dialog.UiDialogOkCancel.TunableFactory().default(
        client.active_sim,
        text=lambda *args: LocalizationHelperTuning.get_raw_text(content),
        title=lambda *args: LocalizationHelperTuning.get_raw_text(f"🧪 {title}")
    )
    dialog.show_dialog()


# === 天气测试 ===




@sims4.commands.Command('test_weather_final', command_type=sims4.commands.CommandType.Live)
def test_weather_final(_connection=None):
    """ 最终天气测试：深挖每个天气对象 """
    result = "❌ 测试失败"
    try:
        ws = services.weather_service()
        if ws and hasattr(ws, 'get_current_weather_types'):
            weather_types = ws.get_current_weather_types()

            result = f"✅ 当前天气 ({len(weather_types)} 个):\n\n"

            for i, wt in enumerate(weather_types):
                result += f"天气 {i + 1}:\n"

                # 尝试多种方式获取名字
                methods = [
                    ('__name__', lambda: wt.__name__ if hasattr(wt, '__name__') else None),
                    ('name', lambda: wt.name if hasattr(wt, 'name') else None),
                    ('guid64', lambda: wt.guid64 if hasattr(wt, 'guid64') else None),
                    ('type().__name__', lambda: type(wt).__name__),
                    ('str()', lambda: str(wt)),
                ]

                for method_name, method_func in methods:
                    try:
                        value = method_func()
                        if value and str(value) != 'WeatherType':
                            result += f"  {method_name}: {value}\n"
                    except:
                        pass

                result += "\n"

                if i >= 2:  # 只显示前3个
                    result += f"...(还有 {len(weather_types) - 3} 个)\n"
                    break

        else:
            result = "❌ 方法不存在"
    except Exception as e:
        result = f"❌ 报错: {str(e)[:300]}"

    show_test_result("天气最终测试", result)


@sims4.commands.Command('test_weather_check', command_type=sims4.commands.CommandType.Live)
def test_weather_check(_connection=None):
    """ 天气方案：逐个检查已知天气类型 """
    result = "✅ 当前天气检查:\n\n"
    try:
        ws = services.weather_service()
        if ws:
            # 常见的天气类型（根据之前看到的常量推测）
            weather_names = [
                'Rain', 'Snow', 'Sunny', 'Cloudy', 'Storm',
                'Cold', 'Hot', 'Windy', 'Clear', 'Fog'
            ]

            active_weather = []

            # 如果有 has_weather_type 方法
            if hasattr(ws, 'has_weather_type'):
                result += "使用 has_weather_type 检查:\n"
                # 这里需要实际的天气类型常量...
                result += "(需要实际的天气类型对象)\n\n"

            # 尝试从 get_current_weather_types 提取
            if hasattr(ws, 'get_current_weather_types'):
                types = ws.get_current_weather_types()
                result += f"get_current_weather_types 返回了 {len(types)} 个对象\n\n"

            # 检查天气效果类型
            result += "天气效果检查:\n"
            try:
                from weather.weather_enums import WeatherEffectType

                # 检查几个关键的
                checks = [
                    ('下雨', WeatherEffectType.WINDOW_FROST),
                    ('下雪', WeatherEffectType.SNOW_ICINESS),
                    ('刮风', WeatherEffectType.WIND),
                ]

                for name, effect_type in checks:
                    if hasattr(ws, 'get_weather_element_value'):
                        try:
                            value = ws.get_weather_element_value(effect_type)
                            if value and value > 0:
                                result += f"- {name}: {value}\n"
                        except:
                            pass
            except:
                result += "(无法导入 WeatherEffectType)\n"

        else:
            result = "❌ weather_service 返回 None"
    except Exception as e:
        result = f"❌ 报错: {str(e)[:300]}"

    show_test_result("天气检查", result)
# === 综合测试 ===

@sims4.commands.Command('test_all', command_type=sims4.commands.CommandType.Live)
def test_all(_connection=None):
    """ 运行所有测试并生成报告 """
    output = sims4.commands.CheatOutput(_connection)
    output("🧪 开始运行所有测试...")
    output("请查看弹窗结果，然后依次输入:")
    output("test_weather_a, test_weather_b, test_weather_c")
    output("test_venue_a, test_venue_b, test_venue_c")


# =======================================================
# 5. 菜单交互类 (Pie Menu Interactions)
# =======================================================

from interactions.base.immediate_interaction import ImmediateSuperInteraction
from sims4.utils import flexmethod


class SaveLogInteraction(ImmediateSuperInteraction):
    """ 保存日志交互 """

    @flexmethod
    def _run_interaction_gen(cls, inst, timeline):
        try:
            path_full = os.path.join(get_desktop_path(), "Sims4_Story_Log_Full.txt")
            path_latest = os.path.join(get_desktop_path(), "Sims4_Story_Log_Latest.txt")

            if not _log_buffer:
                show_story_dialog(f"📝 No new logs to save. ({MOD_VERSION})")
                return True

            header = f"\n--- Save {get_header_context()} ---\n"
            characters_info = get_active_characters_summary()

            content_lines = [header]
            if characters_info:
                content_lines.append(characters_info + "\n")

            for line in _log_buffer:
                content_lines.append(line + "\n")

            full_content = "".join(content_lines)

            with open(path_full, "a", encoding="utf-8") as f:
                f.write(full_content)

            with open(path_latest, "w", encoding="utf-8") as f:
                f.write(full_content)

            count = len(_log_buffer)
            show_story_dialog(
                f"✅ Saved {count} entries\n📁 Full: Sims4_Story_Log_Full.txt\n📄 Latest: Sims4_Story_Log_Latest.txt")
            _log_buffer.clear()
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
        show_story_dialog(f"🚀 AI inbox monitoring started!\nWaiting for stories... ({MOD_VERSION})")
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