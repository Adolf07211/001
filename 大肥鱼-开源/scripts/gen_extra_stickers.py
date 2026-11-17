"""在现有 219 张基础上，再补一批同情绪的备选表情（每个热门类别多 6~10 张）。"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "plugin" / "stickers"
SIZE = 480
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_NORMAL = r"C:\Windows\Fonts\msyh.ttc"

PALETTE = [
    ("#FFE6EE", "#8FD0FF"), ("#E6F4FF", "#7CC4FF"), ("#FFF6D6", "#8FD0FF"),
    ("#EDE4FF", "#7CC4FF"), ("#FFE8F3", "#8FD0FF"), ("#E4E9FF", "#9CCBFF"),
    ("#FFF0DC", "#7CC4FF"), ("#F1ECFF", "#7CC4FF"), ("#E9F7FF", "#8FD0FF"),
    ("#FFF2D9", "#7CC4FF"), ("#EAF4FF", "#7CC4FF"), ("#FFE9F2", "#8FD0FF"),
]

NEW = [
    # 委屈 / 难过
    ("wronged2", "好委屈", "眼泪在打转", "sad", "委屈;难过;想哭"),
    ("wronged3", "没人疼", "自己抱自己", "sad", "委屈;孤单;难过"),
    ("wronged4", "被欺负了", "你帮我骂他", "sad", "委屈;难过;求助"),
    ("teary", "眼泪打转", "忍住不哭", "sad", "委屈;想哭;忍住"),
    ("heavy", "心里堵堵的", "说不出话", "sad", "难过;心事;低落"),
    ("unloved", "想被安慰", "抱一下就好", "sad", "难过;求安慰;孤单"),
    # 开心
    ("happy2", "太好了", "转圈圈", "happy", "开心;好消息;兴奋"),
    ("happy3", "美滋滋", "尾巴翘起来", "happy", "开心;得意;满足"),
    ("happy4", "笑出声", "憋不住", "happy", "开心;大笑;乐"),
    ("happy5", "开心到冒泡", "咕噜咕噜", "happy", "开心;兴奋;冒泡"),
    ("happy6", "爽到", "今天真顺", "happy", "开心;顺利;爽"),
    ("happy7", "心里开花", "藏不住", "happy", "开心;甜;幸福"),
    # 生气
    ("angry2", "气死我了", "谁惹的", "angry", "生气;火大;不满"),
    ("angry3", "火大", "别靠近", "angry", "生气;火大;警告"),
    ("angry4", "想打人", "拳头硬了", "angry", "生气;恼火;打闹"),
    ("angry5", "别惹我", "今天很凶", "angry", "生气;警告;凶"),
    ("angry6", "炸毛了", "谁都别碰", "angry", "生气;炸毛;暴躁"),
    ("angry7", "摔尾巴", "不开心", "pout", "生气;闹脾气;不满"),
    # 困 / 睡
    ("sleepy2", "打哈欠", "困到流泪", "sleepy", "困;哈欠;睡"),
    ("sleepy3", "眼皮沉", "撑不住了", "sleepy", "困;撑不住;睡"),
    ("sleepy4", "想睡觉", "别叫我", "sleepy", "困;睡觉;别吵"),
    ("sleepy5", "睡眠不足", "黑眼圈", "sleepy", "困;熬夜;累"),
    ("sleepy6", "赖床", "再五分钟", "sleepy", "困;赖床;起床"),
    # 抱 / 亲近
    ("hug4", "要抱抱", "伸手", "happy", "抱抱;撒娇;要"),
    ("hug5", "搂住", "不放开", "happy", "抱;亲密;黏人"),
    ("hug6", "靠一下", "就一会儿", "shy", "依靠;亲密;撒娇"),
    ("hug7", "抱大腿", "不让你走", "happy", "抱;黏人;撒娇"),
    ("hug8", "贴脸脸", "软软的", "shy", "贴;亲密;害羞"),
    ("hug9", "抱着睡", "晚安", "sleepy", "抱;睡觉;亲密"),
    # 喜欢
    ("love2", "喜欢你", "说出来了", "shy", "喜欢;表白;害羞"),
    ("love3", "最喜欢了", "只对你", "shy", "喜欢;独占;表白"),
    ("love4", "偷偷喜欢", "不告诉你", "shy", "喜欢;暗恋;害羞"),
    ("love5", "脸红心跳", "别看我", "shy", "心动;害羞;喜欢"),
    ("love6", "想你了", "什么时候来", "sad", "想你;等待;喜欢"),
    # 吃
    ("eat2", "饿了", "饭呢", "normal", "饿;吃饭;催"),
    ("eat3", "来碗饭", "白米饭", "normal", "吃饭;米饭;要"),
    ("eat4", "想吃肉", "大口吃", "happy", "吃;肉;馋"),
    ("eat5", "加餐", "再来一份", "happy", "吃;加餐;馋"),
    ("eat6", "吃货", "嘴巴不停", "happy", "吃;吃货;馋"),
    ("eat7", "好吃的", "眼睛发光", "happy", "吃;好吃;开心"),
    # 震惊
    ("shock2", "什么？！", "没听清", "surprised", "震惊;惊讶;疑问"),
    ("shock3", "不会吧", "真的假的", "surprised", "震惊;不信;惊讶"),
    ("shock4", "吓到", "缩起来", "surprised", "吓;震惊;害怕"),
    ("shock5", "瞪大眼", "看傻了", "surprised", "震惊;看傻;呆"),
    # 无语
    ("speechless3", "无话可说", "你赢了", "normal", "无语;服气;无奈"),
    ("speechless4", "垮掉", "精神出走", "normal", "无语;垮;疲惫"),
    ("speechless5", "服气了", "真的服", "normal", "无语;服气;无奈"),
    ("speechless6", "沉默三秒", "让我缓缓", "normal", "无语;沉默;冷静"),
    # 加油
    ("cheer3", "冲鸭", "往前冲", "happy", "加油;冲;鼓励"),
    ("cheer4", "你可以的", "我相信你", "happy", "加油;相信;鼓励"),
    ("cheer5", "别放弃", "再试一次", "happy", "加油;坚持;鼓励"),
    ("cheer6", "挺住", "我在旁边", "normal", "加油;撑住;陪伴"),
    # 谢谢 / 道歉
    ("thanks2", "多谢", "真的谢谢", "happy", "谢谢;感谢;礼貌"),
    ("thanks3", "谢啦", "记住你了", "happy", "谢谢;记住;感激"),
    ("sorry4", "对不起", "我错了", "sad", "道歉;错了;对不起"),
    ("sorry5", "原谅我", "下次不会", "sad", "道歉;原谅;保证"),
    ("sorry6", "别生气嘛", "我请你吃饭", "sad", "道歉;哄;请客"),
    # 早 / 晚
    ("morning3", "早上好", "今天也加油", "happy", "早安;加油;早上"),
    ("morning4", "起床啦", "太阳晒屁股", "happy", "早安;叫醒;早上"),
    ("night2", "好梦", "梦到我", "sleepy", "晚安;好梦;睡觉"),
    ("night3", "睡了", "明天见", "sleepy", "睡觉;晚安;告别"),
    # 无聊 / 摸鱼
    ("bored2", "好无聊", "陪我玩", "normal", "无聊;陪我;找乐子"),
    ("bored3", "没事干", "发呆中", "normal", "无聊;发呆;闲"),
    ("fish3", "摸鱼中", "别告诉老板", "normal", "摸鱼;偷懒;上班"),
    ("fish4", "划水", "摸一会儿", "normal", "摸鱼;划水;偷懒"),
    # 笑
    ("laugh", "笑死", "绷不住了", "happy", "笑死;大笑;绷不住"),
    ("laugh2", "哈哈哈", "停不下来", "happy", "笑;开心;哈哈"),
    ("laugh3", "乐死", "肚子疼", "happy", "笑;开心;乐"),
    # 撒娇 / 求夸 / 得意
    ("coquetry", "撒娇", "有用吗", "shy", "撒娇;可爱;求"),
    ("coquetry2", "求夸夸", "快夸我", "shy", "求夸;撒娇;可爱"),
    ("smug2", "厉害吧", "我超强", "smug", "得意;厉害;求夸"),
    ("smug3", "哼唧", "才不承认", "smug", "傲娇;得意;别扭"),
    # 陪伴 / 告白
    ("company", "陪你", "一直在", "happy", "陪伴;暖心;在"),
    ("company2", "我在呢", "叫我干嘛", "normal", "陪伴;在;回应"),
    ("company3", "别怕", "有我在", "normal", "安慰;陪伴;别怕"),
    # 天气 / 日常补充
    ("rain2", "下雨了", "记得带伞", "normal", "下雨;关心;提醒"),
    ("cold3", "好冷啊", "缩成团", "sad", "冷;冬天;缩"),
    ("hot2", "热死了", "化了", "sad", "热;夏天;化"),
    ("tired2", "好累", "不想动", "sleepy", "累;疲惫;休息"),
    ("tired3", "撑不住", "想躺平", "sleepy", "累;躺平;疲惫"),
    # 工作 / 学习
    ("work2", "上班中", "别烦我", "normal", "上班;忙;别烦"),
    ("work3", "加班", "还没走", "sad", "加班;累;上班"),
    ("study2", "学习", "脑子进不去", "sad", "学习;难;累"),
    ("exam2", "考试", "救命啊", "surprised", "考试;紧张;救命"),
    # 游戏
    ("game2", "开黑", "上号", "happy", "游戏;开黑;组队"),
    ("game3", "又输了", "不服", "pout", "游戏;输;不服"),
    ("game4", "带带我", "求带", "shy", "游戏;求带;撒娇"),
    # 鲸鱼娘补充
    ("whale2", "本鲸", "在此", "smug", "自称;鲸鱼;得意"),
    ("whale3", "喷水", "哗——", "happy", "喷水;鲸鱼;玩"),
    ("whale4", "回深海", "先走了", "sleepy", "深海;走了;告别"),
    ("whale5", "吃白饭", "第三碗", "normal", "白饭;吃;干饭"),
]


def load_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def draw_whale(draw, cx, cy, scale, color, mood):
    w, h = int(200 * scale), int(130 * scale)
    draw.ellipse([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2], fill=color, outline="#2b6f9e", width=4)
    draw.chord([cx - w // 2 + 10, cy - h // 2 + 10, cx + w // 2 - 10, cy + h // 2 - 6], 10, 170, fill="#EAF6FF")
    tail_x = cx + w // 2 - 12
    draw.polygon([(tail_x, cy), (tail_x + int(52 * scale), cy - int(46 * scale)), (tail_x + int(46 * scale), cy)],
                 fill=color, outline="#2b6f9e")
    draw.polygon([(tail_x, cy), (tail_x + int(52 * scale), cy + int(46 * scale)), (tail_x + int(46 * scale), cy)],
                 fill=color, outline="#2b6f9e")
    ex, ey = cx - int(28 * scale), cy - int(10 * scale)
    r = max(4, int(7 * scale))
    if mood in ("happy", "smug"):
        draw.arc([ex - r, ey - r, ex + r, ey + r], 200, 340, fill="#22343f", width=4)
    elif mood == "sleepy":
        draw.line([ex - r, ey, ex + r, ey], fill="#22343f", width=4)
    elif mood == "sad":
        draw.ellipse([ex - r, ey - r, ex + r, ey + r], fill="#22343f")
        draw.line([ex + r // 2, ey + r, ex + r // 2, ey + r + 12], fill="#6fb7e8", width=4)
    elif mood == "angry":
        draw.ellipse([ex - r, ey - r, ex + r, ey + r], fill="#22343f")
        draw.line([ex - r - 2, ey - r - 8, ex + r + 2, ey - r + 2], fill="#22343f", width=4)
    elif mood == "surprised":
        draw.ellipse([ex - r - 2, ey - r - 2, ex + r + 2, ey + r + 2], fill="#22343f")
    else:
        draw.ellipse([ex - r, ey - r, ex + r, ey + r], fill="#22343f")
    blush = "#FFB7C5" if mood in ("shy", "happy", "smug") else "#FFC9D4"
    draw.ellipse([cx - int(58 * scale), cy + int(4 * scale), cx - int(28 * scale), cy + int(24 * scale)], fill=blush)
    draw.arc([cx - int(20 * scale), cy - int(h * 0.95), cx + int(20 * scale), cy - int(h * 0.45)],
             200, 340, fill="#7CC4FF", width=5)


def make(i, entry):
    key, big, small, mood, tags = entry
    bg, whale = PALETTE[i % len(PALETTE)]
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, SIZE - 6, SIZE - 6], radius=44, fill=bg, outline="#2b6f9e", width=5)
    f_big = load_font(FONT_BOLD, 64 if len(big) <= 4 else (52 if len(big) <= 6 else 40))
    f_small = load_font(FONT_NORMAL, 24)
    bbox = d.textbbox((0, 0), big, font=f_big)
    d.text(((SIZE - (bbox[2] - bbox[0])) / 2, 62), big, font=f_big, fill="#20303c")
    bbox2 = d.textbbox((0, 0), small, font=f_small)
    d.text(((SIZE - (bbox2[2] - bbox2[0])) / 2, 152), small, font=f_small, fill="#5b7183")
    draw_whale(d, SIZE // 2 - 10, 340, 1.05, whale, mood)
    img.save(OUT / f"{key}.png")
    return {"key": key, "text": big, "scene": small, "tags": tags.split(";"), "file": f"{key}.png"}


index_file = OUT / "index.json"
index = json.loads(index_file.read_text(encoding="utf-8-sig"))
existing = {e["key"] for e in index}
added = 0
for i, entry in enumerate(NEW):
    if entry[0] in existing:
        continue
    index.append(make(len(index) + i, entry))
    added += 1
index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
print("added:", added, "total:", len(index))
