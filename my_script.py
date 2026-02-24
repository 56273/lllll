import sims4.commands
import sims4.resources
import services
import os
import alarms
import clock
import ui.ui_dialog
from interactions.base.interaction import Interaction
from sims4.localization import LocalizationHelperTuning
import json



# =======================================================
# 💾 全局配置 & 变量
# =======================================================
MOD_VERSION = "V25.0"
AUTHOR = "kekell"
_log_buffer = []
_last_zone_id = None
_sim_mood_cache = {}
_monitor_alarm = None
_debug_raw_log = []        # 新增：调试用
_debug_filtered_log = []   # 新增：调试用
_debug_mode = False        # 新增：调试用
_sim_last_action_cache = {}
_output_dir = None  # 缓存输出目录，避免每次都重新查找
_rel_cache = {}
_friendship_track = None
_romance_track = None
_npc_seen = set()  # 已经生成过快照的 NPC sim_id
_pending_story = None

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
    从配置读取用户自定义的保存路径
    优先级：JSON配置 → 旧的TXT配置（向下兼容）
    """
    mods_folder = _find_sims4_mods_folder()
    if not mods_folder:
        return None

    # 1. 优先读 JSON（新格式）
    json_path = os.path.join(mods_folder, "AI_Storyteller_Settings.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            custom_path = data.get("save_path", "").strip()
            if custom_path and os.path.isdir(custom_path):
                return custom_path
        except:
            pass

    # 2. 向下兼容旧的 TXT 配置
    config_path = os.path.join(mods_folder, "AI_Storyteller_Config.txt")
    if not os.path.exists(config_path):
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("//"):
                    continue
                if line.startswith("save_path="):
                    custom_path = line.split("=", 1)[1].strip()
                    custom_path = custom_path.strip('"').strip("'")
                    if custom_path and os.path.isdir(custom_path):
                        return custom_path
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

def _safe_name(sim_info):
    """安全取名（修复 full_name 为空的 bug）"""
    if sim_info is None:
        return "?"
    try:
        first = sim_info.first_name or ''
        last = sim_info.last_name or ''
        name = f"{first} {last}".strip()
        return name if name else f"Sim({sim_info.sim_id})"
    except:
        return "?"


def _first_name(sim_info):
    """只取名字（不含姓）"""
    if sim_info is None:
        return "?"
    try:
        return sim_info.first_name or f"Sim({sim_info.sim_id})"
    except:
        return "?"


def _gender_tag(sim_info):
    try:
        return "M" if sim_info.gender.name == "MALE" else "F"
    except:
        return "?"


def _age_tag(sim_info):
    try:
        age_map = {
            'BABY': 'Baby', 'INFANT': 'Infant', 'TODDLER': 'Toddler',
            'CHILD': 'Child', 'TEEN': 'Teen', 'YOUNGADULT': 'YA',
            'ADULT': 'Adult', 'ELDER': 'Elder'
        }
        return age_map.get(sim_info.age.name, sim_info.age.name)
    except:
        return "?"
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
def get_pending_events_path():
    return os.path.join(get_output_directory(), "Sims4_PendingEvents.txt")

def get_character_profile_path():
    return os.path.join(get_output_directory(), "Character_Profile.txt")

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

        event_str = ""
        try:
            events = []
            # 方法1: 从 situation 抓节日/派对
            sm = services.get_zone_situation_manager()
            if sm:
                has_holiday_situation = False
                for sit in sm.running_situations():
                    sit_name = type(sit).__name__.lower()
                    if 'holiday' in sit_name:
                        has_holiday_situation = True
                    elif 'party' in sit_name or 'gathering' in sit_name:
                        if "Party" not in events:
                            events.append("Party")
                    elif 'festival' in sit_name:
                        if "Festival" not in events:
                            events.append("Festival")
                    elif 'wedding' in sit_name:
                        if "Wedding" not in events:
                            events.append("Wedding")
                    elif 'birthday' in sit_name:
                        if "Birthday" not in events:
                            events.append("Birthday")

                # 方法2: 如果检测到节日situation，从drama节点拿具体名字
                if has_holiday_situation:
                    holiday_name = ""
                    try:
                        ds = services.drama_scheduler_service()
                        if ds:
                            for node in ds.active_nodes_gen():
                                node_name = type(node).__name__
                                if 'holiday' in node_name.lower():
                                    # 从 dramaNode_PremadeHoliday_Surprise_PrankDay
                                    # 提取 PrankDay 这样的名字
                                    clean = node_name.replace('dramaNode_', '')
                                    clean = clean.replace('PremadeHoliday_', '')
                                    clean = clean.replace('Holiday_', '')
                                    clean = clean.replace('Surprise_', '')
                                    clean = clean.replace('_', ' ').strip()
                                    if clean and len(clean) > 2:
                                        holiday_name = clean
                                        break
                    except:
                        pass

                    if not holiday_name:
                        holiday_name = "Holiday"
                    if holiday_name not in events:
                        events.append(holiday_name)

            if events:
                event_str = " | " + ", ".join(events[:2])
        except:
            pass


        return f"{time_str} {day_str}|{weather_str} @{venue_str}{event_str}"
    except:
        return "[--:--]"

def get_log_time():
    """ 单行日志极简时间 """
    try:
        now = services.game_clock_service().now()
        return f"[{now.hour():02d}:{now.minute():02d}]"
    except:
        return "[--:--]"

def _init_rel_tracks():
    """初始化友谊和浪漫 track 对象（只跑一次）"""
    global _friendship_track, _romance_track
    try:
        if _friendship_track is not None:
            return
        mgr = services.get_instance_manager(sims4.resources.Types.STATISTIC)
        if mgr:
            _friendship_track = mgr.get(16650)
            _romance_track = mgr.get(16651)
    except:
        pass


def _get_rel_change(actor_info, target_info):
    """获取关系值变化，返回如 ' F+5/R-3' 或空字符串"""
    global _rel_cache
    _init_rel_tracks()

    try:
        actor_id = actor_info.sim_id
        target_id = target_info.sim_id
        tracker = actor_info.relationship_tracker
        key = (actor_id, target_id)

        # 获取当前分数
        f_now = 0.0
        r_now = 0.0
        if _friendship_track:
            try:
                f_now = tracker.get_relationship_score(target_id, _friendship_track)
            except:
                pass
        if _romance_track:
            try:
                r_now = tracker.get_relationship_score(target_id, _romance_track)
            except:
                pass

        # 对比上次
        if key in _rel_cache:
            old_f, old_r = _rel_cache[key]
            df = round(f_now - old_f)
            dr = round(r_now - old_r)

            # 更新缓存
            _rel_cache[key] = (f_now, r_now)

            # 只有变化时才显示
            if df == 0 and dr == 0:
                return ""

            parts = []
            if df != 0:
                parts.append(f"F{df:+d}")
            if dr != 0:
                parts.append(f"R{dr:+d}")
            return " " + "/".join(parts)
        else:
            # 第一次见到这对关系，显示当前总值
            _rel_cache[key] = (f_now, r_now)
            f_int = round(f_now)
            r_int = round(r_now)
            if f_int != 0 or r_int != 0:
                return " [F{}/R{}]".format(f_int, r_int)
            return ""

    except:
        return ""

def clean_string(text):
    """ 清洗代码名，使其更像人类语言 """
    if not text: return ""

    # 去掉社交互动前缀（最重要的清洗）
    prefixes_to_remove = [
        'mixer_social_', 'mixer_socials_', 'mixer_Social_',
        'socialMixer_', 'socials_Targeted_', 'socials_',
        'social_Funny_', 'sim_', 'si_',
        'object_', 'Venue_', 'interaction_',
    ]
    for prefix in prefixes_to_remove:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    # 去掉尾部标签（targeted_friendly_alwaysOn 等）
    tags_to_remove = [
        '_targeted_romance_alwaysOn', '_targeted_mean_alwaysOn',
        '_targeted_mean_emotionSpecific', '_targeted_mean',
        '_targeted_friendly_alwaysOn', '_targeted_Friendly_AlwaysOn',
        '_targeted_Friendly_MiddleScore',
        '_targeted_funny_alwaysOn', '_targeted_funny_alwaysOn_skills',
        '_targeted_mischief_skills',
        '_group_Funny_alwaysOn', '_group_funny_alwaysOn',
        '_group_funny_emotionSpecific',
        '_group_funny_MediumScore_child',
        '_alwaysOn', '_AlwaysOn',
        '_alwaysOn_skills', '_AlwaysOn_coworkers',
        '_Mean_STC', '_Mean_AlwaysOn',
    ]
    for tag in tags_to_remove:
        text = text.replace(tag, '')

    # 去掉杂音词
    trash_list = ['SI', 'Action', 'OneShot', 'Passive', 'Looping',
                  'Touch', 'Adjustment', 'Super', 'Active']
    for trash in trash_list:
        text = text.replace(trash, '')

    text = text.replace('_', ' ').strip()
    return text.title()


def get_sim_name_robust(sim):
    """安全获取 Sim 名字（修复 full_name 在某些语言为空的 bug）"""
    try:
        si = sim.sim_info if hasattr(sim, 'sim_info') else sim
        return _safe_name(si)
    except:
        sim_id = str(sim.id) if hasattr(sim, 'id') else "?"
        return f"Sim({sim_id})"


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

    # 白名单最优先：这些无论如何都保留
    whitelist = [
        'kiss', 'flirt', 'fight', 'woohoo', 'dance', 'propose',
        'wedding', 'hug', 'express', 'compliment', 'insult', 'joke',
        'gossip', 'encourage', 'secret', 'romance', 'mean', 'friendly',
        'mischief', 'yell', 'chew', 'scare', 'impression', 'lash',
        'swear', 'attraction', 'reach', 'recipe', 'gourmet', 'weather',
        'affectionate', 'greet', 'wave goodbye', 'introduction',
        'cry', 'calm', 'peptalk', 'pushups', 'practice', 'paint',
        'cook', 'repair', 'upgrade', 'garden', 'fish', 'write',
        'read', 'play', 'sing', 'guitar', 'violin', 'dj',
        'woohoo', 'tryfor', 'bath', 'shower', 'wash dish',
        'homework', 'skill', 'work', 'career',
        'drink', 'spell', 'knit', 'photo',
        'ballroom', 'kick', 'pickup',
    ]
    if any(w in action for w in whitelist):
        return True

    # 黑名单：这些过滤掉
    blacklist = [
        'stand', 'idle', 'route', 'monitor', 'situation', 'dream',
        'nap', 'watch', 'wait', 'check', 'carry', 'putdown',
        'picker', 'chooser', 'touching', 'create_and_use', 'passive',
        'posture', 'adjustment', 'generic', 'autonomy', 'reaction',
        'job_performance', 'buff_', 'mixer', 'flush', 'moveaway',
        'chatting', 'stc', 'sim-stand',
        'push_leave', 'npcleave', 'leave_lot',
        'welcomewagon', 'aggregate', 'autonomous',
        'emotion_idle', 'emotion_failure',
        'marketstalls_mixers', 'food_eat',
        'holdobj', 'put_down', 'switch_to_default',
        'earbuds', 'swipe', 'deploy', 'satisfy',
        'socialpicker','ai','log','tamponpad','plasmapack','mccommander',
        'opensimprofile'
    ]
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

# =====================================================
# Bit 分类引擎
# =====================================================

_NOISE = [
    'has_met', 'infant_CheckOn', 'SpecialBits_Greeted',
    'relbit_SocialContext', 'shortTermBit_Dynasty', 'HasBeenFriends',
    'relationshipbit_Compatibility', 'bit_NoLongerFriends',
    'Lumpinou_', 'TURBODRIVER:', 'NisaK:',
    'lifeMilestoneBit_', 'romantic_FirstKiss',
    'HaveBeenRomantic', 'relationshipbit_CoWorkers',
    'shortTermBits_healedNegative',
    'relationshipBit_Wedding',
    'WickedWhims', 'friendship-',
    'romantic-HaveDoneWooHoo',
]


def _classify_all_bits(bits):
    result = {
        'family': [],
        'family_trope': [],
        'romance': [],
        'attraction': [],
        'sentiment': [],
        'scandal': [],
    }

    for bit in bits:
        name = bit.__name__ if hasattr(bit, '__name__') else str(bit)

        if any(skip in name for skip in _NOISE):
            continue

        # === 家庭 ===
        if 'family_Target_' in name:
            rel = name.replace('family_Target_', '').replace('_Actor', '').replace('Of', '')
            family_map = {
                'IsParent': 'Parent',
                'IsSonOrDaughter': 'Child',
                'IsBrotherSister': 'Sibling',
                'IsHalfsibling': 'HalfSibling',
                'IsGrandparent': 'Grandparent',
                'IsGrandchild': 'Grandchild',
                'IsAuntUncle': 'Aunt/Uncle',
                'IsNieceNephew': 'Niece/Nephew',
                'IsCousin': 'Cousin',
                'IsStepSibling': 'StepSibling',
                'IsStepParent': 'StepParent',
                'IsStepChild': 'StepChild',
                'IsSiblingInLaw': 'InLaw',
            }
            for key, label in family_map.items():
                if key in rel:
                    result['family'].append(label)
                    break
            else:
                result['family'].append(rel)
            continue

        if 'RomanticCombo_' in name:
            result['romance'].append(name.replace('RomanticCombo_', ''))
            continue

        if 'romanceTrope_' in name:
            result['romance'].append(name.replace('romanceTrope_', ''))
            continue

        if name == 'romantic-Married':
            result['romance'].append('Married')
            continue

        if name == 'romantic-Engaged':
            result['romance'].append('Engaged')
            continue

        if 'CheatedWith' in name:
            result['romance'].append('CheatedWith')
            continue

        if 'romantic-Significant' in name:
            result['romance'].append('Significant')
            continue

        if 'relBit_Attraction_' in name:
            label = name.split('Actor_')[-1].replace('_Target', '').replace('_', '')
            result['attraction'].append(label)
            continue

        if 'relBit_RelSat_' in name:
            label = name.split('Actor_')[-1].replace('_Target', '').replace('With', '').replace('_', '')
            result['attraction'].append(label)
            continue

        if 'SecretChild' in name or 'Scandal' in name:
            label = name.replace('relbit_', '').replace('_', ' ')
            result['scandal'].append(label)
            continue

        if 'sentimentBit_' in name:
            clean = name.replace('sentimentBit_Actor_', '').replace('_Target', '')
            duration = "ST"
            if '_LT_' in clean:
                duration = "LT"
                parts = clean.split('_LT_', 1)
                emotion = parts[0]
                reason = parts[1] if len(parts) > 1 else ""
            elif '_ST_' in clean:
                duration = "ST"
                parts = clean.split('_ST_', 1)
                emotion = parts[0]
                reason = parts[1] if len(parts) > 1 else ""
            else:
                emotion = clean
                reason = ""

            emotion = emotion.replace('To_', '').replace('By_', '').replace('At_', '')
            emotion = emotion.replace('_', '')
            reason = reason.replace('_', ' ').strip()

            if reason:
                label = f"{emotion}({duration}:{reason})"
            else:
                label = f"{emotion}({duration})"

            result['sentiment'].append((duration, label))
            continue

        if 'romantic-' in name:
            result['romance'].append(name.replace('romantic-', ''))
            continue

        if 'Rivalry' in name:
            result['family'].append('Rival')
            continue

        if 'familyTrope_' in name:
            label = name.replace('familyTrope_', '')
            result['family_trope'].append(label)
            continue

    result['sentiment'].sort(key=lambda x: (0 if x[0] == 'LT' else 1, x[1]))
    result['sentiment'] = [item[1] for item in result['sentiment']]

    return result
# ========== 角色特征抓取 ==========

def get_active_characters_summary():
    """新版角色摘要 V2"""
    try:
        client = services.client_manager().get_first_client()
        if not client:
            return ""

        members = list(client.selectable_sims)
        if not members:
            return ""

        lines = []

        # 1. 成员列表
        lines.append("📋 Household Members:")
        for si in members:
            name = _safe_name(si)
            g = _gender_tag(si)
            a = _age_tag(si)
            traits = _get_sim_traits(si)
            t_str = f" [{traits}]" if traits else ""
            lines.append(f"  • {name} ({g}/{a}){t_str}")

        # 收集关系
        all_family = []
        all_romance = []
        all_attraction = []
        all_sentiment = []
        all_scandal = []
        spouse_pairs = set()
        pair_tropes = {}  # {sorted_pair: [tropes]}

        for si in members:
            tracker = si.relationship_tracker
            a_name = _first_name(si)
            a_gender = _gender_tag(si)

            for other in members:
                if si.sim_id == other.sim_id:
                    continue
                if not tracker.has_relationship(other.sim_id):
                    continue

                bits = tracker.get_all_bits(other.sim_id)
                if not bits:
                    continue

                b_name = _first_name(other)
                classified = _classify_all_bits(bits)

                for fam in classified['family']:
                    if fam == 'Child':
                        parent_label = "Father" if a_gender == "M" else "Mother"
                        all_family.append((a_name, b_name, parent_label))
                    elif fam == 'Parent':
                        pass
                    elif fam == 'Sibling':
                        pair = tuple(sorted([a_name, b_name]))
                        all_family.append((pair[0], pair[1], 'Siblings'))
                    elif fam == 'HalfSibling':
                        pair = tuple(sorted([a_name, b_name]))
                        all_family.append((pair[0], pair[1], 'HalfSiblings'))
                    elif fam == 'Rival':
                        all_family.append((a_name, b_name, 'Rival'))
                    elif fam == 'InLaw':
                        pair = tuple(sorted([a_name, b_name]))
                        all_family.append((pair[0], pair[1], 'InLaw'))
                    elif fam == 'Aunt/Uncle':
                        all_family.append((a_name, b_name, 'Aunt/Uncle'))
                    elif fam == 'Niece/Nephew':
                        pass
                    elif fam == 'Grandparent':
                        pass
                    elif fam == 'Grandchild':
                        all_family.append((a_name, b_name, 'Grandparent'))
                    else:
                        all_family.append((a_name, b_name, fam))

                if classified['romance']:
                    if 'Married' in classified['romance']:
                        pair = tuple(sorted([a_name, b_name]))
                        spouse_pairs.add(pair)
                    all_romance.append((a_name, b_name, classified['romance']))

                if classified['attraction']:
                    all_attraction.append((a_name, b_name, classified['attraction']))

                if classified['sentiment']:
                    all_sentiment.append((a_name, b_name, classified['sentiment']))

                if classified['scandal']:
                    all_scandal.append((a_name, classified['scandal']))

                if classified.get('family_trope'):
                    trope_key = tuple(sorted([a_name, b_name]))
                    for trope in classified['family_trope']:
                        pair_tropes[trope_key] = trope

        # 2. Family
        lines.append("")
        lines.append("🔗 Family:")

        for pair in spouse_pairs:
            lines.append(f"  ♥ {pair[0]} & {pair[1]}: Spouse")

        parent_children = {}
        for a, b, label in all_family:
            if label in ('Father', 'Mother'):
                key = (a, label)
                if key not in parent_children:
                    parent_children[key] = []
                if b not in parent_children[key]:
                    parent_children[key].append(b)
        for (parent, label), children in parent_children.items():
            lines.append(f"  {parent} → {', '.join(children)}: {label}")

        seen_sym = set()
        for a, b, label in all_family:
            if label in ('Siblings', 'HalfSiblings', 'InLaw'):
                key = (tuple(sorted([a, b])), label)
                if key not in seen_sym:
                    seen_sym.add(key)
                    trope = pair_tropes.get(tuple(sorted([a, b])), "")
                    trope_str = f", {trope}" if trope else ""
                    lines.append(f"  {a} & {b}: {label}{trope_str}")

        aunt_nephews = {}
        for a, b, label in all_family:
            if label == 'Aunt/Uncle':
                if a not in aunt_nephews:
                    aunt_nephews[a] = []
                if b not in aunt_nephews[a]:
                    aunt_nephews[a].append(b)
        for aunt, nephews in aunt_nephews.items():
            lines.append(f"  {aunt} → {', '.join(nephews)}: Aunt/Uncle")

        gp_map = {}
        for a, b, label in all_family:
            if label == 'Grandparent':
                if a not in gp_map:
                    gp_map[a] = []
                if b not in gp_map[a]:
                    gp_map[a].append(b)
        for gp, gc in gp_map.items():
            lines.append(f"  {gp} → {', '.join(gc)}: Grandparent")

        seen_rival = set()
        for a, b, label in all_family:
            if label == 'Rival':
                pair = tuple(sorted([a, b]))
                if pair not in seen_rival:
                    seen_rival.add(pair)
                    lines.append(f"  ⚡ {pair[0]} & {pair[1]}: Rival")

        # 3. Romance
        seen_romance = set()
        romance_lines = []
        for a, b, labels in all_romance:
            filtered = [l for l in labels if l != 'Married']
            if not filtered:
                continue
            key = tuple(sorted([a, b]))
            if key in seen_romance:
                continue
            seen_romance.add(key)
            romance_lines.append(f"  {a} → {b}: {', '.join(filtered)}")
        if romance_lines:
            lines.append("")
            lines.append("💕 Romance:")
            lines.extend(romance_lines)

        # 4. Attraction
        if all_attraction:
            lines.append("")
            lines.append("💫 Attraction:")
            for a, b, labels in all_attraction:
                lines.append(f"  {a} → {b}: {', '.join(labels)}")

        # 5. Sentiments
        if all_sentiment:
            lines.append("")
            lines.append("💭 Sentiments:")
            for a, b, labels in all_sentiment:
                lines.append(f"  {a} → {b}: {', '.join(labels)}")

        # 6. Scandal
        if all_scandal:
            lines.append("")
            lines.append("🔒 Scandal:")
            seen_sc = set()
            for a, labels in all_scandal:
                for label in labels:
                    key = (a, label)
                    if key not in seen_sc:
                        seen_sc.add(key)
                        lines.append(f"  {a}: {label}")

        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception as e:
        log_error(f"get_active_characters_summary error: {str(e)}", "summary")
        return ""

def build_npc_snapshot(npc_sim_info, active_sim_info):
    """NPC 第一次互动时生成快照"""
    try:
        npc_name = _safe_name(npc_sim_info)
        g = _gender_tag(npc_sim_info)
        a = _age_tag(npc_sim_info)
        traits = _get_sim_traits(npc_sim_info)
        t_str = f" [{traits}]" if traits else ""

        rel_str = ""
        active_name = _first_name(active_sim_info)
        tracker = active_sim_info.relationship_tracker

        if tracker.has_relationship(npc_sim_info.sim_id):
            bits = tracker.get_all_bits(npc_sim_info.sim_id)
            if bits:
                classified = _classify_all_bits(bits)
                parts = []
                if classified['family']:
                    parts.extend(classified['family'])
                if classified['romance']:
                    parts.extend(classified['romance'])
                if classified['attraction']:
                    parts.extend(classified['attraction'])
                if classified['sentiment']:
                    parts.extend(classified['sentiment'][:3])
                if classified['scandal']:
                    parts.extend(classified['scandal'])
                if parts:
                    rel_str = f" Rel({active_name}):{','.join(parts)}"

        return f"[NPC] {npc_name}({g}/{a}){t_str}{rel_str}"
    except:
        return f"[NPC] {_safe_name(npc_sim_info)}(?)"

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
            _npc_seen.clear()
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

                # === 调试模式：记录所有互动（含被过滤的）===
                if _debug_mode:
                    raw_info = f"[RAW] {raw_action} | cleaned: {action}"
                    if is_meaningful(action):
                        _debug_raw_log.append(raw_info)
                    else:
                        _debug_filtered_log.append(raw_info)
                # === 调试模式结束 ===

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

                    # === NPC 快照 ===
                    if target and hasattr(target, 'is_sim') and target.is_sim:
                        t_info = target.sim_info if hasattr(target, 'sim_info') else None
                        if t_info and not is_active_sim(target) and t_info.sim_id not in _npc_seen:
                            _npc_seen.add(t_info.sim_id)
                            try:
                                snapshot = build_npc_snapshot(t_info, sim.sim_info)
                                _log_buffer.append(snapshot)
                            except:
                                pass

                    display_name = get_sim_name_robust(sim)
                    time_str = get_log_time()

                    target_str = ""
                    rel_str = ""
                    if target:
                        t_name = get_target_name_smart(target)
                        if t_name != display_name:
                            target_str = f" -> {t_name}"

                        # 关系值追踪（目标是Sim时）
                        if hasattr(target, 'is_sim') and target.is_sim:
                            try:
                                rel_str = _get_rel_change(sim.sim_info, target.sim_info)
                            except:
                                pass

                    # 只有是主控自己在做动作时，才检查情绪变化
                    current_mood_str = ""
                    if actor_is_family:
                        current_mood_str = get_mood_delta(sim)

                    # 组装日志条目
                    entry = f"{time_str} {display_name}{current_mood_str} -> {action}{target_str}{rel_str}"

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

def show_confirm_dialog(text, title, on_ok, on_cancel=None):
    """
    显示带确认/取消按钮的弹窗，根据玩家选择执行不同操作
    on_ok: 点击OK时调用的函数
    on_cancel: 点击Cancel时调用的函数（可选）
    """
    client = services.client_manager().get_first_client()
    if not client:
        return

    dialog = ui.ui_dialog.UiDialogOkCancel.TunableFactory().default(
        client.active_sim,
        text=lambda *args: LocalizationHelperTuning.get_raw_text(text),
        title=lambda *args: LocalizationHelperTuning.get_raw_text(title)
    )

    def _on_response(d):
        try:
            if d.accepted:
                if on_ok:
                    on_ok()
            else:
                if on_cancel:
                    on_cancel()
        except Exception as e:
            log_error(f"Dialog response error: {e}", "confirm_dialog")

    dialog.add_listener(_on_response)
    dialog.show_dialog()


def check_inbox_logic(_):
    """ 定时检查信箱，缓存内容等待玩家手动查看 """
    global _pending_story
    path = get_inbox_path()
    if not os.path.exists(path): return

    try:
        content = ""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if content:
            _pending_story = content
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


@sims4.commands.Command('ai_setpath', command_type=sims4.commands.CommandType.Live)
def set_path_command(*args, _connection=None):
    """设置自定义保存路径并自动创建所需文件"""
    output = sims4.commands.CheatOutput(_connection)

    path_parts = [str(a) for a in args]
    custom_path = " ".join(path_parts).strip().strip('"').strip("'")

    if not custom_path:
        output("用法: ai_setpath 你的文件夹路径")
        output("例如: ai_setpath C:\\Users\\你的名字\\Desktop\\SimData")
        output(f"当前路径: {get_output_directory()}")
        return

    # 创建文件夹（不存在则创建）
    try:
        os.makedirs(custom_path, exist_ok=True)
    except Exception as e:
        output(f"❌ 路径无效: {e}")
        return

    # 所需文件列表，不存在就创建空文件
    required_files = [
        "Sims4_Story_Log_Full.txt",
        "Sims4_Story_Log_Latest.txt",
        "Sims4_Inbox.txt",
        "Story_Archive.txt",
        "Story_Memory.txt",
        "Sims4_PendingEvents.txt",
        "Character_Profile.txt",
        "Sims4_Error_Log.txt",
    ]

    created = 0
    for fname in required_files:
        fpath = os.path.join(custom_path, fname)
        if not os.path.exists(fpath):
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("")
                created += 1
            except Exception as e:
                output(f"⚠️ 无法创建 {fname}: {e}")

    # 保存到 JSON 配置
    mods_folder = _find_sims4_mods_folder()
    if mods_folder:
        config_json = os.path.join(mods_folder, "AI_Storyteller_Settings.json")
        try:
            config_data = {}
            if os.path.exists(config_json):
                try:
                    with open(config_json, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                except:
                    pass
            config_data["save_path"] = custom_path
            with open(config_json, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            output(f"⚠️ 配置保存失败: {e}")

    # 更新缓存
    global _output_dir
    _output_dir = custom_path

    output(f"✅ 路径已设置: {custom_path}")
    if created > 0:
        output(f"📄 新建了 {created} 个文件")
    else:
        output(f"📄 所有文件已就绪")

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

class ShowStoryInteraction(ImmediateSuperInteraction):
    """ 显示最新剧情交互 """

    @flexmethod
    def _run_interaction_gen(cls, inst, timeline):
        global _pending_story

        if _pending_story:
            show_story_dialog(_pending_story)
            _pending_story = None
        else:
            # 没有缓存的，再尝试直接读一次 inbox
            path = get_inbox_path()
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    if content:
                        show_story_dialog(content)
                        with open(path, "w", encoding="utf-8") as f:
                            f.write("")
                        return True
            except:
                pass
            show_story_dialog("📭 No new story yet.\nWaiting for AI to write...")

        return True

class ReviewEventsInteraction(ImmediateSuperInteraction):
    """
    审核 AI 生成的重要事件
    读取 PendingEvents 文件，玩家确认后保存到 Character_Profile
    """

    @flexmethod
    def _run_interaction_gen(cls, inst, timeline):
        pending_path = get_pending_events_path()
        profile_path = get_character_profile_path()

        # 读取待审核内容
        content = ""
        try:
            if os.path.exists(pending_path):
                with open(pending_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
        except Exception as e:
            log_error(f"Read pending events error: {e}", "review_events")

        if not content:
            show_story_dialog("📭 No pending events to review.")
            return True

        # 定义确认和取消的回调
        def on_confirm():
            try:
                # 追加到 Character_Profile.txt
                with open(profile_path, "a", encoding="utf-8") as f:
                    f.write(f"\n--- AI Events ({get_log_time()}) ---\n")
                    f.write(content + "\n")
                # 清空 pending 文件
                with open(pending_path, "w", encoding="utf-8") as f:
                    f.write("")
                show_story_dialog("✅ Events saved to Character Profile!")
            except Exception as e:
                log_error(f"Save events error: {e}", "review_events")
                show_story_dialog(f"❌ Failed to save: {e}")

        def on_cancel():
            try:
                # 清空 pending 文件，不保存
                with open(pending_path, "w", encoding="utf-8") as f:
                    f.write("")
                show_story_dialog("🗑️ Events discarded.")
            except:
                pass

        # 显示确认弹窗
        display_text = (
            f"📌 AI detected important events:\n\n"
            f"{content}\n\n"
            f"──────────────────\n"
            f"OK = Save to Character Profile\n"
            f"Cancel = Discard"
        )
        show_confirm_dialog(
            display_text,
            f"📌 Review Events ({MOD_VERSION})",
            on_confirm,
            on_cancel
        )

        return True