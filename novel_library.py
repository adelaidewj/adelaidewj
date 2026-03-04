#!/usr/bin/env python3
"""
小说素材库 Novel Library Tool
==============================
从小说/故事中提取人物、时代、地点、关系、事件、金句、搞笑片段等，
存入本地素材库，并可重新组合生成新小说、剧本、场景或金句。

命令一览:
  add <文件>          从文件导入小说
  add-text            交互式粘贴文本
  list                列出素材库所有作品
  show <id>           查看作品详细素材
  delete <id>         删除作品
  search <关键词>      跨作品搜索素材
  quotes              浏览所有金句
  funny               浏览所有搞笑片段
  generate            生成新故事大纲
  generate-scene      生成特定类型场景（搞笑/浪漫/悬疑/虐心/反转）
  generate-quote      生成新金句（模仿指定风格）
"""

import anthropic
import json
import os
import uuid
import argparse
import sys
from pathlib import Path
from datetime import datetime

LIBRARY_FILE = "novel_library.json"


# ─────────────────────────────────────────────
# 数据库（本地 JSON）
# ─────────────────────────────────────────────

def load_library() -> dict:
    if Path(LIBRARY_FILE).exists():
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"novels": []}


def save_library(data: dict):
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# 提取素材（扩展版）
# ─────────────────────────────────────────────

EXTRACT_PROMPT = """请仔细分析以下小说/故事文本，提取所有关键素材，严格按 JSON 格式返回，不加任何额外说明。

JSON 格式如下：
{{
  "characters": [
    {{
      "name": "人物姓名",
      "description": "人物简介",
      "traits": ["性格特征"],
      "role": "主角/配角/反派等",
      "arc": "人物弧线：如何成长或转变，如：从懦弱到勇敢、从善良到堕落",
      "speech_style": "说话口吻特点，如：爱用反问、说话简短、喜欢押韵"
    }}
  ],
  "era": "故事时代背景",
  "locations": ["地点1", "地点2"],
  "relationships": [
    {{
      "from": "人物A",
      "to": "人物B",
      "type": "关系类型",
      "description": "关系简述",
      "tension": "关系张力/矛盾点"
    }}
  ],
  "events": [
    {{
      "title": "事件标题",
      "description": "事件描述",
      "characters": ["相关人物"],
      "location": "地点",
      "significance": "对故事的意义",
      "turning_point": true
    }}
  ],
  "quotes": [
    {{
      "text": "金句原文",
      "speaker": "说话者（旁白则填'旁白'）",
      "context": "说这句话的背景",
      "type": "类型：感悟/讽刺/煽情/霸气/哲理/告白/诀别"
    }}
  ],
  "funny_scenes": [
    {{
      "title": "搞笑片段标题",
      "description": "场景描述",
      "characters": ["涉及人物"],
      "comedy_type": "喜剧类型：误会/反差/吐槽/尬聊/意外/打脸/自嘲",
      "punchline": "包袱/笑点所在"
    }}
  ],
  "conflicts": [
    {{
      "type": "冲突类型：人与人/人与自我/人与社会/人与命运",
      "description": "冲突描述",
      "parties": ["冲突双方"],
      "resolution": "如何解决或未解决"
    }}
  ],
  "foreshadowing": [
    {{
      "hint": "伏笔内容",
      "payoff": "对应的揭示或结果（如文本中有的话）"
    }}
  ],
  "emotional_arc": "情绪曲线描述，如：平静→紧张→崩溃→希望→圆满",
  "symbols": ["象征意象，如：红玫瑰=热烈的爱"],
  "themes": ["主题"],
  "tone": "整体基调",
  "writing_style": "写作风格描述，如：白描为主、大量心理描写、幽默调侃"
}}

小说文本：
{text}
"""


def extract_elements(text: str, title: str) -> dict:
    client = anthropic.Anthropic()
    print(f"  正在分析「{title}」...")

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=6000,
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(text=text[:10000])}]
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    return json.loads(raw)


# ─────────────────────────────────────────────
# 生成：故事大纲
# ─────────────────────────────────────────────

GENERATE_STORY_PROMPT = """你是一位才华横溢的小说家。根据以下素材库元素，创作一篇新故事的详细大纲。

【可用素材】
{elements_json}

【创作要求】
- 时代背景：{era}
- 指定人物：{characters}
- 故事风格：{style}
- 创作类型：{story_type}

输出格式：
1. 【故事标题】
2. 【一句话简介】
3. 【主要人物设定】（可改编原有人物）
4. 【故事大纲】
   第一幕（开端与铺垫）
   第二幕（发展与冲突激化）
   第三幕（高潮、反转与结局）
5. 【核心冲突】
6. 【主题立意】
7. 【建议金句方向】（可在故事中放置的情感爆点台词方向）

自由发挥，让素材产生新的化学反应。
"""


def generate_story(library: dict, characters=None, era=None, style="不限", story_type="小说", output_file=None):
    if not library["novels"]:
        print("素材库为空，请先用 add 命令导入小说。")
        return

    pool = _build_pool(library)
    char_list = _filter_chars(pool["characters"], characters)

    selected = {
        "characters": char_list[:5],
        "events": pool["events"][:5],
        "relationships": pool["relationships"][:4],
        "conflicts": pool["conflicts"][:3],
        "locations": pool["locations"][:5],
        "symbols": pool["symbols"][:4],
        "funny_scenes": pool["funny_scenes"][:2],
    }

    client = anthropic.Anthropic()
    print("  正在创作新故事大纲...\n")
    result = _stream_and_collect(client, GENERATE_STORY_PROMPT.format(
        elements_json=json.dumps(selected, ensure_ascii=False, indent=2),
        era=era or "自由选择",
        characters=characters or "自由选择",
        style=style,
        story_type=story_type
    ))
    if output_file:
        _save_output(output_file, result)


# ─────────────────────────────────────────────
# 生成：特定类型场景
# ─────────────────────────────────────────────

GENERATE_SCENE_PROMPT = """你是一位专业编剧。请根据以下素材，写一段【{scene_type}】类型的场景。

【可用人物】
{characters_json}

【可用地点】{locations}

【参考搞笑片段（如有）】
{funny_json}

【参考金句（如有）】
{quotes_json}

要求：
- 场景类型：{scene_type}
- 长度：500-800字
- 有完整的场景起承转合
- 对白生动，符合各人物说话风格
- {scene_type}类型的核心要到位：
  · 搞笑：包袱要响，节奏要准，笑点自然
  · 浪漫：细节到位，情绪渐进，有回味
  · 虐心：情绪积累，戳心一击，余韵悠长
  · 悬疑：信息控制，氛围营造，留悬念
  · 反转：前后呼应，意外合理，回味无穷
  · 励志：共情铺垫，爆发有力，感染人心

指定人物：{characters}
指定地点：{location}
"""


def generate_scene(library: dict, scene_type="搞笑", characters=None, location=None, output_file=None):
    if not library["novels"]:
        print("素材库为空，请先导入小说。")
        return

    pool = _build_pool(library)
    char_list = _filter_chars(pool["characters"], characters)

    client = anthropic.Anthropic()
    print(f"  正在生成【{scene_type}】场景...\n")
    result = _stream_and_collect(client, GENERATE_SCENE_PROMPT.format(
        scene_type=scene_type,
        characters_json=json.dumps(char_list[:4], ensure_ascii=False, indent=2),
        locations=", ".join(pool["locations"][:6]),
        funny_json=json.dumps(pool["funny_scenes"][:3], ensure_ascii=False, indent=2),
        quotes_json=json.dumps(pool["quotes"][:3], ensure_ascii=False, indent=2),
        characters=characters or "自由选择",
        location=location or "自由选择"
    ))
    if output_file:
        _save_output(output_file, result)


# ─────────────────────────────────────────────
# 生成：金句
# ─────────────────────────────────────────────

GENERATE_QUOTE_PROMPT = """你是一位擅长写金句的作家。请根据以下素材和要求，创作 10 句新的金句。

【参考金句风格】
{ref_quotes}

【人物素材】
{characters}

【主题参考】{themes}

创作要求：
- 风格：{style}
- 类型：{quote_type}（可多种混合）
- 每句要有独立的感染力，能单独传播

输出格式（直接列出，不加序号以外的内容）：
1. [金句] —— [简短说明：适用场景或情绪]
2. ...
...
10. ...
"""


def generate_quote(library: dict, style="不限", quote_type="感悟/哲理", output_file=None):
    if not library["novels"]:
        print("素材库为空，请先导入小说。")
        return

    pool = _build_pool(library)
    ref = pool["quotes"][:6]
    chars = [f"{c['name']}：{c.get('description','')}" for c in pool["characters"][:5]]
    themes = list({t for n in library["novels"] for t in n.get("elements", {}).get("themes", [])})[:6]

    client = anthropic.Anthropic()
    print(f"  正在生成【{quote_type}】金句...\n")
    result = _stream_and_collect(client, GENERATE_QUOTE_PROMPT.format(
        ref_quotes=json.dumps(ref, ensure_ascii=False, indent=2),
        characters="\n".join(chars),
        themes="、".join(themes),
        style=style,
        quote_type=quote_type
    ))
    if output_file:
        _save_output(output_file, result)


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def _build_pool(library: dict) -> dict:
    """汇总所有素材"""
    pool = {
        "characters": [], "locations": [], "events": [],
        "relationships": [], "conflicts": [], "quotes": [],
        "funny_scenes": [], "symbols": [], "themes": []
    }
    for novel in library["novels"]:
        e = novel.get("elements", {})
        for key in pool:
            val = e.get(key, [])
            if isinstance(val, list):
                pool[key].extend(val)
    return pool


def _filter_chars(all_chars: list, names_str: str) -> list:
    if not names_str:
        return all_chars[:5]
    names = [n.strip() for n in names_str.split(",")]
    filtered = [c for c in all_chars if c["name"] in names]
    return filtered if filtered else all_chars[:5]


def _stream_and_collect(client, prompt: str) -> str:
    chunks = []
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            chunks.append(text)
    print("\n")
    return "".join(chunks)


def _save_output(filename: str, content: str):
    path = Path(filename)
    path.write_text(content, encoding="utf-8")
    print(f"  已保存到 {filename}")


def _print_elements_summary(elements: dict):
    print(f"\n  时代：{elements.get('era', '未知')}")
    print(f"  基调：{elements.get('tone', '未知')}")
    print(f"  情绪曲线：{elements.get('emotional_arc', '未知')}")
    chars = [c["name"] for c in elements.get("characters", [])]
    print(f"  人物：{', '.join(chars)}")
    print(f"  地点：{', '.join(elements.get('locations', []))}")
    print(f"  金句：{len(elements.get('quotes', []))} 句")
    print(f"  搞笑片段：{len(elements.get('funny_scenes', []))} 个")
    print(f"  事件：{len(elements.get('events', []))} 个")
    print(f"  伏笔：{len(elements.get('foreshadowing', []))} 条")


# ─────────────────────────────────────────────
# CLI 命令
# ─────────────────────────────────────────────

def cmd_add(args):
    path = Path(args.file)
    if not path.exists():
        print(f"错误：找不到文件 {args.file}")
        sys.exit(1)
    text = path.read_text(encoding="utf-8")
    title = args.title or path.stem
    elements = extract_elements(text, title)
    library = load_library()
    novel_id = str(uuid.uuid4())[:8]
    library["novels"].append({
        "id": novel_id, "title": title,
        "added_at": datetime.now().isoformat(),
        "text_preview": text[:200] + "..." if len(text) > 200 else text,
        "elements": elements
    })
    save_library(library)
    print(f"\n✓ 已添加「{title}」(id: {novel_id})")
    _print_elements_summary(elements)


def cmd_add_text(args):
    title = args.title or input("故事标题：").strip() or "未命名"
    print("请输入故事文本（Ctrl+D 结束）：")
    try:
        text = sys.stdin.read()
    except KeyboardInterrupt:
        print("\n已取消。")
        return
    if not text.strip():
        print("未输入内容。")
        return
    elements = extract_elements(text, title)
    library = load_library()
    novel_id = str(uuid.uuid4())[:8]
    library["novels"].append({
        "id": novel_id, "title": title,
        "added_at": datetime.now().isoformat(),
        "text_preview": text[:200] + "..." if len(text) > 200 else text,
        "elements": elements
    })
    save_library(library)
    print(f"\n✓ 已添加「{title}」(id: {novel_id})")
    _print_elements_summary(elements)


def cmd_list(args):
    library = load_library()
    novels = library["novels"]
    if not novels:
        print("素材库为空。")
        return
    print(f"\n{'ID':<10} {'标题':<20} {'人物':<5} {'金句':<5} {'搞笑':<5} {'事件':<5} {'添加时间'}")
    print("─" * 70)
    for n in novels:
        e = n.get("elements", {})
        print(
            f"{n['id']:<10} {n['title'][:18]:<20} "
            f"{len(e.get('characters', [])):<5} "
            f"{len(e.get('quotes', [])):<5} "
            f"{len(e.get('funny_scenes', [])):<5} "
            f"{len(e.get('events', [])):<5} "
            f"{n.get('added_at', '')[:10]}"
        )
    print(f"\n共 {len(novels)} 部作品")


def cmd_show(args):
    library = load_library()
    novel = next((n for n in library["novels"] if n["id"] == args.id), None)
    if not novel:
        print(f"找不到 id={args.id}")
        return

    e = novel["elements"]
    print(f"\n{'═'*55}")
    print(f"  {novel['title']}")
    print(f"{'═'*55}")
    print(f"时代：{e.get('era','?')}  基调：{e.get('tone','?')}  风格：{e.get('writing_style','?')}")
    print(f"情绪曲线：{e.get('emotional_arc','?')}")
    print(f"主题：{', '.join(e.get('themes',[]))}")
    print(f"象征意象：{', '.join(e.get('symbols',[]))}")

    print("\n【人物】")
    for c in e.get("characters", []):
        print(f"  {c['name']} [{c.get('role','')}] — {c.get('description','')}")
        print(f"    弧线：{c.get('arc','?')}  口吻：{c.get('speech_style','?')}")

    print("\n【地点】" + "  ".join(e.get("locations", [])))

    print("\n【人物关系】")
    for r in e.get("relationships", []):
        print(f"  {r['from']} ─{r['type']}→ {r['to']}：{r.get('description','')}  张力：{r.get('tension','')}")

    print("\n【冲突】")
    for c in e.get("conflicts", []):
        print(f"  [{c['type']}] {c['description']}  → {c.get('resolution','未解决')}")

    print("\n【关键事件】")
    for i, ev in enumerate(e.get("events", []), 1):
        tp = "【转折点】" if ev.get("turning_point") else ""
        print(f"  {i}. {tp}【{ev['title']}】{ev.get('description','')}")

    print("\n【金句】")
    for q in e.get("quotes", []):
        print(f"  [{q.get('type','')}] 「{q['text']}」—— {q.get('speaker','?')}")
        print(f"    背景：{q.get('context','')}")

    print("\n【搞笑片段】")
    for f in e.get("funny_scenes", []):
        print(f"  [{f.get('comedy_type','')}] 【{f['title']}】{f.get('description','')}")
        print(f"    包袱：{f.get('punchline','')}")

    print("\n【伏笔线索】")
    for fs in e.get("foreshadowing", []):
        print(f"  伏笔：{fs.get('hint','')}  →  揭示：{fs.get('payoff','？')}")


def cmd_quotes(args):
    """浏览所有金句"""
    library = load_library()
    all_quotes = []
    for novel in library["novels"]:
        for q in novel.get("elements", {}).get("quotes", []):
            all_quotes.append((novel["title"], q))

    if not all_quotes:
        print("暂无金句，导入小说后自动提取。")
        return

    # 过滤类型
    if args.type:
        all_quotes = [(t, q) for t, q in all_quotes if args.type in q.get("type", "")]

    print(f"\n共 {len(all_quotes)} 句金句\n{'─'*55}")
    for title, q in all_quotes:
        print(f"\n[{q.get('type','')}] 《{title}》")
        print(f"  「{q['text']}」")
        print(f"   —— {q.get('speaker','?')}  背景：{q.get('context','')}")


def cmd_funny(args):
    """浏览所有搞笑片段"""
    library = load_library()
    all_funny = []
    for novel in library["novels"]:
        for f in novel.get("elements", {}).get("funny_scenes", []):
            all_funny.append((novel["title"], f))

    if not all_funny:
        print("暂无搞笑片段。")
        return

    if args.type:
        all_funny = [(t, f) for t, f in all_funny if args.type in f.get("comedy_type", "")]

    print(f"\n共 {len(all_funny)} 个搞笑片段\n{'─'*55}")
    for title, f in all_funny:
        print(f"\n[{f.get('comedy_type','')}] 《{title}》 — 【{f['title']}】")
        print(f"  {f.get('description','')}")
        print(f"  包袱：{f.get('punchline','')}")
        print(f"  人物：{', '.join(f.get('characters',[]))}")


def cmd_search(args):
    """跨作品关键词搜索"""
    keyword = args.keyword.lower()
    library = load_library()
    results = []

    for novel in library["novels"]:
        e = novel.get("elements", {})
        title = novel["title"]

        for q in e.get("quotes", []):
            if keyword in q.get("text", "").lower() or keyword in q.get("context", "").lower():
                results.append(("金句", title, q["text"]))

        for f in e.get("funny_scenes", []):
            if keyword in f.get("description", "").lower() or keyword in f.get("punchline", "").lower():
                results.append(("搞笑", title, f.get("title", "") + "：" + f.get("description", "")))

        for ev in e.get("events", []):
            if keyword in ev.get("description", "").lower():
                results.append(("事件", title, ev.get("title", "") + "：" + ev.get("description", "")))

        for c in e.get("characters", []):
            if keyword in c.get("name", "").lower() or keyword in c.get("description", "").lower():
                results.append(("人物", title, c["name"] + "：" + c.get("description", "")))

    if not results:
        print(f"未找到包含「{args.keyword}」的内容。")
        return

    print(f"\n找到 {len(results)} 条结果：\n{'─'*55}")
    for cat, title, content in results:
        print(f"[{cat}] 《{title}》")
        print(f"  {content[:120]}")


def cmd_generate(args):
    library = load_library()
    generate_story(
        library,
        characters=args.characters,
        era=args.era,
        style=args.style,
        story_type=args.type,
        output_file=args.output
    )


def cmd_generate_scene(args):
    library = load_library()
    generate_scene(
        library,
        scene_type=args.scene_type,
        characters=args.characters,
        location=args.location,
        output_file=args.output
    )


def cmd_generate_quote(args):
    library = load_library()
    generate_quote(
        library,
        style=args.style,
        quote_type=args.type,
        output_file=args.output
    )


def cmd_delete(args):
    library = load_library()
    before = len(library["novels"])
    library["novels"] = [n for n in library["novels"] if n["id"] != args.id]
    if len(library["novels"]) < before:
        save_library(library)
        print(f"已删除 id={args.id}")
    else:
        print(f"找不到 id={args.id}")


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="小说素材库 — 提取、管理、重新创作故事元素",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导入
  python novel_library.py add 红楼梦.txt --title "红楼梦"
  python novel_library.py add-text --title "我的故事"

  # 浏览
  python novel_library.py list
  python novel_library.py show a1b2c3d4
  python novel_library.py quotes --type 哲理
  python novel_library.py funny --type 误会
  python novel_library.py search 爱情

  # 生成（加 --output 保存到文件）
  python novel_library.py generate --style 悬疑 --era 民国 --output story.txt
  python novel_library.py generate-scene --scene-type 搞笑 --characters 林黛玉,贾宝玉
  python novel_library.py generate-scene --scene-type 虐心 --output scene.txt
  python novel_library.py generate-quote --type 讽刺 --style 鲁迅风
        """
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="从文件导入小说")
    p_add.add_argument("file")
    p_add.add_argument("--title")

    # add-text
    p_at = sub.add_parser("add-text", help="交互式输入文本")
    p_at.add_argument("--title")

    # list / show / delete
    sub.add_parser("list", help="列出所有作品")
    p_show = sub.add_parser("show", help="查看作品详细素材")
    p_show.add_argument("id")
    p_del = sub.add_parser("delete", help="删除作品")
    p_del.add_argument("id")

    # quotes
    p_q = sub.add_parser("quotes", help="浏览所有金句")
    p_q.add_argument("--type", help="过滤类型：感悟/讽刺/煽情/霸气/哲理/告白/诀别")

    # funny
    p_f = sub.add_parser("funny", help="浏览所有搞笑片段")
    p_f.add_argument("--type", help="过滤类型：误会/反差/吐槽/尬聊/意外/打脸/自嘲")

    # search
    p_s = sub.add_parser("search", help="跨作品关键词搜索")
    p_s.add_argument("keyword")

    # generate
    p_gen = sub.add_parser("generate", help="生成新故事大纲")
    p_gen.add_argument("--characters", help="指定人物，逗号分隔")
    p_gen.add_argument("--era", help="时代背景")
    p_gen.add_argument("--style", default="不限", help="故事风格")
    p_gen.add_argument("--type", default="小说", help="小说 或 剧本")
    p_gen.add_argument("--output", help="保存到文件")

    # generate-scene
    p_gs = sub.add_parser("generate-scene", help="生成特定类型场景")
    p_gs.add_argument("--scene-type", default="搞笑",
                      help="场景类型：搞笑/浪漫/虐心/悬疑/反转/励志（默认搞笑）")
    p_gs.add_argument("--characters", help="指定人物，逗号分隔")
    p_gs.add_argument("--location", help="指定地点")
    p_gs.add_argument("--output", help="保存到文件")

    # generate-quote
    p_gq = sub.add_parser("generate-quote", help="生成新金句")
    p_gq.add_argument("--type", default="感悟/哲理", help="金句类型：感悟/讽刺/煽情/霸气/哲理/告白")
    p_gq.add_argument("--style", default="不限", help="风格，如：鲁迅风/张爱玲风/网文爽文风")
    p_gq.add_argument("--output", help="保存到文件")

    args = parser.parse_args()

    if args.command in ("add", "add-text", "generate", "generate-scene", "generate-quote"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("错误：请设置环境变量 ANTHROPIC_API_KEY")
            print("  export ANTHROPIC_API_KEY=your_key_here")
            sys.exit(1)

    {
        "add": cmd_add,
        "add-text": cmd_add_text,
        "list": cmd_list,
        "show": cmd_show,
        "delete": cmd_delete,
        "quotes": cmd_quotes,
        "funny": cmd_funny,
        "search": cmd_search,
        "generate": cmd_generate,
        "generate-scene": cmd_generate_scene,
        "generate-quote": cmd_generate_quote,
    }[args.command](args)


if __name__ == "__main__":
    main()
