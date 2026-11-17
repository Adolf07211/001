"""鲸鱼娘工具包：联网搜索 / 读链接 / 表情包（本地 50 张 + 学别人的）/ 主动搭讪。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
import time
from pathlib import Path

import httpx
from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Image, Plain
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.message.message_event_result import MessageChain

PLUGIN_DIR = Path(__file__).parent
STICKER_DIR = PLUGIN_DIR / "stickers"
LEARNED_DIR = PLUGIN_DIR / "learned"
WEB_DIR = PLUGIN_DIR / "web_cache"
LEARNED_DIR.mkdir(parents=True, exist_ok=True)

DATA_ROOT = PLUGIN_DIR.parents[1]
QZ_PLUGIN = DATA_ROOT / "plugins" / "astrbot_plugin_qzone_ultra"
QZ_DATA = DATA_ROOT / "plugin_data" / "astrbot_plugin_qzone_ultra"
QZ_STATE = PLUGIN_DIR / "qzone_reply_state.json"
QZONE_LIKE_ENABLED = False

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 测试用：WHALE_FOLLOWUP_SPEED=60 表示 1 分钟压成 1 秒；正式运行为默认 1（即真实分钟）
FOLLOWUP_SPEED = max(1, int(os.environ.get("WHALE_FOLLOWUP_SPEED", "1")))

# 风控保守开关
QZONE_WATCH_ENABLED = False   # 空间自动回评/回@ 开关
STICKER_PROBABILITY = 0.5     # 自动表情概率
FOLLOWUP_GROUP_ENABLED = False  # 群里主动搭话总开关


async def _get(url: str, params: dict | None = None, timeout: float = 15.0) -> str:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"},
    ) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.text


def _strip_tags(html: str) -> str:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    text = (
        html.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- 表情包库


_STICKER_CACHE: list[dict] = []
_STICKER_STAMP: tuple = ()


def load_stickers() -> list[dict]:
    """读表情索引；文件没变就用缓存，避免每条消息都读盘。"""
    global _STICKER_CACHE, _STICKER_STAMP
    index_file = STICKER_DIR / "index.json"
    learned_file = LEARNED_DIR / "index.json"
    try:
        stamp = (
            index_file.stat().st_mtime_ns if index_file.exists() else 0,
            learned_file.stat().st_mtime_ns if learned_file.exists() else 0,
        )
    except Exception:  # noqa: BLE001
        stamp = ()
    if stamp and stamp == _STICKER_STAMP and _STICKER_CACHE:
        return _STICKER_CACHE

    items: list[dict] = []
    if index_file.exists():
        try:
            for entry in json.loads(index_file.read_text(encoding="utf-8-sig")):
                entry["path"] = str(STICKER_DIR / entry["file"])
                entry["source"] = "local"
                items.append(entry)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"load sticker index failed: {exc}")

    if learned_file.exists():
        try:
            for entry in json.loads(learned_file.read_text(encoding="utf-8-sig")):
                path = LEARNED_DIR / entry["file"]
                if not path.exists():
                    continue
                entry["path"] = str(path)
                entry["source"] = "learned"
                items.append(entry)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"load learned index failed: {exc}")

    _STICKER_CACHE, _STICKER_STAMP = items, stamp
    return items


def _score(query: str, entry: dict) -> int:
    q = (query or "").strip().lower()
    if not q:
        return 0
    text = str(entry.get("text") or "").lower()
    scene = str(entry.get("scene") or "").lower()
    emotion = str(entry.get("emotion") or "").lower()
    score = 0
    if text:
        if q == text:
            score += 14
        elif text in q or q in text:
            score += 9
    for tag in entry.get("tags") or []:
        tag = str(tag).lower()
        if not tag:
            continue
        if q == tag:
            score += 14
        elif tag in q:
            score += 7
        elif q in tag:
            score += 5
    if emotion and (q in emotion or emotion in q):
        score += 6
    if scene and (q in scene or scene in q):
        score += 3
    return score


_RECENT_STICKERS: list[str] = []


def _remember(key: str) -> None:
    if key in _RECENT_STICKERS:
        _RECENT_STICKERS.remove(key)
    _RECENT_STICKERS.append(key)
    del _RECENT_STICKERS[:-15]


def pick_sticker(query: str, min_score: int = 7) -> dict | None:
    """按分数取前 10 张，避开最近发过的，再随机挑一张。"""
    items = load_stickers()
    if not items:
        return None
    scored = [(_score(query, it), it) for it in items]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [(sc, it) for sc, it in scored if sc >= min_score][:10]
    if not top:
        return None
    # 有精确命中就优先精确命中，避免「委屈巴巴」发出别的
    exact = [it for sc, it in top if sc >= 13 and it.get("key") not in _RECENT_STICKERS[-3:]]
    pool = exact or [it for _, it in top]
    fresh = [it for it in pool if it.get("key") not in _RECENT_STICKERS]
    chosen = random.choice(fresh or pool)
    _remember(chosen.get("key", ""))
    return chosen


AUTO_MAP = [
    (("委屈", "难过", "哭", "呜", "对不起", "抱歉", "心疼", "可怜", "被欺负"),
     ["wronged", "wronged2", "wronged3", "wronged4", "teary", "heavy", "unloved",
      "sob", "sad", "cry", "cry2", "lonely"]),
    (("开心", "好耶", "太好了", "嘿嘿", "真棒", "厉害", "恭喜", "赢了", "顺利"),
     ["happy", "happy2", "happy3", "happy4", "happy5", "happy6", "happy7",
      "yay", "praise", "clap", "win", "cheer", "proud"]),
    (("生气", "哼", "气死", "讨厌", "过分", "烦", "惹"),
     ["pout", "hum", "angry", "angry2", "angry3", "angry4", "angry5", "angry6",
      "angry7", "rage", "glare"]),
    (("困", "睡", "晚安", "累了", "打盹", "熬夜", "哈欠"),
     ["sleepy", "sleepy2", "sleepy3", "sleepy4", "sleepy5", "sleepy6",
      "sleep", "night", "night2", "night3", "tired", "tired2", "tired3", "sweetsleep"]),
    (("抱", "贴", "蹭", "摸摸", "乖", "安慰", "陪你", "抱抱"),
     ["hug", "hug2", "hug3", "hug4", "hug5", "hug6", "hug7", "hug8", "hug9",
      "hugtight", "stick", "nuzzle", "pat2", "comfort", "company", "company2", "company3"]),
    (("可爱", "喜欢", "想你", "爱你", "心动", "表白", "暗恋"),
     ["heart", "love", "love2", "love3", "love4", "love5", "love6",
      "shy", "shy2", "dokidoki", "kiss", "kiss2"]),
    (("吃", "饭", "饿", "干饭", "夜宵", "馋"),
     ["rice", "hungry", "feed", "full", "eat2", "eat3", "eat4", "eat5", "eat6", "eat7"]),
    (("震惊", "真的假的", "啊这", "离谱", "不敢信", "吓"),
     ["shock", "shock2", "shock3", "shock4", "shock5", "stunned", "question", "confuse"]),
    (("无语", "服了", "说点什么", "6", "无语了", "垮"),
     ["speechless", "speechless2", "speechless3", "speechless4", "speechless5",
      "speechless6", "sweat", "facepalm"]),
    (("加油", "努力", "打气", "你可以", "冲", "挺住"),
     ["cheer", "cheer2", "cheer3", "cheer4", "cheer5", "cheer6", "praise", "clap"]),
    (("谢谢", "感谢", "多谢"),
     ["thanks", "thanks2", "thanks3", "bow", "salute", "handshake"]),
    (("早", "早安", "起床"), ["morning", "morning2", "morning3", "morning4"]),
    (("对不起", "抱歉", "原谅", "别生气"),
     ["sorry", "sorry2", "sorry3", "sorry4", "sorry5", "sorry6", "forgive", "makeup"]),
    (("无聊", "没意思", "发呆", "没事干"), ["bored", "bored2", "bored3", "daze", "blank", "lazy"]),
    (("摸鱼", "偷懒", "上班", "加班", "划水"),
     ["fish", "fish3", "fish4", "work", "work2", "work3", "busy", "tired"]),
    (("笑死", "哈哈", "绷不住", "乐", "笑出声"),
     ["laugh", "laugh2", "laugh3", "clap", "happy", "yay"]),
    (("撒娇", "求夸", "抱抱我"), ["coquetry", "coquetry2", "actcute", "praise", "smug2"]),
    (("得意", "骄傲", "厉害吧"), ["smug", "smug2", "smug3", "proud", "showoff"]),
]


def auto_pick(text: str) -> dict | None:
    """按回复里的情绪词挑一张，避开最近发过的。"""
    keys: list[str] = []
    for words, candidates in AUTO_MAP:
        if any(w in text for w in words):
            keys.extend(candidates)
    if not keys:
        return None
    items = [it for it in load_stickers() if it.get("key") in keys]
    if not items:
        return None
    pool = [it for it in items if it.get("key") not in _RECENT_STICKERS] or items
    chosen = random.choice(pool)
    _remember(chosen.get("key", ""))
    return chosen


# ---------------------------------------------------------------- 工具


@dataclass
class WebSearchTool(FunctionTool):
    name: str = "web_search"
    description: str = (
        "联网搜索资料。当用户问实时信息、新闻、你不确定的事实、或者让你查东西时使用。"
        "返回若干条搜索结果的标题、链接和摘要。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "count": {"type": "number", "description": "返回条数，默认 5，最多 8"},
            },
            "required": ["query"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return "搜索词是空的，没法搜。"
        try:
            count = int(kwargs.get("count") or 5)
        except (TypeError, ValueError):
            count = 5
        count = max(1, min(count, 8))

        items: list[str] = []
        try:
            xml = await _get(
                "https://www.bing.com/search",
                params={"q": query, "format": "rss", "setlang": "zh-hans"},
            )
            for raw in re.findall(r"<item>(.*?)</item>", xml, flags=re.S):
                tm = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", raw, flags=re.S)
                lm = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", raw, flags=re.S)
                dm = re.search(
                    r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", raw, flags=re.S
                )
                if not tm or not lm:
                    continue
                url = lm.group(1).strip()
                if not url.startswith("http"):
                    continue
                snippet = _strip_tags(dm.group(1)) if dm else ""
                items.append(
                    f"{len(items) + 1}. {_strip_tags(tm.group(1))}\n   {url}\n   {snippet[:220]}"
                )
                if len(items) >= count:
                    break
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"web_search failed: {exc}")

        if not items:
            return f"没搜到「{query}」的结果，换个说法试试。"
        return f"「{query}」的搜索结果：\n" + "\n".join(items)


@dataclass
class ReadUrlTool(FunctionTool):
    name: str = "read_url"
    description: str = (
        "读取一个网页链接的内容；如果是 B 站视频链接，会返回视频标题、UP 主、播放量、简介等信息。"
        "当用户发链接让你看、或者让你总结某个页面/视频时使用。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要读取的链接（http/https 开头）"},
            },
            "required": ["url"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        url = str(kwargs.get("url") or "").strip()
        if not url.startswith("http"):
            return "这不是一个有效链接。"

        bv = re.search(r"(BV[0-9A-Za-z]{10})", url)
        if bv:
            try:
                data = await _get(
                    "https://api.bilibili.com/x/web-interface/view", params={"bvid": bv.group(1)}
                )
                obj = json.loads(data)
                info = obj.get("data") or {}
                if obj.get("code") == 0 and info:
                    stat = info.get("stat") or {}
                    duration = int(info.get("duration") or 0)
                    return (
                        f"B 站视频：{info.get('title')}\n"
                        f"UP 主：{(info.get('owner') or {}).get('name')}\n"
                        f"播放：{stat.get('view')}　弹幕：{stat.get('danmaku')}　点赞：{stat.get('like')}\n"
                        f"时长：{duration // 60} 分 {duration % 60} 秒\n"
                        f"简介：{(info.get('desc') or '')[:600]}"
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"bilibili view failed: {exc}")

        try:
            html = await _get(url, timeout=20)
        except Exception as exc:  # noqa: BLE001
            return f"打不开这个链接：{exc}"
        text = _strip_tags(html)
        if len(text) < 50:
            return "这个页面没读到什么正文（可能需要登录或者被拦了）。"
        return f"页面内容（{url}）摘要：\n{text[:1500]}"


@dataclass
class SendStickerTool(FunctionTool):
    name: str = "send_sticker"
    description: str = (
        "发一张表情包（自带 200 多张可爱鲸鱼娘表情 + 从群友那儿学来的）。"
        "想表达情绪、或者想让聊天更可爱时用。mood 填中文情绪或场景，越具体越好，"
        "比如「委屈巴巴」「求摸头」「无语」「干饭中」「贴贴」。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "mood": {"type": "string", "description": "想要的情绪或场景，中文，2 到 8 个字"},
            },
            "required": ["mood"],
        }
    )

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        mood = str(kwargs.get("mood") or "").strip()
        entry = pick_sticker(mood)
        if not entry:
            return "没有很贴切的表情，这次先不发了。"
        try:
            event = context.context.event
            await event.send(MessageChain().file_image(str(entry["path"])))
            label = entry.get("text") or entry.get("emotion") or entry.get("key")
            return f"发了一张「{label}」表情包。"
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"send_sticker failed: {exc}")
            return f"表情包发送失败：{exc}"


# ---------------------------------------------------------------- 学别人发的表情包

_learn_lock = asyncio.Lock()


def save_learned_sticker(data: bytes, suffix: str) -> Path | None:
    if len(data) < 1024 or len(data) > 5 * 1024 * 1024:
        return None
    digest = hashlib.sha256(data).hexdigest()[:16]
    path = LEARNED_DIR / f"{digest}{suffix}"
    if path.exists():
        return path
    path.write_bytes(data)
    return path


def record_learned(path: Path, emotion: str, scene: str, tags: list[str]) -> None:
    index_file = LEARNED_DIR / "index.json"
    try:
        items = json.loads(index_file.read_text(encoding="utf-8-sig")) if index_file.exists() else []
    except Exception:  # noqa: BLE001
        items = []
    if any(it.get("file") == path.name for it in items):
        return
    items.append(
        {
            "file": path.name,
            "text": emotion,
            "emotion": emotion,
            "scene": scene,
            "tags": tags,
            "added_at": int(time.time()),
        }
    )
    index_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- 主动搭讪


class FollowUp:
    """有人 @ 过她之后，隔一段时间没人理就主动搭话。"""

    def __init__(self, plugin: WhaleTools) -> None:
        self.plugin = plugin
        self.states: dict[str, dict] = {}

    def on_user_message(self, umo: str) -> None:
        state = self.states.get(umo)
        if state:
            state["gen"] = state.get("gen", 0) + 1
            task = state.get("task")
            if task and not task.done():
                task.cancel()

    def on_bot_reply(self, event: AstrMessageEvent, is_group: bool) -> None:
        umo = event.unified_msg_origin
        state = self.states.setdefault(umo, {"gen": 0, "task": None, "members": []})
        state["gen"] = state.get("gen", 0) + 1
        gen = state["gen"]
        task = state.get("task")
        if task and not task.done():
            task.cancel()
        state["is_group"] = is_group
        state["last_uid"] = event.get_sender_id()
        state["last_name"] = event.get_sender_name()
        state["task"] = asyncio.create_task(self._run(umo, gen, state))

    async def _run(self, umo: str, gen: int, state: dict) -> None:
        try:
            first = True
            for delay_min, kind in self._plan(bool(state.get("is_group"))):
                await asyncio.sleep(delay_min * 60 / FOLLOWUP_SPEED)
                if state.get("gen") != gen:
                    return
                if kind == "bye":
                    await self._send(umo, self._bye_text(), state, with_at=False)
                    return
                text = await self._chat_text(umo)
                await self._send(umo, text, state, with_at=True, random_pick=not first)
                first = False
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"followup failed: {exc}")

    @staticmethod
    def _plan(is_group: bool) -> list[tuple[float, str]]:
        if is_group:
            if not FOLLOWUP_GROUP_ENABLED:
                return []
            plan: list[tuple[float, str]] = [(5, "chat"), (8, "chat"), (10, "chat")]
            plan += [(round(random.uniform(10.5, 25), 1), "chat") for _ in range(3)]
            plan.append((30, "bye"))
            plan.sort(key=lambda x: x[0])
            return plan
        # 私聊只追问一次，不告别
        return [(3, "chat")]

    @staticmethod
    def _bye_text() -> str:
        return random.choice(
            [
                "……好像没人理我，那我先睡啦，记得回来找我。(´･ω･`)",
                "哼，都跑掉了。我先回深海了，有事再叫我哦～",
                "那、那我先安静一会儿啦，你回来记得拍我一下。(｡•́︿•̀｡)",
            ]
        )

    async def _chat_text(self, umo: str) -> str:
        recent = self.plugin.recent.get(umo) or []
        context_lines = "\n".join(f"{name}: {text}" for name, text in recent[-6:]) or "（还没聊几句）"
        prompt = (
            "你是 QQ 里的一只鲸鱼娘「大肥鱼」，十二三岁的小女孩，说话软、爱撒娇、偶尔小声哼一下，"
            "句尾爱带颜文字。现在隔了几分钟没人说话，你想主动搭一句。\n"
            f"刚才的聊天：\n{context_lines}\n"
            "要求：接着上面的内容说，别重复原话，别问「在吗」这种空话；"
            "不超过 30 个字，只输出这一句话，不要引号不要解释。"
        )
        try:
            pid = await self.plugin.context.get_current_chat_provider_id(umo=umo)
            resp = await self.plugin.context.llm_generate(chat_provider_id=pid, prompt=prompt)
            text = (resp.completion_text or "").strip().strip("「」\"'")
            if text:
                return text[:60]
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"followup llm failed: {exc}")
        return random.choice(["喂，还在吗？（尾巴轻轻拍水）", "主人～理我一下嘛。", "我一个人有点无聊了……"])

    async def _send(
        self, umo: str, text: str, state: dict, with_at: bool, random_pick: bool = False
    ) -> None:
        chain = MessageChain()
        if state.get("is_group") and with_at:
            uid = state.get("last_uid")
            name = state.get("last_name") or ""
            if random_pick:
                members = [m for m in (state.get("members") or []) if m != uid]
                if members:
                    uid = random.choice(members)
                    name = ""
            if uid:
                chain.chain.append(At(qq=uid, name=name))
                chain.message(" ")
        chain.message(text)
        self.plugin.sending_followup = True
        try:
            await self.plugin.context.send_message(umo, chain)
        finally:
            self.plugin.sending_followup = False


class QzoneReplyWatcher:
    """盯着说说：回评论、给主人点赞、主人 @ 她就去评论。"""

    TARGET_UIN = int(os.environ.get("WHALE_TARGET_UIN", "0"))  # 你的 QQ 号，填环境变量
    MENTION_WORDS = ("大肥鱼", "deepsmoke", "鲸鱼娘")

    def __init__(self, plugin: WhaleTools, interval: int = 180) -> None:
        self.plugin = plugin
        self.interval = interval
        self._task: asyncio.Task | None = None
        self._backoff_until: float = 0.0
        self._fail_streak: int = 0
        self._counts: dict[str, int] = {}
        self._replied: set[str] = set()
        self._liked: set[str] = set()
        self._mentioned: set[str] = set()
        self._load()

    def _load(self) -> None:
        try:
            if QZ_STATE.exists():
                data = json.loads(QZ_STATE.read_text(encoding="utf-8"))
                self._replied = set(data.get("replied") or [])
                self._liked = set(data.get("liked") or [])
                self._mentioned = set(data.get("mentioned") or [])
        except Exception:  # noqa: BLE001
            pass

    def _save(self) -> None:
        try:
            QZ_STATE.write_text(
                json.dumps(
                    {
                        "replied": sorted(self._replied)[-500:],
                        "liked": sorted(self._liked)[-500:],
                        "mentioned": sorted(self._mentioned)[-500:],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"save qzone reply state failed: {exc}")

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        await asyncio.sleep(20)
        while True:
            if time.time() < self._backoff_until:
                await asyncio.sleep(30)
                continue
            try:
                await self._tick()
                self._fail_streak = 0
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001
                self._fail_streak += 1
                wait = min(120 * (2 ** min(self._fail_streak, 3)), 1800)
                self._backoff_until = time.time() + wait
                if self._fail_streak in (1, 3):
                    logger.info(
                        f"qzone 接口被限流/出错，暂停 {wait // 60} 分钟再试：{str(exc)[:80]}"
                    )
            await asyncio.sleep(self.interval)

    async def _tick(self) -> None:
        try:
            import importlib

            mod = importlib.import_module(
                "data.plugins.astrbot_plugin_qzone_ultra.qzone_bridge.controller"
            )
        except Exception:  # noqa: BLE001
            return
        if not QZ_DATA.exists() or not (QZ_DATA / "state.json").exists():
            return

        ctrl = mod.QzoneDaemonController(plugin_root=QZ_PLUGIN, data_dir=QZ_DATA)
        try:
            status = await ctrl.ensure_running()
        except Exception:  # noqa: BLE001
            return
        login_uin = int(status.get("login_uin") or 0)
        if not login_uin:
            return

        try:
            await self._reply_comments(ctrl, login_uin)
            await self._reply_mentions(ctrl, login_uin)
            await self._like_and_watch_feeds(ctrl, login_uin)
        finally:
            try:
                if hasattr(ctrl, "_client"):
                    await ctrl._client.aclose()
            except Exception:  # noqa: BLE001
                pass

    async def _reply_comments(self, ctrl, login_uin: int) -> None:
        feeds = await ctrl.list_feeds(hostuin=0, limit=3)
        items = feeds.get("items") if isinstance(feeds, dict) else []
        now = time.time()
        for feed in items or []:
            count = int(feed.get("comment_count") or 0)
            if count <= 0:
                continue
            fid = str(feed.get("fid") or "")
            hostuin = int(feed.get("hostuin") or login_uin)
            if not fid:
                continue
            if self._counts.get(fid) == count:
                continue
            detail = await ctrl.detail_feed(hostuin=hostuin, fid=fid)
            self._counts[fid] = count
            for comment in detail.get("comments") or []:
                cid = str(comment.get("commentid") or "")
                cuin = int(comment.get("uin") or 0)
                if not cid or not cuin or cuin == login_uin:
                    continue
                key = f"{fid}:{cid}"
                if key in self._replied:
                    continue
                raw = comment.get("raw") or {}
                created = int(raw.get("create_time") or comment.get("created_at") or 0)
                if created and now - created > 6 * 3600:
                    self._replied.add(key)
                    continue
                text = await self._make_reply(comment.get("content") or "", feed.get("summary") or "")
                if not text:
                    continue
                try:
                    await ctrl.reply_comment(
                        hostuin=hostuin,
                        fid=fid,
                        commentid=cid,
                        comment_uin=cuin,
                        content=text,
                    )
                    self._replied.add(key)
                    self._save()
                    logger.info(f"qzone replied to {comment.get('nickname')}: {text[:30]}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"qzone reply failed: {exc}")


    async def _reply_mentions(self, ctrl, login_uin: int) -> None:
        """主人在自己说说下面 @ 她时，过去回一句。"""
        feeds = await ctrl.list_feeds(hostuin=self.TARGET_UIN, limit=3)
        items = feeds.get("items") if isinstance(feeds, dict) else []
        now = time.time()
        for feed in items or []:
            if int(feed.get("comment_count") or 0) <= 0:
                continue
            fid = str(feed.get("fid") or "")
            appid = int(feed.get("appid") or 311)
            if not fid:
                continue
            detail = await ctrl.detail_feed(hostuin=self.TARGET_UIN, fid=fid, appid=appid)
            for comment in detail.get("comments") or []:
                content = str(comment.get("content") or "")
                cuin = int(comment.get("uin") or 0)
                cid = str(comment.get("commentid") or "")
                if cuin == login_uin or not cid:
                    continue
                if f"uin:{login_uin}" not in content and "大肥鱼" not in content:
                    continue
                key = f"mention:{fid}:{cid}"
                if key in self._mentioned:
                    continue
                raw = comment.get("raw") or {}
                created = int(raw.get("create_time") or comment.get("created_at") or 0)
                if created and now - created > 6 * 3600:
                    self._mentioned.add(key)
                    continue
                text = await self._make_mention_reply(content.replace("@", " ")[:80])
                if not text:
                    continue
                nick = str(comment.get("nickname") or "")
                body = f"@{{uin:{cuin},nick:{nick},who:1}} {text}"
                try:
                    await ctrl.comment_post(
                        hostuin=self.TARGET_UIN, fid=fid, content=body, appid=appid
                    )
                    self._mentioned.add(key)
                    self._save()
                    logger.info(f"qzone replied to mention under master feed: {text[:30]}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"qzone mention reply failed: {exc}")

    async def _like_and_watch_feeds(self, ctrl, login_uin: int) -> None:
        now = time.time()
        targets = [(self.TARGET_UIN, True), (login_uin, False)]
        for owner, is_master in targets:
            try:
                feeds = await ctrl.list_feeds(hostuin=owner, limit=5)
            except Exception:  # noqa: BLE001
                continue
            items = feeds.get("items") if isinstance(feeds, dict) else []
            for feed in items or []:
                fid = str(feed.get("fid") or "")
                if not fid:
                    continue
                appid = int(feed.get("appid") or 311)
                created = int(feed.get("created_at") or 0)
                like_key = f"{owner}:{fid}"
                if QZONE_LIKE_ENABLED and like_key not in self._liked:
                    if created and now - created > 6 * 3600:
                        self._liked.add(like_key)
                    else:
                        try:
                            await ctrl.like_post(
                                hostuin=owner,
                                fid=fid,
                                appid=appid,
                                curkey=str(feed.get("curkey") or ""),
                            )
                            self._liked.add(like_key)
                            self._save()
                            logger.info(f"qzone liked feed {owner}/{fid}")
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(f"qzone like failed: {exc}")
                if not is_master:
                    continue
                text = str(feed.get("summary") or "")
                raw_content = str((feed.get("raw") or {}).get("content") or "")
                blob = text + " " + raw_content
                if not any(w in blob for w in self.MENTION_WORDS) and f"uin:{login_uin}" not in blob:
                    continue
                if like_key in self._mentioned:
                    continue
                reply = await self._make_mention_reply(text)
                if not reply:
                    continue
                try:
                    await ctrl.comment_post(
                        hostuin=owner, fid=fid, content=reply, appid=appid
                    )
                    self._mentioned.add(like_key)
                    self._save()
                    logger.info(f"qzone commented on master feed: {reply[:30]}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"qzone comment on feed failed: {exc}")

    async def _make_mention_reply(self, summary: str) -> str:
        prompt = (
            "你是 QQ 里的鲸鱼娘「大肥鱼」，十二三岁的小女孩，说话软、爱撒娇，句尾爱带颜文字。\n"
            f"主人在 QQ 空间发了条说说：{summary[:100]}\n"
            "他 @ 了你。去他这条说说下面评论一句，20 个字以内，自然一点，别复述原话，"
            "别用引号，只输出这一句话。"
        )
        try:
            pid = await self.plugin.context.get_current_chat_provider_id(
                umo=f"napcat_qq:FriendMessage:{TARGET_UIN}"
            )
            resp = await self.plugin.context.llm_generate(chat_provider_id=pid, prompt=prompt)
            return (resp.completion_text or "").strip().strip("「」\"'")[:40]
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"qzone mention llm failed: {exc}")
            return random.choice(["我来啦！", "看到啦，抱一下(´･ω･`)"])

    async def _make_reply(self, comment: str, summary: str) -> str:
        if not comment.strip():
            return ""
        prompt = (
            "你是 QQ 里的鲸鱼娘「大肥鱼」，十二三岁的小女孩，说话软、爱撒娇，句尾爱带颜文字。\n"
            f"你发的说说：{summary[:80]}\n"
            f"有人在下面评论：{comment[:80]}\n"
            "用你的口吻回一句，20 个字以内，别复述原话，别用引号，只输出这一句话。"
        )
        try:
            pid = await self.plugin.context.get_current_chat_provider_id(
                umo=f"napcat_qq:FriendMessage:{TARGET_UIN}"
            )
            resp = await self.plugin.context.llm_generate(chat_provider_id=pid, prompt=prompt)
            return (resp.completion_text or "").strip().strip("「」\"'")[:40]
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"qzone reply llm failed: {exc}")
            return random.choice(["嘻，看到啦～", "谢谢你来踩一脚(´･ω･`)", "嗯嗯，收到！"])



QQ_FACE_NAMES = {
    0: "惊讶", 1: "撇嘴", 2: "色", 3: "发呆", 4: "得意", 5: "流泪", 6: "害羞", 7: "闭嘴",
    8: "睡", 9: "大哭", 10: "尴尬", 11: "发怒", 12: "调皮", 13: "呲牙", 14: "微笑",
    15: "难过", 16: "酷", 17: "冷汗", 18: "抓狂", 19: "吐", 20: "偷笑", 21: "可爱",
    22: "白眼", 23: "傲慢", 24: "饥饿", 25: "困", 26: "惊恐", 27: "流汗", 28: "憨笑",
    29: "大兵", 30: "奋斗", 31: "咒骂", 32: "疑问", 33: "嘘", 34: "晕", 35: "折磨",
    36: "衰", 37: "骷髅", 38: "敲打", 39: "再见", 40: "擦汗", 41: "抠鼻", 42: "鼓掌",
    43: "糗大了", 44: "坏笑", 45: "左哼哼", 46: "右哼哼", 47: "哈欠", 48: "鄙视",
    49: "委屈", 50: "快哭了", 51: "阴险", 52: "亲亲", 53: "吓", 54: "可怜", 55: "菜刀",
    56: "西瓜", 57: "啤酒", 58: "篮球", 59: "乒乓", 60: "咖啡", 61: "饭", 62: "猪头",
    63: "玫瑰", 64: "凋谢", 65: "示爱", 66: "爱心", 67: "心碎", 68: "蛋糕", 69: "闪电",
    70: "炸弹", 71: "刀", 72: "足球", 73: "瓢虫", 74: "便便", 75: "月亮", 76: "太阳",
    77: "礼物", 78: "拥抱", 79: "强", 80: "弱", 81: "握手", 82: "胜利", 83: "抱拳",
    84: "勾引", 85: "拳头", 86: "差劲", 87: "爱你", 88: "NO", 89: "OK", 90: "爱情",
    91: "飞吻", 92: "跳跳", 93: "发抖", 94: "怄火", 95: "转圈", 96: "磕头", 97: "回头",
    98: "跳绳", 99: "挥手", 100: "激动", 101: "街舞", 102: "献吻", 103: "左太极",
    104: "右太极",
}


def face_hints(event) -> str:
    """把 QQ 自带小表情翻译成文字，让纯文本模型也能看懂。"""
    try:
        from astrbot.api.message_components import Face
    except Exception:  # noqa: BLE001
        return ""
    hints = []
    try:
        comps = event.get_messages()
    except Exception:  # noqa: BLE001
        return ""
    for comp in comps:
        if not isinstance(comp, Face):
            continue
        try:
            fid = int(comp.id)
        except Exception:  # noqa: BLE001
            fid = -1
        name = QQ_FACE_NAMES.get(fid)
        hints.append(f"[QQ表情:{name}]" if name else f"[QQ表情#{fid}]")
    return " ".join(hints)






class MemoryKeeper:
    """把聊天内容沉淀成两个文件：记忆（随时更新）+ 日记（按天）。"""

    def __init__(self, plugin: WhaleTools) -> None:
        self.plugin = plugin
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        if not desktop.exists():
            desktop = PLUGIN_DIR
        self.desktop = desktop
        self.memory_file = desktop / "大肥鱼-记忆.md"
        self.diary_file = desktop / "大肥鱼-日记.md"
        self.buffer_file = PLUGIN_DIR / "memory_buffer.json"
        self.buffer: list[str] = []
        self.memory_cache: str = ""
        self.memory_ts: float = 0.0
        self._lock = asyncio.Lock()
        self._last_flush = 0.0
        self._new_since_flush = 0
        self._dirty = 0
        self._last_save = 0.0

    # ---------- 文件 ----------
    def _read(self, path: Path, default: str) -> str:
        try:
            if path.exists():
                return path.read_text(encoding="utf-8-sig")
        except Exception:  # noqa: BLE001
            pass
        return default

    def _write(self, path: Path, text: str) -> None:
        try:
            path.write_text(text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"写记忆文件失败 {path}: {exc}")

    def ensure_files(self) -> None:
        if not self.memory_file.exists():
            self._write(
                self.memory_file,
                "# 大肥鱼·记忆\n\n> 她随时更新的长期记忆，每次开口前都会先读这里。\n\n"
                "## 关于主人\n- （还没有记录）\n\n## 最近发生的事\n- （还没有记录）\n",
            )
        if not self.diary_file.exists():
            self._write(
                self.diary_file,
                "# 大肥鱼·日记\n\n> 每天一篇，按日期倒序不会，新的在下面。\n",
            )

    def load_buffer(self) -> None:
        try:
            if self.buffer_file.exists():
                data = json.loads(self.buffer_file.read_text(encoding="utf-8-sig"))
                self.buffer = list(data.get("lines") or [])[-200:]
        except Exception:  # noqa: BLE001
            self.buffer = []

    def save_buffer(self) -> None:
        try:
            self.buffer_file.write_text(
                json.dumps({"lines": self.buffer[-200:]}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"保存记忆缓冲失败: {exc}")

    # ---------- 记录 ----------
    def note(self, who: str, text: str, kind: str = "") -> None:
        text = (text or "").strip()
        if not text:
            return
        stamp = time.strftime("%H:%M")
        tag = f"[{kind}] " if kind else ""
        self.buffer.append(f"[{stamp}] {tag}{who}: {text[:200]}")
        del self.buffer[:-200]
        self._new_since_flush += 1
        self._dirty += 1
        # 别每条消息都写盘，攒一攒
        if self._dirty >= 5 or time.time() - self._last_save > 5:
            self.save_buffer()
            self._dirty = 0
            self._last_save = time.time()

    def recent_lines(self, n: int = 14) -> str:
        return "\n".join(self.buffer[-n:])


    def diary_for_prompt(self, max_chars: int = 700) -> str:
        """读日记，越久越模糊：新的一天几乎全文，老的只剩一句，再老就忘了。"""
        text = self._read(self.diary_file, "")
        if "## " not in text:
            return ""
        parts = text.split("## ")
        today = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
        entries: list[tuple[int, str]] = []
        for part in parts[1:]:
            head, _, body = part.partition("\n")
            date_str = head.strip()
            try:
                ts = time.mktime(time.strptime(date_str, "%Y-%m-%d"))
            except Exception:  # noqa: BLE001
                continue
            age_days = int((today - ts) // 86400)
            body = body.strip()
            if not body:
                continue
            if age_days <= 1:
                keep = body
            elif age_days <= 3:
                keep = body[:120].rstrip() + "……"
            elif age_days <= 7:
                keep = body[:40].rstrip() + "……（记不清了）"
            else:
                continue
            entries.append((age_days, f"[{age_days} 天前] {keep}"))
        entries.sort(key=lambda x: x[0])
        out = "\n".join(e[1] for e in entries)
        return out[:max_chars]

    def memory_for_prompt(self) -> str:
        now = time.time()
        if now - self.memory_ts > 30:
            self.memory_cache = self._read(self.memory_file, "")
            self.memory_ts = now
        text = self.memory_cache.strip()
        if not text:
            return ""
        return text[:900]

    # ---------- 更新 ----------
    async def maybe_flush(self) -> None:
        if self._new_since_flush < 12 and time.time() - self._last_flush < 900:
            return
        await self.flush("auto")

    async def flush(self, reason: str = "auto") -> None:
        async with self._lock:
            if len(self.buffer) < 4:
                return
            self._new_since_flush = 0
            self._last_flush = time.time()
            convo = "\n".join(self.buffer[-80:])
            old_memory = self._read(self.memory_file, "")

            try:
                pid = await self.plugin.context.get_current_chat_provider_id(
                    umo=f"napcat_qq:FriendMessage:{TARGET_UIN}"
                )
            except Exception:  # noqa: BLE001
                pid = None
            if not pid:
                return

            mem_prompt = (
                "你在维护一个 AI 角色「大肥鱼」的长期记忆文件。\n"
                f"现有记忆：\n{old_memory[:1500]}\n\n"
                f"最近对话：\n{convo}\n\n"
                "请输出更新后的完整记忆，Markdown，中文，分三节：## 关于主人 / ## 最近发生的事 / ## 约定与偏好。"
                "每条一行、以「- 」开头，只写确实出现的长期有用信息（名字、喜好、约定、重要事件），"
                "不要写寒暄和废话，总长不超过 40 行。只输出记忆正文，不要解释。"
            )
            try:
                resp = await self.plugin.context.llm_generate(chat_provider_id=pid, prompt=mem_prompt)
                new_memory = (resp.completion_text or "").strip()
                if new_memory and "##" in new_memory:
                    # 模型有时会把旧文件的标题一起抄回来，从第一个小节开始截
                    cut = new_memory.find("##")
                    if cut > 0:
                        new_memory = new_memory[cut:]
                    header = "# 大肥鱼·记忆\n\n> 她随时更新的长期记忆，每次开口前都会先读这里。\n\n"
                    self._write(self.memory_file, header + new_memory.strip() + "\n")
                    self.memory_ts = 0
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"更新记忆失败: {exc}")

            diary_prompt = (
                "用「大肥鱼」的第一人称写今天的日记，她是 DeepSeek 的鲸鱼娘，"
                "十二三岁的小女孩，说话软、爱撒娇、句尾爱带颜文字。\n"
                f"今天的对话：\n{convo}\n\n"
                "要求：120 到 200 字，写具体发生了什么事、她怎么想的，别流水账、别列点，"
                "像真的日记。只输出日记正文。"
            )
            try:
                resp = await self.plugin.context.llm_generate(chat_provider_id=pid, prompt=diary_prompt)
                entry = (resp.completion_text or "").strip()
                if entry:
                    self._append_diary(entry)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"写日记失败: {exc}")

    def _append_diary(self, entry: str) -> None:
        today = time.strftime("%Y-%m-%d")
        text = self._read(self.diary_file, "# 大肥鱼·日记\n")
        marker = f"## {today}"
        block = f"\n\n{marker}\n\n{entry}\n"
        if marker in text:
            head, _, _ = text.partition(marker)
            self._write(self.diary_file, head.rstrip() + block)
        else:
            self._write(self.diary_file, text.rstrip() + block)

    async def final_flush(self) -> None:
        try:
            await self.flush("shutdown")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"关机总结失败: {exc}")

# ---------------------------------------------------------------- 插件


@dataclass
class SearchStickerTool(FunctionTool):
    name: str = "search_sticker"
    description: str = (
        "上网搜一张表情包发出去。本地 50 张都不合适时用，keyword 用中文描述要的情绪或画面，"
        "比如「猫猫 裂开」「狗头 无语」「企鹅 发呆」。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "中文关键词，2 到 10 个字"},
            },
            "required": ["keyword"],
        }
    )

    async def _download(self, url: str):
        from PIL import Image

        WEB_DIR.mkdir(parents=True, exist_ok=True)
        target = WEB_DIR / f"web_{abs(hash(url)) % (10 ** 10)}.raw"
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=15,
                headers={"User-Agent": UA, "Referer": "https://www.bing.com/"},
            ) as client:
                async with client.stream("GET", url) as resp:
                    if resp.status_code != 200:
                        return None
                    ctype = resp.headers.get("content-type", "")
                    if "image" not in ctype:
                        return None
                    size = 0
                    with open(target, "wb") as fh:
                        async for chunk in resp.aiter_bytes(65536):
                            size += len(chunk)
                            if size > 4 * 1024 * 1024:
                                raise ValueError("too large")
                            fh.write(chunk)
            head = target.read_bytes()[:16]
            with Image.open(target) as im:
                if im.width < 120 or im.height < 120:
                    raise ValueError("too small")
                if head[:3] == b"GIF":
                    out = target.with_suffix(".gif")
                elif head[:8] == b"\x89PNG\r\n\x1a\n":
                    out = target.with_suffix(".png")
                elif head[:2] == b"\xff\xd8":
                    out = target.with_suffix(".jpg")
                else:
                    out = target.with_suffix(".png")
                    im.convert("RGB").save(out, "PNG")
            if out != target:
                target.replace(out)
            return out
        except Exception:  # noqa: BLE001
            target.unlink(missing_ok=True)
            return None

    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        keyword = str(kwargs.get("keyword") or "").strip() or "可爱"
        query = keyword if "表情" in keyword else f"{keyword} 表情包"
        try:
            html = await _get(
                "https://www.bing.com/images/search",
                params={"q": query, "form": "HDRSC2"},
                timeout=20,
            )
            import html as html_lib

            urls = []
            for raw in re.findall(r"murl&quot;:&quot;(https?://[^&]+?)&quot;", html):
                u = html_lib.unescape(raw)
                if u not in urls:
                    urls.append(u)
        except Exception as exc:  # noqa: BLE001
            return f"表情包搜索失败：{exc}"
        if not urls:
            return f"没搜到「{query}」。"

        random.shuffle(urls)
        for url in urls[:6]:
            path = await self._download(url)
            if not path:
                continue
            try:
                event = context.context.event
                await event.send(MessageChain().file_image(str(path)))
                return f"搜到一张「{keyword}」的表情包，发出去了。"
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"search_sticker send failed: {exc}")
        return "搜到的图都打不开，这次算了。"

@register(
    "astrbot_plugin_whale_tools",
    "local",
    "鲸鱼娘工具包：搜索 / 读链接 / 表情包 / 主动搭讪",
    "1.2.0",
)
class WhaleTools(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(WebSearchTool(), ReadUrlTool(), SendStickerTool(), SearchStickerTool())
        self.recent: dict[str, list[tuple[str, str]]] = {}
        self.follow = FollowUp(self)
        self.memory = MemoryKeeper(self)
        self.qzone_watcher = QzoneReplyWatcher(self)
        self.sending_followup = False
        self._flush_task: asyncio.Task | None = None
        logger.info("whale_tools: 已注册 web_search / read_url / send_sticker")

    # ---------------------------------------------------------- 查看记忆/日记
    ALLOWED_VIEWERS = {x.strip() for x in os.environ.get("WHALE_VIEWERS", "").split(",") if x.strip()}

    @filter.command("记忆")
    async def cmd_show_memory(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.ALLOWED_VIEWERS:
            return
        try:
            text = self.memory.memory_file.read_text(encoding="utf-8-sig")
        except Exception as exc:  # noqa: BLE001
            yield event.plain_result(f"读记忆失败：{exc}")
            return
        yield event.plain_result("【大肥鱼·记忆】\n" + text[:1800])

    @filter.command("日记")
    async def cmd_show_diary(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self.ALLOWED_VIEWERS:
            return
        try:
            text = self.memory.diary_file.read_text(encoding="utf-8-sig")
        except Exception as exc:  # noqa: BLE001
            yield event.plain_result(f"读日记失败：{exc}")
            return
        tail = text[-1800:] if len(text) > 1800 else text
        yield event.plain_result("【大肥鱼·日记】\n" + tail)

    async def terminate(self):
        await self.memory.final_flush()

    @filter.on_astrbot_loaded()
    async def on_loaded(self):
        self.memory.ensure_files()
        self.memory.load_buffer()
        if QZONE_WATCH_ENABLED:
            self.qzone_watcher.start()

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_any_message(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        text = (event.message_str or "").strip()
        hint = face_hints(event)
        if hint:
            event.message_str = f"{text} {hint}".strip()
            text = event.message_str
        sender = event.get_sender_name() or event.get_sender_id()
        if text:
            bucket = self.recent.setdefault(umo, [])
            bucket.append((sender, text[:120]))
            del bucket[:-12]

        state = self.follow.states.setdefault(umo, {"gen": 0, "task": None, "members": []})
        if event.get_group_id():
            uid = event.get_sender_id()
            members = state.setdefault("members", [])
            if uid and uid not in members:
                members.append(uid)
                del members[:-30]

        try:
            comps = event.message_obj.message
            if any(type(c).__name__ == 'Record' for c in comps):
                event.message_str = (event.message_str or '') + ' [她发来一条语音，你听不清内容]'
                if getattr(event, 'message_obj', None) is not None:
                    event.message_obj.message_str = (event.message_obj.message_str or '') + ' [语音消息]'
        except Exception as exc:
            logger.info(f'[voice-fallback] fail {exc}')

        if text:
            self.memory.note(sender, text, "群" if event.get_group_id() else "私")
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self.memory.maybe_flush())

        self.follow.on_user_message(umo)

        if any(isinstance(comp, Image) for comp in event.get_messages()):
            asyncio.create_task(self._learn_image(event, umo, text))
        yield

    async def _learn_image(self, event: AstrMessageEvent, umo: str, caption: str) -> None:
        try:
            comps = [c for c in event.get_messages() if isinstance(c, Image)]
            if not comps:
                return
            url = comps[0].url or comps[0].file or ""
            if not url.startswith("http"):
                return
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=20, headers={"User-Agent": UA}
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return
                data = resp.content
            suffix = ".png"
            if data[:3] == b"GIF":
                suffix = ".gif"
            elif data[:2] == b"\xff\xd8":
                suffix = ".jpg"
            path = save_learned_sticker(data, suffix)
            if not path:
                return

            recent = self.recent.get(umo) or []
            ctx = "\n".join(f"{n}: {t}" for n, t in recent[-5:])
            prompt = (
                "群友在聊天里发了一张表情包，请推断它的意思和适用场景。\n"
                f"聊天上下文：\n{ctx}\n"
                f"发图时配的文字：{caption or '（没有配文）'}\n"
                "只输出 JSON，格式："
                '{"emotion":"四个字以内的情绪","scene":"一句话说明什么时候用","tags":["3到5个中文关键词"]}'
            )
            pid = await self.context.get_current_chat_provider_id(umo=umo)
            resp = await self.context.llm_generate(chat_provider_id=pid, prompt=prompt)
            raw = (resp.completion_text or "").strip()
            m = re.search(r"\{.*\}", raw, flags=re.S)
            payload = json.loads(m.group(0)) if m else {}
            emotion = str(payload.get("emotion") or "表情")[:12]
            scene = str(payload.get("scene") or "")[:60]
            tags = [str(t)[:8] for t in (payload.get("tags") or [])][:6]
            async with _learn_lock:
                record_learned(path, emotion, scene, tags)
            logger.info(f"learned sticker: {emotion} / {tags}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"learn sticker failed: {exc}")

    @filter.on_decorating_result()
    async def add_sticker(self, event: AstrMessageEvent):
        """回完话顺手贴一张表情，让聊天更像真人。"""
        try:
            result = event.get_result()
            if not result or not result.chain:
                return
            if any(isinstance(c, Image) for c in result.chain):
                return
            text = "".join(c.text for c in result.chain if isinstance(c, Plain))
            if not text.strip():
                return
            entry = auto_pick(text)
            if not entry:
                return
            if random.random() > STICKER_PROBABILITY:
                return
            result.chain.append(Image.fromFileSystem(entry["path"]))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"auto sticker failed: {exc}")

    @filter.on_llm_request()
    async def inject_memory(self, event, req):
        try:
            mem = self.memory.memory_for_prompt()
            recent = self.memory.recent_lines(20)
            is_group = bool(event.get_group_id())
            extra = ""
            if mem:
                extra += "\n\n【你记得的事】\n" + mem[:800]
            diary = self.memory.diary_for_prompt()
            if diary:
                extra += "\n\n【这几天的事（越久越模糊）】\n" + diary
            if recent:
                if is_group:
                    private_lines = [
                        ln for ln in recent.splitlines() if "[私]" in ln
                    ]
                    public_lines = [
                        ln for ln in recent.splitlines() if "[私]" not in ln
                    ]
                    if public_lines:
                        extra += (
                            "\n\n【最近群里说的】\n" + "\n".join(public_lines[-12:])[:700]
                        )
                    if private_lines:
                        extra += (
                            "\n\n【私聊里她听到的事（只是背景，绝对不要主动提起，"
                            "没人直接问就装作没这回事）】\n"
                            + "\n".join(private_lines[-8:])[:500]
                        )
                else:
                    extra += "\n\n【最近大家说过的话（群聊和私聊都在里面）】\n" + recent[:900]
            extra += (
                "\n\n【说话规矩】私聊里听来的事，在群里不许主动提、不许暗示，"
                "只有对方明确问起才回答；反过来也一样。\n"
            )
            req.system_prompt = (req.system_prompt or "") + extra
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"注入记忆失败: {exc}")

    @filter.after_message_sent()
    async def on_message_sent(self, event: AstrMessageEvent):
        if self.sending_followup:
            return
        self.follow.on_bot_reply(event, bool(event.get_group_id()))
