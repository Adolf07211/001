# 大肥鱼 · AstrBot 插件与人格包

一个跑在 QQ 上的「鲸鱼娘」陪伴机器人：会聊天、会发表情、记得你、还会自己写日记。

> 供学习交流使用。QQ 官方协议不支持第三方客户端，使用本项目存在账号被限制的风险，请自行评估。

---

## 功能

| 功能 | 说明 |
|---|---|
| 🎭 **人格** | 娇八分傲两分的小女孩「大肥鱼」，DeepSeek 鲸鱼娘 |
| 💬 **分段回复** | 一句话拆成 2~3 条发，间隔按字数计算（`y = log₂.₆(x)` 秒） |
| 🖼️ **表情包** | 内置 310 张自绘表情，按情绪自动选图，最近 15 张不重复 |
| 🧠 **长期记忆** | 自动把聊天提炼成「记忆」，每轮对话前注入 |
| 📔 **日记** | 每天写一篇，越久越模糊（过期自动淡忘） |
| 🔇 **群聊接话** | 群里冷场到阈值时偶尔插一句，不会刷屏 |
| 🌐 **联网** | 工具式联网搜索、读网页 |
| 📱 **QQ 空间** | 可发说说、评说说（可选，默认关闭自动巡检） |

---

## 目录结构

```
大肥鱼-开源/
├─ plugin/                 AstrBot 插件（放进 data/plugins/）
│  ├─ main.py              主逻辑
│  ├─ metadata.yaml        插件元信息
│  ├─ stickers/index.json  310 张表情的索引（图片自己生成）
│  └─ learned/             群友发的表情会学到这里
├─ persona/大肥鱼人设.md     人格提示词 + 调参建议
├─ config/                 配置示例与说明
├─ scripts/                表情包生成脚本
├─ deploy/                 docker-compose 部署示例
└─ patches/                对 AstrBot 核心的可选改动说明
```

---

## 快速开始

### 1. 准备环境

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) 4.29.x
- [NapCat](https://github.com/NapNeko/NapCatQQ)（QQ 协议端）
- 一个能接受风险的 QQ 小号

### 2. 安装插件

把 `plugin/` 整个目录复制到：

```
AstrBot/data/plugins/astrbot_plugin_whale_tools/
```

### 3. 生成表情图

`plugin/stickers/index.json` 只有索引，图片要自己渲染：

```bash
pip install pillow
python scripts/gen_base_stickers.py     # 生成 219 张
python scripts/gen_extra_stickers.py    # 补齐到 310 张
```

脚本默认用 Windows 自带「微软雅黑」，其他系统请改脚本里的 `FONT_*` 路径。

### 4. 配置

**人格**：把 `persona/大肥鱼人设.md` 里「【人格提示词】」以下的部分贴进 AstrBot 的「人格 → 系统提示词」，并把里面的「主人」「YOUR_QQ」换成你自己。

**接话阈值**：在 `AstrBot/data/whale_wake.json` 写：

```json
{ "group_reply_threshold": 15, "wake_on_unknown_reply": true }
```

**环境变量**（可选）：

| 变量 | 作用 |
|---|---|
| `WHALE_TARGET_UIN` | 你的 QQ 号（空间巡检用） |
| `WHALE_VIEWERS` | 允许用 `/记忆` `/日记` 的 QQ，逗号分隔 |
| `WHALE_FOLLOWUP_SPEED` | 主动搭话加速倍率，测试用，正式保持 1 |

### 5. 插件内开关

`plugin/main.py` 顶部：

```python
QZONE_WATCH_ENABLED = False     # QQ 空间自动回评/回@
STICKER_PROBABILITY = 0.5       # 自动发表情概率
FOLLOWUP_GROUP_ENABLED = False  # 群聊主动搭话
```

### 6. 启动

```bash
cd AstrBot
python main.py
```

NapCat 侧配置反向 WebSocket：`ws://127.0.0.1:6199/ws`。

---

## 命令

| 命令 | 权限 | 说明 |
|---|---|---|
| `/记忆` | 管理员 | 把长期记忆文件内容发给你 |
| `/日记` | 管理员 | 把最近的日记发给你 |

---

## 记忆系统设计

三层，由近到远：

```
最近对话（实时，14 条原始消息，群聊私聊共享）
    ↓ 每 12 条或 15 分钟提炼
长期记忆（Markdown，注入 system prompt）
    ↓ 同时
日记（每天一篇，按时间衰减）
```

**衰减规则**（`diary_for_prompt`）：

| 时间 | 保留 |
|---|---|
| 今天 / 昨天 | 全文 |
| 2~3 天前 | 前 120 字 |
| 4~7 天前 | 前 40 字 +「记不清了」 |
| 8 天以上 | 不再出现 |

记忆和日记默认写在 `Desktop/大肥鱼-记忆.md`、`Desktop/大肥鱼-日记.md`，没有桌面目录时落在插件目录下。都是普通 Markdown，可以手改。

---

## 关于风控

这套东西**违反 QQ 用户协议**（使用非官方客户端），风险真实存在：

- 异地登录 + 手机与服务器同时在线 → 最容易被判定异常
- 主动发消息、主动 @ 人、高频互动 → 加重风险
- 建议：用小号、新号先养 2 周、固定 IP、头几天只做被动回复

默认配置已经是保守档：群聊不主动、空间巡检关闭、表情 50%、回复间隔按字数。

---

## 协议

AGPL-3.0（与 AstrBot 保持一致）。

第三方插件 `astrbot_plugin_qzone_ultra` 不在本项目中，版权归其作者。
