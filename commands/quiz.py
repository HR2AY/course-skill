#!/usr/bin/env python3
"""
commands/quiz.py - /quiz 命令数据层

职责：
  从 .course/processed/knowledge_base/ 加载指定范围的知识点，
  输出结构化上下文供 skill.md 出题流程使用。

用法：
  python quiz.py --list                    列出所有可出题的章节和知识点
  python quiz.py --chapter "信号基础"      加载指定章节全部知识点
  python quiz.py --topic "傅里叶变换"     加载单个知识点（精确匹配）
  python quiz.py --weak                   加载所有 weak=true 的知识点
"""

import os
import json
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

COURSE_DIR = os.getcwd()
COURSE_DATA = os.path.join(COURSE_DIR, ".course")
KB_DIR = os.path.join(COURSE_DATA, "processed", "knowledge_base")


def load_all_topics():
    """加载 knowledge_base/ 下所有 JSON 文件，返回列表。"""
    if not os.path.exists(KB_DIR):
        return []
    topics = []
    for fname in sorted(os.listdir(KB_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(KB_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "topic" in data:
                topics.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return topics


def infer_question_type(entry):
    """
    根据知识点内容推断适合的题型：
      math   - 含公式/数值，适合计算题
      memory - 概念定义类，适合选择/判断题
    """
    signals = [
        entry.get("d", ""),
        " ".join(entry.get("e", [])),
        entry.get("t", ""),
    ]
    math_hints = ["=", "∫", "∑", "∂", "公式", "计算", "推导", "求", "证明",
                  "Hz", "dB", "rad", "变换", "矩阵", "导数", "积分"]
    text = " ".join(signals)
    if any(h in text for h in math_hints):
        return "math"
    return "memory"


def format_entry(index, entry):
    """将单个知识点格式化为 LLM 可读的文本块。"""
    lines = []
    lines.append(f"[{index}] {entry.get('topic', '（无标题）')}")
    if entry.get("d"):
        lines.append(f"  定义: {entry['d']}")
    if entry.get("e"):
        examples = entry["e"] if isinstance(entry["e"], list) else [entry["e"]]
        lines.append(f"  示例: {' / '.join(str(e) for e in examples)}")
    if entry.get("t"):
        lines.append(f"  应用: {entry['t']}")
    if entry.get("v"):
        lines.append(f"  验证题: {entry['v']}")
    tags = entry.get("tags", [])
    if tags:
        lines.append(f"  章节: {', '.join(tags)}")
    lines.append(f"  题型建议: {'计算题（数学型）' if infer_question_type(entry) == 'math' else '选择/判断题（记忆型）'}")
    if entry.get("weak"):
        lines.append("  ★ 标记为薄弱点")
    return "\n".join(lines)


def cmd_list(topics):
    """列出所有章节及其知识点，供用户/LLM 选择范围。"""
    if not topics:
        print("KB_EMPTY: knowledge_base 为空，请先上传并处理课件。")
        return

    # 按 tags 分组（一个知识点可能属于多个章节）
    chapter_map = defaultdict(list)
    no_tag = []
    for t in topics:
        tags = t.get("tags", [])
        if tags:
            for tag in tags:
                chapter_map[tag].append(t["topic"])
        else:
            no_tag.append(t["topic"])

    print("QUIZ_LIST:")
    print(f"共 {len(topics)} 个知识点\n")

    for chapter, topic_names in sorted(chapter_map.items()):
        unique = list(dict.fromkeys(topic_names))  # 去重保序
        print(f"  {chapter} ({len(unique)} 个知识点)")
        for name in unique:
            print(f"    · {name}")

    if no_tag:
        print(f"\n  （未分章节，{len(no_tag)} 个）")
        for name in no_tag:
            print(f"    · {name}")

    print("\n使用 --chapter <章节名> 或 --topic <知识点名> 指定出题范围。")


def cmd_chapter(topics, chapter):
    """加载指定章节的所有知识点。"""
    matched = [t for t in topics if chapter in t.get("tags", [])]

    if not matched:
        # 模糊提示：列出含有部分匹配的章节
        candidates = set()
        for t in topics:
            for tag in t.get("tags", []):
                if chapter in tag or tag in chapter:
                    candidates.add(tag)
        if candidates:
            print(f"CHAPTER_NOT_FOUND: 未找到章节 "{chapter}"")
            print(f"相近章节: {', '.join(sorted(candidates))}")
        else:
            print(f"CHAPTER_NOT_FOUND: 未找到章节 "{chapter}"，请用 --list 查看可用章节。")
        sys.exit(1)

    print(f"QUIZ_CONTEXT:")
    print(f"章节: {chapter}")
    print(f"共 {len(matched)} 个知识点\n")
    for i, entry in enumerate(matched, 1):
        print(format_entry(i, entry))
        print()


def cmd_topic(topics, topic_name):
    """加载单个知识点（精确匹配优先，模糊匹配兜底）。"""
    # 精确匹配
    matched = [t for t in topics if t.get("topic") == topic_name]

    # 模糊匹配
    if not matched:
        matched = [t for t in topics if topic_name in t.get("topic", "")]

    if not matched:
        print(f"TOPIC_NOT_FOUND: 未找到知识点 "{topic_name}"，请用 --list 查看可用知识点。")
        sys.exit(1)

    print(f"QUIZ_CONTEXT:")
    print(f"知识点: {topic_name}")
    print(f"共 {len(matched)} 条\n")
    for i, entry in enumerate(matched, 1):
        print(format_entry(i, entry))
        print()


def cmd_weak(topics):
    """加载所有薄弱点知识点。"""
    matched = [t for t in topics if t.get("weak")]
    if not matched:
        print("NO_WEAK: 当前没有标记为薄弱点的知识点。")
        return

    print(f"QUIZ_CONTEXT:")
    print(f"范围: 薄弱点复习")
    print(f"共 {len(matched)} 个知识点\n")
    for i, entry in enumerate(matched, 1):
        print(format_entry(i, entry))
        print()


def main():
    args = sys.argv[1:]
    topics = load_all_topics()

    if not args or "--list" in args:
        cmd_list(topics)
        return

    if "--chapter" in args:
        idx = args.index("--chapter")
        if idx + 1 >= len(args):
            print("用法: python quiz.py --chapter <章节名>")
            sys.exit(1)
        cmd_chapter(topics, args[idx + 1])
        return

    if "--topic" in args:
        idx = args.index("--topic")
        if idx + 1 >= len(args):
            print("用法: python quiz.py --topic <知识点名>")
            sys.exit(1)
        cmd_topic(topics, args[idx + 1])
        return

    if "--weak" in args:
        cmd_weak(topics)
        return

    print("用法: python quiz.py [--list | --chapter <名> | --topic <名> | --weak]")
    sys.exit(1)


if __name__ == "__main__":
    main()
