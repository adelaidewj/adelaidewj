#!/usr/bin/env python3
"""
小说素材库 Novel Library Tool
==============================
从小说/故事中提取人物、时代、地点、关系、事件，
存入本地素材库，并可重新组合生成新小说或剧本大纲。

用法:
  python novel_library.py add <文件路径> --title "小说名"
  python novel_library.py add-text --title "小说名"     (交互输入)
  python novel_library.py list
  python novel_library.py show <id>
  python novel_library.py generate
  python novel_library.py generate --characters 林黛玉,贾宝玉 --era 现代 --style 悬疑
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
# 提取素材
# ─────────────────────────────────────────────

EXTRACT_PROMPT = """请仔细分析以下小说/故事文本，提取关键素材，并严格按照 JSON 格式返回，不要加任何额外说明。

JSON 格式如下：
{{
  "characters": [
    {{
      "name": "人物姓名",
      "description": "人物简介",
      "traits": ["性格特征1", "性格特征2"],
      "role": "主角/配角/反派 等"
    }}
  ],
  "era": "故事所处的时代，如：民国、现代、架空魔幻、宋朝 等",
  "locations": ["地点1", "地点2"],
  "relationships": [
    {{
      "from": "人物A",
      "to": "人物B",
      "type": "关系类型，如：父子、情侣、对立、盟友 等",
      "description": "关系简述"
    }}
  ],
  "events": [
    {{
      "title": "事件标题",
      "description": "事件描述",
      "characters": ["相关人物"],
      "location": "发生地点",
      "significance": "对故事的意义"
    }}
  ],
  "themes": ["主题1", "主题2"],
  "tone": "故事基调，如：悲剧、喜剧、悬疑、浪漫 等"
}}

小说文本：
{text}
"""


def extract_elements(text: str, title: str) -> dict:
    """调用 Claude API 从文本中提取故事素材"""
    client = anthropic.Anthropic()

    print(f"  正在分析「{title}」的故事素材...")

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": EXTRACT_PROMPT.format(text=text[:8000])  # 限制长度
            }
        ]
    )

    raw = message.content[0].text.strip()

    # 清理 markdown 代码块
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    elements = json.loads(raw)
    return elements


# ─────────────────────────────────────────────
# 生成新故事
# ─────────────────────────────────────────────

GENERATE_PROMPT = """你是一位才华横溢的小说家。请根据以下从素材库中挑选的元素，创作一篇新故事的详细大纲。

【可用素材】
{elements_json}

【创作要求】
- 时代背景：{era}
- 指定人物：{characters}
- 指定地点：{locations}
- 故事风格：{style}
- 类型：{story_type}

请输出：
1. 故事标题
2. 故事简介（200字以内）
3. 主要人物设定（可对原有人物进行改编）
4. 三幕式故事大纲：
   - 第一幕（开端）
   - 第二幕（发展与冲突）
   - 第三幕（高潮与结局）
5. 核心冲突
6. 主题与立意

可以自由发挥创意，不必完全照搬原素材，重点是让这些元素产生新的化学反应。
"""


def generate_story(library: dict, characters: str = None, era: str = None,
                   locations: str = None, style: str = "不限", story_type: str = "小说"):
    """从素材库中抽取元素，生成新故事大纲"""

    if not library["novels"]:
        print("素材库为空，请先用 add 命令导入小说。")
        return

    # 汇总所有素材
    all_characters = []
    all_locations = []
    all_events = []
    all_relationships = []

    for novel in library["novels"]:
        e = novel.get("elements", {})
        all_characters.extend(e.get("characters", []))
        all_locations.extend(e.get("locations", []))
        all_events.extend(e.get("events", []))
        all_relationships.extend(e.get("relationships", []))

    # 过滤指定人物
    if characters:
        names = [c.strip() for c in characters.split(",")]
        filtered_chars = [c for c in all_characters if c["name"] in names]
        if not filtered_chars:
            filtered_chars = all_characters[:4]
    else:
        filtered_chars = all_characters[:5]

    selected_elements = {
        "characters": filtered_chars,
        "events": all_events[:6],
        "relationships": all_relationships[:4],
        "locations": all_locations[:6]
    }

    client = anthropic.Anthropic()

    print("  正在创作新故事大纲...\n")

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=3000,
        messages=[
            {
                "role": "user",
                "content": GENERATE_PROMPT.format(
                    elements_json=json.dumps(selected_elements, ensure_ascii=False, indent=2),
                    era=era or "自由选择",
                    characters=characters or "自由选择",
                    locations=locations or "自由选择",
                    style=style,
                    story_type=story_type
                )
            }
        ]
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print("\n")


# ─────────────────────────────────────────────
# CLI 命令
# ─────────────────────────────────────────────

def cmd_add(args):
    """从文件导入小说并提取素材"""
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
        "id": novel_id,
        "title": title,
        "added_at": datetime.now().isoformat(),
        "text_preview": text[:200] + "..." if len(text) > 200 else text,
        "elements": elements
    })
    save_library(library)

    print(f"\n✓ 已添加「{title}」(id: {novel_id})")
    _print_elements_summary(elements)


def cmd_add_text(args):
    """交互式输入故事文本"""
    title = args.title or input("故事标题：").strip() or "未命名"
    print("请输入故事文本（输入完成后按 Ctrl+D 或 Ctrl+Z 结束）：")
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
        "id": novel_id,
        "title": title,
        "added_at": datetime.now().isoformat(),
        "text_preview": text[:200] + "..." if len(text) > 200 else text,
        "elements": elements
    })
    save_library(library)

    print(f"\n✓ 已添加「{title}」(id: {novel_id})")
    _print_elements_summary(elements)


def cmd_list(args):
    """列出素材库中的所有小说"""
    library = load_library()
    novels = library["novels"]

    if not novels:
        print("素材库为空。使用 add 命令导入小说。")
        return

    print(f"\n{'ID':<10} {'标题':<20} {'人物数':<6} {'地点数':<6} {'事件数':<6} {'添加时间'}")
    print("─" * 70)
    for n in novels:
        e = n.get("elements", {})
        print(
            f"{n['id']:<10} "
            f"{n['title'][:18]:<20} "
            f"{len(e.get('characters', [])):<6} "
            f"{len(e.get('locations', [])):<6} "
            f"{len(e.get('events', [])):<6} "
            f"{n.get('added_at', '')[:10]}"
        )
    print(f"\n共 {len(novels)} 部作品")


def cmd_show(args):
    """显示某部小说的详细素材"""
    library = load_library()
    novel = next((n for n in library["novels"] if n["id"] == args.id), None)

    if not novel:
        print(f"找不到 id 为 {args.id} 的作品。")
        return

    e = novel["elements"]
    print(f"\n{'═' * 50}")
    print(f"  {novel['title']}")
    print(f"{'═' * 50}")
    print(f"时代：{e.get('era', '未知')}")
    print(f"基调：{e.get('tone', '未知')}")
    print(f"主题：{', '.join(e.get('themes', []))}")

    print("\n【人物】")
    for c in e.get("characters", []):
        traits = "、".join(c.get("traits", []))
        print(f"  {c['name']} [{c.get('role', '')}] — {c.get('description', '')}")
        if traits:
            print(f"    性格：{traits}")

    print("\n【地点】")
    for loc in e.get("locations", []):
        print(f"  · {loc}")

    print("\n【人物关系】")
    for r in e.get("relationships", []):
        print(f"  {r['from']} ─{r['type']}→ {r['to']}：{r.get('description', '')}")

    print("\n【关键事件】")
    for i, ev in enumerate(e.get("events", []), 1):
        chars = "、".join(ev.get("characters", []))
        print(f"  {i}. 【{ev['title']}】{ev.get('description', '')}")
        print(f"     人物：{chars}  地点：{ev.get('location', '')}")


def cmd_generate(args):
    """从素材库生成新故事大纲"""
    library = load_library()
    generate_story(
        library,
        characters=args.characters,
        era=args.era,
        locations=args.locations,
        style=args.style,
        story_type=args.type
    )


def cmd_delete(args):
    """从素材库删除一部作品"""
    library = load_library()
    before = len(library["novels"])
    library["novels"] = [n for n in library["novels"] if n["id"] != args.id]
    if len(library["novels"]) < before:
        save_library(library)
        print(f"已删除 id={args.id} 的作品。")
    else:
        print(f"找不到 id={args.id} 的作品。")


def _print_elements_summary(elements: dict):
    print(f"\n  时代：{elements.get('era', '未知')}")
    print(f"  基调：{elements.get('tone', '未知')}")
    chars = [c["name"] for c in elements.get("characters", [])]
    print(f"  人物：{', '.join(chars)}")
    print(f"  地点：{', '.join(elements.get('locations', []))}")
    print(f"  事件：{len(elements.get('events', []))} 个")


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="小说素材库 — 提取故事元素，重新组合创作新故事",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python novel_library.py add story.txt --title "红楼梦节选"
  python novel_library.py add-text --title "我的故事"
  python novel_library.py list
  python novel_library.py show a1b2c3d4
  python novel_library.py generate
  python novel_library.py generate --characters 林黛玉,贾宝玉 --era 现代都市 --style 悬疑
  python novel_library.py generate --type 剧本
        """
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="从文件导入小说并提取素材")
    p_add.add_argument("file", help="小说文件路径（.txt）")
    p_add.add_argument("--title", help="作品标题（默认使用文件名）")

    # add-text
    p_add_text = sub.add_parser("add-text", help="交互式输入故事文本")
    p_add_text.add_argument("--title", help="作品标题")

    # list
    sub.add_parser("list", help="列出素材库中的所有作品")

    # show
    p_show = sub.add_parser("show", help="显示某部作品的详细素材")
    p_show.add_argument("id", help="作品 ID")

    # generate
    p_gen = sub.add_parser("generate", help="从素材库生成新故事大纲")
    p_gen.add_argument("--characters", help="指定人物，逗号分隔，如：林黛玉,贾宝玉")
    p_gen.add_argument("--era", help="指定时代，如：现代都市、民国、架空")
    p_gen.add_argument("--locations", help="指定地点，逗号分隔")
    p_gen.add_argument("--style", default="不限", help="故事风格，如：悬疑、浪漫、惊悚（默认不限）")
    p_gen.add_argument("--type", default="小说", help="创作类型：小说 或 剧本（默认小说）")

    # delete
    p_del = sub.add_parser("delete", help="从素材库删除一部作品")
    p_del.add_argument("id", help="作品 ID")

    args = parser.parse_args()

    # 检查 API Key
    if args.command in ("add", "add-text", "generate"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("错误：请设置环境变量 ANTHROPIC_API_KEY")
            print("  export ANTHROPIC_API_KEY=your_key_here")
            sys.exit(1)

    cmd_map = {
        "add": cmd_add,
        "add-text": cmd_add_text,
        "list": cmd_list,
        "show": cmd_show,
        "generate": cmd_generate,
        "delete": cmd_delete,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
