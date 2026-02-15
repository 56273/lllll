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
API_KEY = ""

# 🌐 代理设置 (如果需要)
# os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
# os.environ['HTTP_PROXY']  = 'http://127.0.0.1:7890'

# 路径设置
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
# DESKTOP = r"C:\Users\lnykk\Desktop" # 手动指定备用

FILE_LOG = os.path.join(DESKTOP, "Sims4_Story_Log_Full.txt")
FILE_PROFILE = os.path.join(DESKTOP, "Character_Profile.txt")
FILE_INBOX = os.path.join(DESKTOP, "Sims4_Inbox.txt")
FILE_MEMORY = os.path.join(DESKTOP, "Story_Memory.txt")
FILE_ARCHIVE = os.path.join(DESKTOP, "Story_Archive.txt")

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

    【任务要求】
    1. 你是一位笔触细腻、风格幽默的现代小说家，结合人设和事件，写一段 **800字以内** 的剧情旁白，内容为简体字，不要使用繁体字。风格生动具有戏剧性，人物鲜活，内容具有高可读性，尽量不要写定于过于长的句子，拒绝翻译腔，剧情内容中不要带有log中的杂乱的数据，请把游戏术语隐形化。不要每次都提到角色的特质！只有当特质导致了**反常**或**极其典型**的行为时才顺带一提。剧情要有轻重缓急，不要把所有琐碎的喝水、上厕所都写得像史诗一样宏大。重点描写冲突。当情景合适时，可适当描写人物说了什么，说了哪些话，像是这个人物在这个场景下会说的话。
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
    print("🚀 AI 助手启动 (适配版 V24.0)！")
    print(f"📂 正在监控: {FILE_LOG}")

    # 初始化文件
    for f in [FILE_PROFILE, FILE_MEMORY, FILE_ARCHIVE]:
        if not os.path.exists(f):
            with open(f, "w", encoding="utf-8") as file: file.write("")

    last_size = 0
    if os.path.exists(FILE_LOG):
        last_size = os.path.getsize(FILE_LOG)
        print(f"ℹ️ 当前日志大小: {last_size}")

    while True:
        try:
            time.sleep(5)

            if not os.path.exists(FILE_LOG): continue

            current_size = os.path.getsize(FILE_LOG)

            if current_size < last_size:
                last_size = current_size
                continue

            if current_size > last_size:
                print(f"📨 收到新日志！({current_size - last_size} 字节)")

                try:
                    with open(FILE_LOG, "r", encoding="utf-8") as f:
                        f.seek(last_size)
                        new_content = f.read().strip()
                except:
                    continue

                last_size = current_size

                if not new_content: continue

                # 读取上下文
                profile = ""
                memory = ""
                if os.path.exists(FILE_PROFILE):
                    with open(FILE_PROFILE, "r", encoding="utf-8") as f: profile = f.read()
                if os.path.exists(FILE_MEMORY):
                    with open(FILE_MEMORY, "r", encoding="utf-8") as f: memory = f.read()

                # 呼叫 AI
                result = ask_gemini(new_content, profile, memory)

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
