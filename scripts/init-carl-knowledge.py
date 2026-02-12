#!/usr/bin/env python3
"""
初始化 Carl 的 Privacy Guard 知识库

从 USER.md、people/、data/ 提取信息，分类为 public/private。
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "privacy"))

from knowledge_store import KnowledgeStore, KnowledgeItem, KNOWLEDGE_DIR

SGT = timezone(timedelta(hours=8))
NOW = datetime.now(SGT).isoformat()

store = KnowledgeStore(KNOWLEDGE_DIR)

# Clear existing Carl data
carl_dir = KNOWLEDGE_DIR / "carl"
carl_dir.mkdir(parents=True, exist_ok=True)
for f in carl_dir.glob("*.jsonl"):
    f.unlink()

items = []

# ═══════════════════════════════════════════
# PUBLIC — 可在群聊中使用的信息
# ═══════════════════════════════════════════

public_items = [
    # 技能和兴趣
    ("会 Python 和 JavaScript 编程", "skill", ["编程", "技术"]),
    ("对 AI/LLM 训练有浓厚兴趣，研究从零训练模型", "skill", ["AI", "研究"]),
    ("喜欢看演唱会和音乐会", "preference", ["音乐", "娱乐"]),
    ("经常带孩子看儿童剧", "preference", ["戏剧", "亲子"]),
    ("喜欢徒步和户外运动", "preference", ["运动", "户外"]),
    ("想用 AI 玩小丑牌 (Balatro)", "preference", ["游戏", "AI"]),
    # 公开身份
    ("使用 OpenClaw AI 助手平台", "preference", ["技术", "工具"]),
    ("居住在新加坡", "preference", ["地点"]),
]

for i, (content, category, tags) in enumerate(public_items, 1):
    items.append(KnowledgeItem(
        id=f"k_carl_pub_{i:03d}",
        user="carl",
        content=content,
        visibility="public",
        category=category,
        source="user_declared",
        created=NOW,
        tags=tags,
    ))

# ═══════════════════════════════════════════
# PRIVATE — 仅私聊可用的信息
# ═══════════════════════════════════════════

private_items = [
    # 个人身份
    ("Carl 真名 bo li", "contact_private", ["身份"], None),
    ("生日 1984-04-29", "contact_private", ["生日"], None),
    ("Email: adam429.lee@gmail.com", "auth", ["联系方式"], None),
    ("Lark: carlnoah6@gmail.com", "auth", ["联系方式"], None),
    ("Super admin of anz.io Lark org", "auth", ["权限"], None),

    # 家庭
    ("大儿子元宝 (Yuanbao)，2019-03-22 生日，快7岁", "family", ["孩子"], None),
    ("小女儿朵朵 (Duoduo)，2021-05-16 生日，快5岁", "family", ["孩子"], None),
    ("元宝每周日 9:30-10:20 上架子鼓课", "family", ["孩子", "课程"], None),
    ("朵朵睡觉比元宝早，晚上演出一般不带她", "family", ["孩子"], None),
    ("孩子晚饭一般 17:30-18:30", "family", ["作息"], None),
    ("倾向于让小朋友 20:00 左右上床", "family", ["作息"], None),

    # 日程和活动
    ("通常早晨 7:00 起床", "calendar", ["作息"], None),
    ("一般不安排太晚的活动（因为孩子的作息）", "calendar", ["作息"], None),
    ("和马原约每两周见一次，公司会谈+Kent Ridge Park 徒步", "calendar", ["定期"], None),

    # 人际关系详情
    ("马原是其公司的投资人+顾问角色，有多个公司", "contact_private", ["商务"], None),
    ("马原办公地点 The Cavendish, 85 Science Park Drive, Singapore 118259", "contact_private", ["地址"], None),
    ("马原宝宝叫豆豆", "family", ["朋友家人"], None),
    ("卢琦是好朋友，别称鱼丸妈妈", "contact_private", ["朋友"], None),
    ("卢琦的孩子：鱼丸、森宝", "family", ["朋友家人"], None),
    ("费叔叔/老费，北京朋友，不定期来新加坡住 Carl 家里", "contact_private", ["朋友"], None),
    ("Junyi 是合伙人，定期来新加坡住 Carl 家里", "contact_private", ["商务"], None),

    # 重要日期/事件
    ("2026-02-22 16:30 Charlie Cook's Favourite Book 儿童剧 Victoria Theatre", "calendar", ["事件"], None),
    ("2026-03-22 元宝实际生日", "calendar", ["生日"], None),
    ("2026-03-29 上午 元宝7岁生日聚会 在家办 19位小朋友", "calendar", ["事件"], None),
    ("2026-03-28 20:00 Harry Potter 音乐会 和 Junyi 一起去", "calendar", ["事件"], None),
    ("2026-03-29 20:00-23:00 汪苏泷演唱会 和 Junyi 一起", "calendar", ["事件"], None),
    ("2026-04-15 Les Misérables 音乐剧", "calendar", ["事件"], None),

    # 工作偏好
    ("最烦重复说同一件事，系统不记住他说过的东西", "dm_content", ["偏好"], None),
    ("希望 Luna 是协作者而非指令执行器", "dm_content", ["偏好"], None),
    ("喜欢快速决策，不喜欢被太多选项淹没", "dm_content", ["偏好"], None),
    ("不纠结 token 成本，专注变强变独立", "dm_content", ["偏好"], None),
]

for i, (content, category, tags, _) in enumerate(private_items, 1):
    items.append(KnowledgeItem(
        id=f"k_carl_prv_{i:03d}",
        user="carl",
        content=content,
        visibility="private",
        category=category,
        source="user_declared",
        created=NOW,
        tags=tags,
    ))

# Save all items
for item in items:
    store.add(item)

# Summary
pub_count = len([i for i in items if i.visibility == "public"])
prv_count = len([i for i in items if i.visibility == "private"])
print(f"✅ Carl 知识库初始化完成:")
print(f"   Public:  {pub_count} 条")
print(f"   Private: {prv_count} 条")
print(f"   存储位置: {carl_dir}")
