#!/usr/bin/env python3
"""
commands/review.py - /review 命令数据层

职责：
  1. 列出错题记录（支持时间范围、章节、跨课程筛选）
  2. bump：将指定错题的 call_count +1，更新 last_reviewed

错题文件由 AI 直接写入 .course/memory/mistakes/{YYYYMMDD}_{topic}.json，
本脚本只负责读取、筛选和更新。

用法：
  python review.py --list                              当前课程全部错题
  python review.py --list --since 2026-04-01           时间过滤（起）
  python review.py --list --until 2026-04-10           时间过滤（止）
  python review.py --list --chapter "第三章"           按章节过滤
  python review.py --list --sort-by-count              按错误次数降序
  python review.py --list --all-courses                跨所有已注册课程
  python review.py --bump {mistake_filepath}           call_count +1
"""

import os
import json
import sys
from datetime import date, datetime

sys.stdout.reconfigure(encoding="utf-8")

COURSE_DIR = os.getcwd()
COURSE_DATA = os.path.join(COURSE_DIR, ".course")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(SKILL_DIR, "registry.json")


def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default if default is not None else {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_mistakes_from_dir(mistakes_dir, since=None, until=None, chapter=None):
    """从指定 mistakes/ 目录加载并过滤错题列表。"""
    if not os.path.exists(mistakes_dir):
        return []

    results = []
    for fname in sorted(os.listdir(mistakes_dir), reverse=True):  # 最新的排前面
        if not fname.endswith(".json"):
            continue
        path = os.path.join(mistakes_dir, fname)
        try:
            data = load_json(path)
            if not data or "topic" not in data:
                continue

            created = data.get("created_at", "")[:10]  # YYYY-MM-DD

            if since and created < since:
                continue
            if until and created > until:
                continue
            if chapter:
                entry_chapter = data.get("chapter", "")
                if chapter not in entry_chapter and entry_chapter not in chapter:
                    continue

            data["_file"] = path
            results.append(data)
        except OSError:
            pass

    return results


def format_mistake(index, entry, show_course=False):
    """将错题条目格式化为 LLM 可读的文本块。"""
    lines = []
    header = f"[{index}] {entry.get('topic', '（无标题）')}"
    if entry.get("chapter"):
        header += f" | {entry['chapter']}"
    if show_course and entry.get("course_name"):
        header += f" | {entry['course_name']}"
    header += f" | 错误 {entry.get('call_count', 1)} 次"
    if entry.get("last_reviewed"):
        header += f" | 最近: {entry['last_reviewed'][:10]}"
    lines.append(header)

    if entry.get("question"):
        lines.append(f"  题目: {entry['question']}")
    if entry.get("options"):
        opts = entry["options"]
        if isinstance(opts, dict):
            for k, v in opts.items():
                lines.append(f"    {k}. {v}")
    if entry.get("user_answer"):
        lines.append(f"  用户答案: {entry['user_answer']}")
    if entry.get("correct_answer"):
        lines.append(f"  正确答案: {entry['correct_answer']}")
    if entry.get("explanation"):
        lines.append(f"  解析: {entry['explanation']}")
    lines.append(f"  文件: {entry['_file']}")
    return "\n".join(lines)


def cmd_list(args):
    since = None
    until = None
    chapter = None
    all_courses = "--all-courses" in args
    sort_by_count = "--sort-by-count" in args

    if "--since" in args:
        idx = args.index("--since")
        since = args[idx + 1] if idx + 1 < len(args) else None
    if "--until" in args:
        idx = args.index("--until")
        until = args[idx + 1] if idx + 1 < len(args) else None
    if "--chapter" in args:
        idx = args.index("--chapter")
        chapter = args[idx + 1] if idx + 1 < len(args) else None

    all_mistakes = []

    if all_courses:
        registry = load_json(REGISTRY_PATH, default={"courses": []})
        courses = registry.get("courses", [])
        for course in courses:
            course_dir = course.get("path", "")
            mistakes_dir = os.path.join(course_dir, ".course", "memory", "mistakes")
            entries = load_mistakes_from_dir(mistakes_dir, since, until, chapter)
            for e in entries:
                e["course_name"] = course.get("name", os.path.basename(course_dir))
                e["course_dir"] = course_dir
            all_mistakes.extend(entries)
    else:
        mistakes_dir = os.path.join(COURSE_DATA, "memory", "mistakes")
        all_mistakes = load_mistakes_from_dir(mistakes_dir, since, until, chapter)

    if not all_mistakes:
        filters = []
        if since:
            filters.append(f"since={since}")
        if until:
            filters.append(f"until={until}")
        if chapter:
            filters.append(f"chapter={chapter}")
        filter_str = f"（{', '.join(filters)}）" if filters else ""
        print(f"NO_MISTAKES: 没有符合条件的错题记录{filter_str}。")
        return

    if sort_by_count:
        all_mistakes.sort(key=lambda e: e.get("call_count", 1), reverse=True)

    print("MISTAKES_LIST:")
    scope = "跨课程" if all_courses else "当前课程"
    print(f"共 {len(all_mistakes)} 条错题（{scope}）\n")
    for i, entry in enumerate(all_mistakes, 1):
        print(format_mistake(i, entry, show_course=all_courses))
        print()


def cmd_bump(mistake_filepath):
    """call_count +1，更新 last_reviewed。"""
    if not os.path.exists(mistake_filepath):
        print(f"BUMP_ERROR: 文件不存在: {mistake_filepath}")
        sys.exit(1)

    data = load_json(mistake_filepath)
    data["call_count"] = data.get("call_count", 1) + 1
    data["last_reviewed"] = datetime.now().isoformat(timespec="minutes")
    save_json(mistake_filepath, data)
    print(f"BUMP_OK: {data['topic']} | call_count={data['call_count']}")


def main():
    args = sys.argv[1:]

    if not args or "--list" in args:
        cmd_list(args)
        return

    if "--bump" in args:
        idx = args.index("--bump")
        if idx + 1 >= len(args):
            print("用法: python review.py --bump <mistake_filepath>")
            sys.exit(1)
        cmd_bump(args[idx + 1])
        return

    print("用法: python review.py [--list [...] | --bump <filepath>]")
    sys.exit(1)


if __name__ == "__main__":
    main()
