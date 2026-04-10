#!/usr/bin/env python3
"""
sync.py - 跨课程日摘要同步

职责：
  1. 读取每门课的 calendar/events.jsonl，生成课程级日摘要 → sync/daily/YYYY-MM-DD.json
  2. 聚合所有课程的日摘要      → SKILL_DIR/memory/daily/YYYY-MM-DD.json

用法：
  python sync.py                  同步今天
  python sync.py --date 2026-04-08  同步指定日期
  python sync.py --read 2026-04-08  只读取指定日期的跨课程摘要，不写入

调用时机（由 skill.md 决定）：
  - 每日对话结束时
  - 用户询问跨课程问题（如"这周学了什么"）时先同步再查询
"""

import os
import json
import sys
from datetime import date, datetime

sys.stdout.reconfigure(encoding="utf-8")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(SKILL_DIR, "registry.json")
SESSION_PATH = os.path.join(SKILL_DIR, "session.json")


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

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


def load_jsonlines(path):
    """读取 .jsonl 文件，返回事件列表。"""
    if not os.path.exists(path):
        return []
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


# ---------------------------------------------------------------------------
# 课程级日摘要：从 calendar/events.jsonl 提取某天的摘要
# ---------------------------------------------------------------------------

def summarize_course_day(course_dir, target_date):
    """
    读取 course_dir/.course/calendar/events.jsonl，
    提取 target_date 当天的事件，生成摘要字典。
    """
    course_data = os.path.join(course_dir, ".course")
    events_path = os.path.join(course_data, "calendar", "events.jsonl")
    all_events = load_jsonlines(events_path)

    day_events = [
        e for e in all_events
        if e.get("ts", "").startswith(target_date)
    ]

    if not day_events:
        return None

    config = load_json(os.path.join(course_data, "config.json"), default={})

    completed_tasks = [
        e.get("task_id", "") for e in day_events
        if e.get("type") == "task_complete"
    ]
    topics = list({
        e.get("topic", "") for e in day_events
        if e.get("topic")
    })
    mistakes = [
        e.get("topic", "") for e in day_events
        if e.get("type") == "mistake"
    ]
    time_minutes = sum(
        e.get("duration_minutes", 0) for e in day_events
        if e.get("type") == "session_end"
    )

    return {
        "date": target_date,
        "course": config.get("name", os.path.basename(course_dir)),
        "course_dir": course_dir,
        "completed_tasks": [t for t in completed_tasks if t],
        "topics": [t for t in topics if t],
        "mistakes": [t for t in mistakes if t],
        "time_minutes": time_minutes,
        "summary": "",   # 留空，由 skill.md 在对话结束时填写
    }


# ---------------------------------------------------------------------------
# 写入课程级日摘要
# ---------------------------------------------------------------------------

def write_course_day_summary(course_dir, target_date, summary):
    path = os.path.join(course_dir, ".course", "sync", "daily", f"{target_date}.json")
    save_json(path, summary)


# ---------------------------------------------------------------------------
# 聚合：所有课程 → skill 级跨课程日摘要
# ---------------------------------------------------------------------------

def aggregate_today_from_session():
    """
    今日聚合：直接从 SKILL_DIR/session.json 读取，无需遍历各课程目录。
    session.json 已包含所有课程的当日实时状态。
    """
    session = load_json(SESSION_PATH, default={})
    today = date.today().isoformat()

    if session.get("date") != today:
        return None

    course_summaries = []
    for course_dir, cdata in session.get("courses", {}).items():
        course_summaries.append({
            "name": cdata.get("name", os.path.basename(course_dir)),
            "course_dir": course_dir,
            "topics": cdata.get("topics", []),
            "completed_tasks": cdata.get("completed", []),
            "mistakes": cdata.get("weak_topics", []),
            "time_minutes": 0,   # 实时 session 不追踪时长，由 events.jsonl 补充
            "summary": cdata.get("summary", ""),
        })

    if not course_summaries:
        return None

    all_topics = [t for c in course_summaries for t in c["topics"]]
    aggregated = {
        "date": today,
        "courses": course_summaries,
        "total_time_minutes": 0,
        "all_topics": all_topics,
        "summary": "",
    }

    out_path = os.path.join(SKILL_DIR, "memory", "daily", f"{today}.json")
    save_json(out_path, aggregated)
    return aggregated


def aggregate_history_from_files(target_date):
    """
    历史日期聚合：从各课程的 .course/sync/daily/YYYY-MM-DD.json 读取。
    """
    registry = load_json(REGISTRY_PATH, default={"courses": []})
    courses = registry.get("courses", [])

    course_summaries = []
    for course in courses:
        course_dir = course.get("path", "")
        sync_path = os.path.join(course_dir, ".course", "sync", "daily", f"{target_date}.json")
        summary = load_json(sync_path)
        if summary:
            course_summaries.append({
                "name": summary.get("course", course.get("name", "")),
                "topics": summary.get("topics", []),
                "completed_tasks": summary.get("completed_tasks", []),
                "mistakes": summary.get("mistakes", []),
                "time_minutes": summary.get("time_minutes", 0),
                "summary": summary.get("summary", ""),
            })

    if not course_summaries:
        return None

    total_minutes = sum(c["time_minutes"] for c in course_summaries)
    all_topics = [t for c in course_summaries for t in c["topics"]]

    aggregated = {
        "date": target_date,
        "courses": course_summaries,
        "total_time_minutes": total_minutes,
        "all_topics": all_topics,
        "summary": "",
    }

    out_path = os.path.join(SKILL_DIR, "memory", "daily", f"{target_date}.json")
    save_json(out_path, aggregated)
    return aggregated


def aggregate_to_skill_memory(target_date):
    today = date.today().isoformat()
    if target_date == today:
        return aggregate_today_from_session()
    return aggregate_history_from_files(target_date)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def sync(target_date):
    registry = load_json(REGISTRY_PATH, default={"courses": []})
    courses = registry.get("courses", [])

    if not courses:
        print("SYNC_SKIP: registry.json 中没有注册的课程")
        return

    synced = []
    for course in courses:
        course_dir = course.get("path", "")
        if not os.path.exists(course_dir):
            continue
        summary = summarize_course_day(course_dir, target_date)
        if summary:
            write_course_day_summary(course_dir, target_date, summary)
            synced.append(course.get("name", course_dir))

    aggregated = aggregate_to_skill_memory(target_date)

    if aggregated:
        total = aggregated["total_time_minutes"]
        print(f"SYNC_OK: {target_date} | {len(synced)} 门课程 | 合计 {total} 分钟")
        print(f"涉及话题: {', '.join(aggregated['all_topics']) or '无'}")
    else:
        print(f"SYNC_SKIP: {target_date} 无学习记录")


def read_day(target_date):
    """只读取跨课程日摘要，不触发同步写入。"""
    path = os.path.join(SKILL_DIR, "memory", "daily", f"{target_date}.json")
    data = load_json(path)
    if not data:
        print(f"NO_DATA: {target_date} 无跨课程摘要，可运行同步生成")
        return
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    args = sys.argv[1:]
    target_date = date.today().isoformat()

    if "--date" in args:
        idx = args.index("--date")
        if idx + 1 < len(args):
            target_date = args[idx + 1]

    if "--read" in args:
        idx = args.index("--read")
        read_date = args[idx + 1] if idx + 1 < len(args) else target_date
        read_day(read_date)
    else:
        sync(target_date)


if __name__ == "__main__":
    main()
