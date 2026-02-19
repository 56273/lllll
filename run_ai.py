# ================= 强力兼容补丁 =================
import sys
import os

try:
    import pyparsing

    if not hasattr(pyparsing, 'DelimitedList'):
        if hasattr(pyparsing, 'delimited_list'):
            pyparsing.DelimitedList = pyparsing.delimited_list
        elif hasattr(pyparsing, 'delimitedList'):
            pyparsing.DelimitedList = pyparsing.delimitedList
except ImportError:
    pass
# ===============================================

import time
import google.generativeai as genai

# 🔴🔴🔴 填入你的 API KEY 🔴🔴🔴
API_KEY = "####"



# =======================================================
# 智能路径检测（和游戏内脚本保持一致）
# =======================================================
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

def get_output_dir():
    # 1. 先读配置文件
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
            except:
                pass
    # 2. 桌面
    home = os.path.expanduser("~")
    for desktop in [os.path.join(home, "Desktop"), os.path.join(home, "OneDrive", "Desktop"), os.path.join(home, "桌面")]:
        if os.path.isdir(desktop):
            return desktop
    # 3. 主目录
    return home

OUTPUT_DIR = get_output_dir()
print(f"📁 输出目录: {OUTPUT_DIR}")

FILE_LOG = os.path.join(OUTPUT_DIR, "Sims4_Story_Log_Latest.txt")
FILE_PROFILE = os.path.join(OUTPUT_DIR, "Character_Profile.txt")
FILE_INBOX = os.path.join(OUTPUT_DIR, "Sims4_Inbox.txt")
FILE_MEMORY = os.path.join(OUTPUT_DIR, "Story_Memory.txt")
FILE_ARCHIVE = os.path.join(OUTPUT_DIR, "Story_Archive.txt")
genai.configure(api_key=API_KEY)


def ask_gemini(new_log, profile, memory):
    print("✨ AI 正在构思剧情...")
    prompt = f"""
    你是一个《模拟人生4》的剧情导演。请根据以下信息生成一段简短的剧情更新。

    【角色人设】
    {profile}

    【前情提要】
    {memory}

    【刚刚发生的事件】
    {new_log}
    【日志格式说明】
    - 时间格式: [HH:MM] 角色名(日志中显示的是名在前，姓在后，生成的文请显示姓名，而非名姓)(情绪[Buff原因]) -> 动作 -> 目标 关系值
    - 关系值 [F98/R10] 表示首次出现的友谊/浪漫总值
    - 关系值 F+5/R-3 表示友谊变化+5/浪漫变化-3，关系值的变化用于判断主动做出的互动是否成功，以及接受该互动的人是否喜爱该互动
    - 注意：关系值变化有延迟，况且beaffectionate或者chat等非具体互动通常不加值，如果在此条日志后出现值变化，通常显示的是上一个互动造成的结果
    - "=== Travel ===" 表示场景切换
    - "| Holiday" 或 "| Party" 表示当前有节日或派对
    -如果有角色名和主控的一样，但姓不一样，请记住，那是不同的人，不要把名一样的人当成主控，游戏中有重名的角色非常正常。
    【任务要求】
    1.下笔之前，先完整阅读所有日志，找出：
- 最核心的情绪转折或事件冲突，重点描写这些
- 哪些细节最能体现人物性格
- 什么不需要写（琐碎的日常动作、没有推进剧情的事件）
-实在是没有什么drama事件，再写日常
    2. 你是一位笔触克制、风格典雅的现代小说家，保持贵族/世家视角时，用词端正克制，不用现代网络语，- 禁止出现游戏特质名称，例如"势利鬼"、"孤独感生活方式"、"书呆子"等
- 禁止出现游戏系统术语，例如"技能值"、"心情buff"、"需求槽"等
- 禁止用括号或注释解释游戏机制。【如果角色有特质，这样处理】，禁止无缘无故反复提到人物的特征或背景，因为你的写作是连续的，每次都在内容中提到我在character里留下的内容非常怪异！
不写名字，写行为表现。
-禁止脑补日志内没有的内容，比如ab是夫妇，a出轨了，但是日志内没有显示b有对出轨的伤心情感，那么证明其不知道这件事，如果知道了，日志内一定会有情绪。不要过度解读，专注日志原本有的内容。
-禁止在内容的结尾进行不必要的总结，比如“唯有空气中残留的淡淡酒气，诉说着这个家族正加速走向腐朽。”，因为故事是不会有结尾的，除非发生了重大事件，指代着某个转折的发生。
❌ "他的势利鬼特质让他对宿舍感到厌恶"
✅ "他扫了一眼那张摇摇晃晃的椅子和发黄的墙壁，没有坐下"
结合人设和事件，写一段 **800字左右** 的剧情旁白，内容为简体字，不要使用繁体字。风格生动，人物鲜活，内容具有高可读性，要像一篇记录一样，内容按时间顺序展开，尽量不要写定于过于长的句子，拒绝翻译腔，剧情内容中不要带有log中的杂乱的数据，请把游戏术语隐形化。不要每次都提到角色的特质！只有当特质导致了**反常**或**极其典型**的行为时才顺带一提。剧情要有轻重缓急，不要把所有琐碎的喝水、上厕所都写得像史诗一样宏大。重点描写冲突。当情景合适时，可适当描写人物说了什么，说了哪些话，像是这个人物在这个场景下会说的话。
    2. 生成一个新的“前情提要”。

    【输出格式】
    请严格按照以下格式输出：
    剧情内容...
    ||SPLIT||
    新的前情提要...
    """

    try:
        # ⬇️ 换成你的列表里有的 'gemini-flash-latest'
        # 这是一个别名，通常指向当前稳定的 Flash 版本
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        error_str = str(e)
        if "429" in error_str:
            print(f"⚠️ 触发频率限制 (429)！")
            print("☕ AI 需要休息一下，脚本将自动暂停 60 秒...")
            time.sleep(60)
            return None
        elif "404" in error_str:
            print(f"❌ 模型 404：可能是网络没走代理，或者模型名字 {model.model_name} 不可用。")
        else:
            print(f"❌ API 连接失败: {e}")
        return None


def main():
    print("🚀 AI 助手启动 (适配版 V25.0)！")
    print(f"📂 正在监控: {FILE_LOG}")
    print(f"📬 Inbox 路径: {FILE_INBOX}")

    # 初始化文件
    for f in [FILE_PROFILE, FILE_MEMORY, FILE_ARCHIVE]:
        if not os.path.exists(f):
            with open(f, "w", encoding="utf-8") as file: file.write("")

    last_content_hash = ""
    if os.path.exists(FILE_LOG):
        try:
            with open(FILE_LOG, "r", encoding="utf-8") as f:
                last_content_hash = str(hash(f.read()))
        except:
            pass
        print(f"ℹ️ 已记录当前日志状态")

    while True:
        try:
            time.sleep(5)

            if not os.path.exists(FILE_LOG): continue

            # 读取当前内容
            try:
                with open(FILE_LOG, "r", encoding="utf-8") as f:
                    current_content = f.read().strip()
            except:
                continue

            if not current_content: continue

            current_hash = str(hash(current_content))
            if current_hash == last_content_hash:
                continue

            # 内容变了！
            print(f"📨 检测到新日志！")
            last_content_hash = current_hash

            # 读取上下文
            profile = ""
            memory = ""
            if os.path.exists(FILE_PROFILE):
                with open(FILE_PROFILE, "r", encoding="utf-8") as f: profile = f.read()
            if os.path.exists(FILE_MEMORY):
                with open(FILE_MEMORY, "r", encoding="utf-8") as f: memory = f.read()

            # 呼叫 AI
            result = ask_gemini(current_content, profile, memory)

            if result and "||SPLIT||" in result:
                parts = result.split("||SPLIT||")
                story = parts[0].strip()
                new_mem = parts[1].strip() if len(parts) > 1 else memory

                with open(FILE_INBOX, "w", encoding="utf-8") as f:
                    f.write(story)
                print(f"✅ 剧情已发送给游戏！")

                with open(FILE_MEMORY, "w", encoding="utf-8") as f:
                    f.write(new_mem)

                with open(FILE_ARCHIVE, "a", encoding="utf-8") as f:
                    f.write(f"\n{story}\n")
            else:
                if result: print(f"⚠️ 格式异常，跳过本次")

        except KeyboardInterrupt:
            print("\n🛑 程序已停止")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()