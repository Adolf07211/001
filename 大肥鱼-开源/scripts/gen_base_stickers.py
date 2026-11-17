# 生成 200 张基础表情包（需要 Windows 微软雅黑字体，或自行改 FONT_* 路径）
"""生成 200 张「大肥鱼」表情包 + 细分的标签索引。"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "plugin" / "stickers"
OUT.mkdir(parents=True, exist_ok=True)
SIZE = 480
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_NORMAL = r"C:\Windows\Fonts\msyh.ttc"

PALETTE = [
    ("#FFE6EE", "#8FD0FF"), ("#E6F4FF", "#7CC4FF"), ("#FFF6D6", "#8FD0FF"),
    ("#EDE4FF", "#7CC4FF"), ("#FFE8F3", "#8FD0FF"), ("#E4E9FF", "#9CCBFF"),
    ("#FFF0DC", "#7CC4FF"), ("#F1ECFF", "#7CC4FF"), ("#E9F7FF", "#8FD0FF"),
    ("#FFF2D9", "#7CC4FF"), ("#EAF4FF", "#7CC4FF"), ("#FFE9F2", "#8FD0FF"),
]

# (key, 大字, 小字, 表情, 标签/ ; 分隔)
S = [
    # ---- 亲密互动
    ("hug", "抱抱", "抱一个就不许跑了", "happy", "抱抱;拥抱;安慰;暖心"),
    ("hugtight", "抱紧", "不松手的那种", "happy", "抱紧;拥抱;黏人;安慰"),
    ("hug3", "抱一下就好", "就一下", "shy", "抱抱;安慰;难过;撒娇"),
    ("kiss", "亲亲", "就、就一下", "shy", "亲亲;么么;喜欢;害羞"),
    ("kiss2", "木马", "啵你一口", "happy", "亲亲;木马;喜欢;调皮"),
    ("nuzzle", "蹭蹭", "毛都要蹭掉了", "happy", "蹭蹭;撒娇;黏人;亲密"),
    ("snuggle", "蹭脸", "脸贴脸", "shy", "蹭脸;亲密;撒娇;害羞"),
    ("patme", "求摸头", "我很乖的", "shy", "摸头;求摸;乖;撒娇"),
    ("headpat", "顺毛", "别炸毛啦", "happy", "顺毛;摸头;安慰;乖"),
    ("pat2", "拍拍", "拍拍你", "normal", "拍拍;安慰;鼓励;乖"),
    ("stick", "贴贴", "紧紧贴着", "happy", "贴贴;亲密;黏人;撒娇"),
    ("heart", "比心", "给你", "happy", "比心;喜欢;爱;示爱"),
    ("love", "爱你", "说出来了", "shy", "爱你;喜欢;表白;害羞"),
    ("dokidoki", "心动", "砰砰跳", "shy", "心动;喜欢;害羞;恋爱"),
    ("shy", "害羞", "别、别看了", "shy", "害羞;脸红;不好意思"),
    ("shy2", "脸红了", "都是你害的", "shy", "脸红;害羞;别扭;被夸"),
    ("blush", "红脸", "热死了", "shy", "脸红;害羞;热;不好意思"),
    ("wink", "眨眼", "懂了吧", "smug", "眨眼;调皮;暗示;得意"),
    ("lift", "举高高", "要要要", "happy", "举高高;抱;玩;撒娇"),
    ("rub", "揉脸", "软乎乎的", "happy", "揉脸;软;可爱;亲密"),
    ("pinch", "捏脸", "轻一点啦", "shy", "捏脸;调戏;可爱;害羞"),
    ("boop", "戳戳", "戳你一下", "normal", "戳;调皮;互动;可爱"),
    ("poke", "戳一下", "在不在", "normal", "戳;在吗;互动;找人"),
    ("peek", "偷看", "被你发现了", "shy", "偷看;看;瞄;害羞"),
    ("peek2", "探头", "有人在吗", "normal", "探头;在吗;看看;冒头"),
    ("listen", "偷听", "谁在说我", "normal", "偷听;八卦;好奇"),
    ("mine", "你是我的", "不许乱跑", "smug", "占有;喜欢;吃醋;霸道"),
    ("jealous2", "不许理别人", "我才是最好的", "pout", "吃醋;占有;生气;撒娇"),
    ("ours", "我们的", "说好了", "happy", "约定;一起;亲密;承诺"),
    ("forever", "一直陪着你", "不许赶我走", "happy", "陪伴;喜欢;承诺;暖心"),
    ("promise", "说好了", "拉钩", "happy", "约定;承诺;拉钩;认真"),
    ("memorize", "我记住了", "你说的每句", "shy", "记住;认真;感动;暖心"),
    ("remember", "记得", "当然记得", "happy", "记得;认真;暖心"),
    ("comfort", "没事的", "有我在", "normal", "安慰;没事;暖心;陪伴"),
    ("comfort2", "没事的啦", "别自己扛", "normal", "安慰;暖心;鼓励"),
    ("protect", "我护着你", "谁都不许欺负你", "smug", "护短;保护;撑腰"),
    ("defend", "我帮你骂", "骂到他道歉", "angry", "护短;生气;骂人;撑腰"),
    ("forgive", "原谅你", "就这一次", "normal", "原谅;和好;宽容"),
    ("sorry", "我错了", "原谅我嘛", "sad", "道歉;错了;对不起"),
    ("sorry2", "对不起嘛", "别生气了", "sad", "道歉;哄;别生气"),
    ("sorry3", "别生气了", "我给你顺毛", "sad", "道歉;哄;安慰"),
    ("makeup", "和好吧", "拉钩", "happy", "和好;约定;道歉"),
    ("thanks", "谢谢", "真的谢啦", "happy", "谢谢;感谢;礼貌"),
    ("welcome", "不客气", "哼，应该的", "smug", "不客气;礼貌;得意"),
    # ---- 情绪
    ("happy", "开心", "嘿嘿嘿", "happy", "开心;高兴;快乐"),
    ("yay", "好耶", "赢啦", "happy", "好耶;庆祝;赢了"),
    ("cheer", "加油", "你可以的", "happy", "加油;鼓励;打气"),
    ("cheer2", "打气", "冲鸭", "happy", "打气;鼓励;加油"),
    ("praise", "求表扬", "我超棒的", "happy", "表扬;夸;棒;求夸"),
    ("proud", "骄傲", "快夸我", "smug", "骄傲;得意;求夸"),
    ("smug", "得意", "那当然啦", "smug", "得意;骄傲;自豪"),
    ("showoff", "显摆", "看看这个", "smug", "显摆;得意;炫耀"),
    ("smirk", "坏笑", "计划通", "smug", "坏笑;得意;调皮"),
    ("wronged", "委屈巴巴", "真的不是我", "sad", "委屈;难过;无辜"),
    ("sad", "难过", "有点想哭", "sad", "难过;伤心;低落"),
    ("cry", "呜呜", "快哄我", "sad", "哭;委屈;哄"),
    ("sob", "哭哭", "眼泪止不住", "sad", "哭;难过;流泪"),
    ("cry2", "抽泣", "吸鼻子", "sad", "哭;委屈;可怜"),
    ("lonely", "孤单", "一个人", "sad", "孤单;寂寞;难过"),
    ("aaa", "啊啊啊", "破防了", "sad", "崩溃;破防;啊啊"),
    ("sigh", "叹气", "唉——", "sad", "叹气;无奈;累"),
    ("tired", "累了", "趴一会儿", "sleepy", "累;疲惫;休息"),
    ("lazy", "摆烂", "今天不干了", "normal", "摆烂;偷懒;不想动"),
    ("bored", "无聊", "陪我玩", "normal", "无聊;找乐子;陪我"),
    ("daze", "发呆", "脑子空白", "normal", "发呆;空白;走神"),
    ("blank", "空白", "……", "normal", "空白;无语;呆住"),
    ("pout", "气鼓鼓", "不跟你讲话", "angry", "生气;鼓;不理"),
    ("angry", "生气", "真的生气了", "angry", "生气;恼火;不开心"),
    ("rage", "暴怒", "别拦我", "angry", "暴怒;生气;火大"),
    ("hum", "哼", "就哼一下", "smug", "哼;傲娇;不服"),
    ("ignore", "不理你了", "……三秒钟", "smug", "生气;不理;别扭"),
    ("silent", "不说话", "自己体会", "normal", "沉默;冷战;不说话"),
    ("cold", "冷战", "你哄不哄", "pout", "冷战;生气;别扭"),
    ("jealous", "吃醋", "酸了", "pout", "吃醋;酸;别扭"),
    ("glare", "瞪你", "再说一遍", "angry", "瞪;生气;警告"),
    ("hit", "捶你", "揍你哦", "angry", "捶;生气;打闹"),
    ("kick", "踢你", "踹一脚", "angry", "踢;生气;打闹"),
    ("bite", "咬你", "真咬", "angry", "咬;生气;打闹"),
    ("shock", "震惊", "真的假的", "surprised", "震惊;惊讶;真的"),
    ("stunned", "呆住", "啊？", "surprised", "呆;愣;啊"),
    ("confuse", "迷惑", "看不懂", "normal", "迷惑;不懂;奇怪"),
    ("question", "问号", "???", "normal", "问号;疑问;不解"),
    ("sweat", "流汗", "无语凝噎", "normal", "流汗;无语;尴尬"),
    ("speechless", "无语", "说点什么好", "normal", "无语;无奈;沉默"),
    ("speechless2", "沉默", "我缓缓", "normal", "沉默;无语;冷静"),
    ("facepalm", "扶额", "没眼看", "normal", "扶额;无奈;无语"),
    ("wake", "起床气", "别吵我", "angry", "起床;生气;早"),
    ("sleepy", "困困", "眯一小会儿", "sleepy", "困;睡觉;累"),
    ("sleep", "睡觉", "晚安啦", "sleepy", "睡觉;晚安;困"),
    ("sweetsleep", "睡啦睡啦", "明天见", "sleepy", "睡觉;晚安;告别"),
    ("night", "晚安", "做个好梦", "sleepy", "晚安;睡觉;梦"),
    ("dream", "做梦", "梦到你了", "sleepy", "做梦;梦;想你"),
    ("morning", "早安", "起床啦", "happy", "早安;早上;起床"),
    ("morning2", "早呀", "太阳晒屁股了", "happy", "早安;叫醒;早上"),
    # ---- 反应 & 社交
    ("clap", "鼓掌", "啪啪啪", "happy", "鼓掌;表扬;厉害"),
    ("salute", "敬礼", "收到！", "normal", "敬礼;收到;服从"),
    ("bow", "鞠躬", "多谢款待", "normal", "鞠躬;谢谢;礼貌"),
    ("handshake", "握手", "合作愉快", "normal", "握手;合作;礼貌"),
    ("highfive", "击掌", "啪！", "happy", "击掌;庆祝;默契"),
    ("gift", "礼物", "给你的", "happy", "礼物;送;惊喜"),
    ("flower", "送花", "拿好别掉了", "happy", "送花;礼物;喜欢"),
    ("lucky", "好运", "分你一点", "happy", "好运;祝福;幸运"),
    ("wish", "许愿", "希望成真", "normal", "许愿;愿望;期待"),
    ("magic", "魔法", "变！", "smug", "魔法;变;调皮"),
    ("ok", "好哒", "没问题", "happy", "好;可以;答应"),
    ("yes", "可以", "行吧", "normal", "可以;行;同意"),
    ("no", "不行", "想都别想", "pout", "不行;拒绝;不同意"),
    ("wait2", "等一下", "马上好", "normal", "等;稍等;马上"),
    ("coming", "来了来了", "别催", "normal", "来了;马上;别催"),
    ("leaving", "我走了", "别想我", "normal", "走了;告别;嘴硬"),
    ("back", "我回来了", "想我没", "happy", "回来;回来了;想你"),
    ("online", "上线", "我来了", "happy", "上线;来了;出现"),
    ("offline", "下线", "先撤了", "sleepy", "下线;走了;告别"),
    ("callme", "叫我干嘛", "有事说事", "normal", "叫我;找人;不耐烦"),
    ("busy", "忙着呢", "稍等", "normal", "忙;稍等;没空"),
    ("later", "回头说", "等会儿", "normal", "回头;等会;忙"),
    ("hey", "嘿", "看这里", "happy", "嘿;招呼;注意"),
    ("hello", "你好呀", "第一次见", "happy", "你好;打招呼;初见"),
    ("bye", "拜拜", "记得回来", "normal", "再见;拜拜;走了"),
    ("run", "跑路", "先溜了", "normal", "跑路;溜;逃跑"),
    ("hide", "躲起来", "找不到我", "normal", "躲;藏;玩"),
    ("escape", "溜了", "溜了溜了", "normal", "溜;跑;逃"),
    ("catch", "抓到你了", "别跑", "smug", "抓;逮住;玩"),
    ("chase", "追你", "等等我", "happy", "追;跑;玩"),
    ("jump", "跳一下", "蹦蹦", "happy", "跳;蹦;开心"),
    ("dance", "跳舞", "扭起来", "happy", "跳舞;开心;庆祝"),
    ("sing", "唱歌", "听我唱", "happy", "唱歌;表演;开心"),
    ("time", "时间", "到点了", "normal", "时间;到点;提醒"),
    ("clock", "迟到", "又晚了", "sad", "迟到;晚;抱歉"),
    ("late", "又迟到了", "对不起", "sad", "迟到;道歉;晚"),
    ("hurry", "快点", "来不及了", "surprised", "快点;着急;催"),
    ("slow", "慢慢来", "不着急", "normal", "慢慢;不急;安慰"),
    ("patience", "耐心点", "等等嘛", "normal", "耐心;等;哄"),
    ("calm", "冷静", "深呼吸", "normal", "冷静;安慰;别急"),
    ("relax", "放松", "别绷着", "normal", "放松;安慰;休息"),
    ("breathe", "深呼吸", "吸——呼——", "normal", "深呼吸;放松;冷静"),
    # ---- 日常
    ("rice", "干饭中", "勿扰谢谢", "normal", "干饭;吃;白米饭"),
    ("hungry", "饿饿", "饭呢饭呢", "normal", "饿;吃饭;饭"),
    ("feed", "求投喂", "就一口", "normal", "投喂;吃;饿"),
    ("full", "吃饱了", "动不了了", "sleepy", "吃饱;撑;满足"),
    ("diet", "减肥", "明天再说", "normal", "减肥;胖;明天"),
    ("fat2", "不许说胖", "再说就哭", "pout", "胖;不许说;生气"),
    ("weigh", "称体重", "不看数字", "sad", "体重;胖;难过"),
    ("coffee", "咖啡", "续命", "normal", "咖啡;提神;上班"),
    ("tea", "喝茶", "养生", "normal", "喝茶;养生;悠闲"),
    ("water", "喝水", "记得喝水", "normal", "喝水;关心;提醒"),
    ("cake", "蛋糕", "甜的", "happy", "蛋糕;甜;生日"),
    ("candy", "糖", "给你一颗", "happy", "糖;甜;给"),
    ("icecream", "冰淇淋", "夏天必备", "happy", "冰淇淋;夏天;甜"),
    ("ramen", "拉面", "热乎的", "happy", "拉面;吃;热"),
    ("hotpot", "火锅", "走起", "happy", "火锅;吃;约"),
    ("bbq", "烧烤", "配冰可乐", "happy", "烧烤;吃;夜宵"),
    ("milk", "奶茶", "三分糖", "happy", "奶茶;喝;甜"),
    ("tshirt", "新衣服", "好看吗", "shy", "衣服;新;好看"),
    ("mirror", "照镜子", "我最好看", "smug", "镜子;好看;自恋"),
    ("selfie", "自拍", "拍一张", "shy", "自拍;拍照;害羞"),
    ("photo", "拍照", "茄子", "happy", "拍照;合影;记录"),
    ("game", "打游戏", "开一局", "happy", "游戏;开黑;玩"),
    ("gameover", "GAME OVER", "再来一局", "sad", "游戏;输了;结束"),
    ("win", "赢了", "我超强", "happy", "赢;胜利;厉害"),
    ("lose", "输了", "不服", "pout", "输;不服;再来"),
    ("lag", "卡了", "网不行", "angry", "卡;延迟;网络"),
    ("ping", "掉线", "人没了", "sad", "掉线;断网;消失"),
    ("code", "写代码", "别打断", "normal", "代码;编程;忙"),
    ("bug", "有bug", "不关我事", "sad", "bug;报错;崩溃"),
    ("fix", "修好了", "夸我", "happy", "修;修好;搞定"),
    ("deploy", "上线了", "别出事", "surprised", "上线;发布;紧张"),
    ("sleepcode", "通宵了", "头发还在吗", "sleepy", "通宵;熬夜;累"),
    ("study", "学习", "看不进去", "sad", "学习;看书;难"),
    ("exam", "考试", "救命", "surprised", "考试;紧张;救命"),
    ("homework", "作业", "写不完", "sad", "作业;写;累"),
    ("work", "上班", "不想动", "sleepy", "上班;工作;累"),
    ("offwork", "下班", "冲！", "happy", "下班;回家;开心"),
    ("meeting", "开会", "走神中", "normal", "开会;走神;无聊"),
    ("boss", "老板", "别过来", "surprised", "老板;怕;上班"),
    ("salary", "发工资", "发财了", "happy", "工资;钱;开心"),
    ("broke", "没钱了", "吃土", "sad", "没钱;穷;难过"),
    ("payday", "发财", "请客", "happy", "发财;有钱;请客"),
    ("shop", "剁手", "就看看", "happy", "买东西;剁手;购物"),
    ("deliver", "外卖到了", "冲", "happy", "外卖;吃;到了"),
    ("package", "快递到了", "拆箱", "happy", "快递;拆箱;开心"),
    ("rain", "下雨", "湿乎乎", "sad", "下雨;天气;湿"),
    ("sunny", "晴天", "出去玩", "happy", "晴天;太阳;出去玩"),
    ("snow", "下雪", "好漂亮", "happy", "下雪;冬天;漂亮"),
    ("wind", "刮风", "头发乱了", "normal", "风;天气;乱"),
    ("cold2", "好冷", "缩成一团", "sad", "冷;冬天;缩"),
    ("hot", "好热", "化了", "sad", "热;夏天;化"),
    ("spring", "春天", "开花啦", "happy", "春天;花;季节"),
    ("summer", "夏天", "空调救命", "happy", "夏天;热;空调"),
    ("autumn", "秋天", "落叶", "normal", "秋天;落叶;季节"),
    ("winter", "冬天", "想冬眠", "sleepy", "冬天;冷;冬眠"),
    # ---- 鲸鱼娘专属
    ("bubble", "冒泡", "咕噜咕噜", "normal", "冒泡;在吗;潜水"),
    ("dive", "潜水", "别找我", "normal", "潜水;忙;消失"),
    ("splash", "拍水", "溅你一脸", "smug", "拍水;尾巴;调皮"),
    ("wag", "摇尾巴", "摇摇摇摇", "happy", "摇尾巴;开心;狗"),
    ("whale", "鲸鱼", "本鲸在此", "smug", "鲸鱼;自称;得意"),
    ("deepsea", "深海", "回家了", "sleepy", "深海;回家;睡觉"),
    ("lighthouse", "灯塔", "给你照路", "normal", "灯塔;照路;守护"),
    ("sea", "大海", "有点咸", "normal", "大海;海;味道"),
    ("fish", "摸鱼", "上班中别管我", "normal", "摸鱼;偷懒;上班"),
    ("fish2", "鱼", "抓一条", "happy", "鱼;抓;玩"),
    ("melon", "吃瓜", "然后呢然后呢", "normal", "吃瓜;八卦;看戏"),
    ("star", "星星", "摘一颗", "happy", "星星;送;浪漫"),
    ("moon", "月亮", "晚安", "sleepy", "月亮;晚安;夜"),
    ("sun", "太阳", "晒晒", "happy", "太阳;晴;暖"),
    ("flower2", "花", "开得正好", "happy", "花;好看;春天"),
    ("tree", "树", "靠着睡", "sleepy", "树;靠着;睡"),
    ("cloud", "云", "软软的", "normal", "云;软;天"),
    ("rainbow", "彩虹", "好运来", "happy", "彩虹;好运;美"),
    ("cat", "猫猫", "喵", "happy", "猫;喵;可爱"),
    ("dog", "狗狗", "汪", "happy", "狗;汪;可爱"),
    # ---- 特别场合
    ("bday", "生日快乐", "蛋糕呢", "happy", "生日;蛋糕;祝福"),
    ("congrats", "恭喜", "太强了", "happy", "恭喜;祝贺;厉害"),
    ("newyear", "新年快乐", "红包拿来", "happy", "新年;红包;祝福"),
    ("holiday", "放假", "自由了", "happy", "放假;自由;开心"),
    ("weekend", "周末", "躺平", "happy", "周末;休息;躺平"),
    ("tomorrow", "明天见", "说好了", "normal", "明天;再见;约定"),
    ("forget", "忘了", "真忘了", "sad", "忘;记忆;抱歉"),
    ("magic2", "变身", "看我", "smug", "变身;魔法;看"),
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


# 去重（key 重复只保留第一个）
seen = set()
uniq = []
for e in S:
    if e[0] in seen:
        continue
    seen.add(e[0])
    uniq.append(e)

index = [make(i, e) for i, e in enumerate(uniq)]
(OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
print("stickers:", len(index))
