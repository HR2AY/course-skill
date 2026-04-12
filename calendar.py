#!/usr/bin/env python3
"""
calendar.py - 日历系统：连接计划线与历史线的时间索引

这不是展示组件，而是 AI 查询/操作课程时间线的库。
所有与时间相关的活动（查进度、改计划、回顾、出题定位）都经过这里。

数据文件（在 COURSE_DIR 下）：
  calendar/index.json   — 按日期的稀疏索引（只有有事件的日期才有条目）
  calendar/events.jsonl  — 只追加的事件流（完整历史）

用法：
  python calendar.py get_day 2026-04-09
  python calendar.py get_range 2026-04-07 2026-04-13
  python calendar.py get_topic 傅里叶变换
  python calendar.py get_overdue
  python calendar.py log '{"type":"task_complete","task_id":"t001","topic":"傅里叶变换"}'
  python calendar.py reschedule t002 2026-04-12
  python calendar.py plan_day 2026-04-10 '["t003","t004"]'
"""

import os
import json
import sys
from datetime import date, datetime

sys.stdout.reconfigure(encoding="utf-8")

COURSE_DIR = os.getcwd()
COURSE_DATA = os.path.join(COURSE_DIR, ".course")
INDEX_PATH = os.path.join(COURSE_DATA, "calendar", "index.json")
EVENTS_PATH = os.path.join(COURSE_DATA, "calendar", "events.jsonl")


# ---------------------------------------------------------------------------
# 底层读写
# ---------------------------------------------------------------------------

def load_index():
    if not os.path.exists(INDEX_PATH):
        return {}
    with open(INDEX_PATH, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_index(index):
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def append_event(event):
    """追加一条事件到 events.jsonl，自动补时间戳。"""
    if "ts" not in event:
        event["ts"] = datetime.now().isoformat(timespec="minutes")
    os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
    with open(EVENTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_events():
    if not os.path.exists(EVENTS_PATH):
        return []
    events = []
    with open(EVENTS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


def ensure_day(index, d):
    """确保 index 中有某天的条目。"""
    if d not in index:
        index[d] = {
            "planned_tasks": [],
            "completed_tasks": [],
            "topics": [],
            "refs": {"mistakes": [], "insights": []},
        }
    return index[d]


# ---------------------------------------------------------------------------
# 查询接口
# ---------------------------------------------------------------------------

def get_day(target_date):
    """返回某天的计划 + 实际。"""
    index = load_index()
    day = index.get(target_date, {
        "planned_tasks": [],
        "completed_tasks": [],
        "topics": [],
        "refs": {"mistakes": [], "insights": []},
    })
    day["date"] = target_date
    # 计算完成率
    planned = len(day.get("planned_tasks", []))
    done = len(day.get("completed_tasks", []))
    day["progress"] = f"{done}/{planned}" if planned > 0 else "无计划"
    return day


def get_range(start_date, end_date):
    """返回日期范围内所有有记录的天。"""
    index = load_index()
    result = {}
    for d, data in index.items():
        if start_date <= d <= end_date:
            data["date"] = d
            result[d] = data
    return result


def get_topic_history(topic):
    """查找某知识点在哪些日期出现过，返回按时间排序的列表。"""
    index = load_index()
    result = []
    for d, data in sorted(index.items()):
        if topic in data.get("topics", []):
            result.append({
                "date": d,
                "was_planned": topic in [t for t in data.get("planned_tasks", [])],
                "had_mistake": any(
                    topic in ref for ref in data.get("refs", {}).get("mistakes", [])
                ),
            })
    return result


def get_overdue():
    """返回所有过期未完成的任务：计划日期 < 今天 且不在 completed_tasks 中。"""
    today = date.today().isoformat()
    index = load_index()
    overdue = []
    for d, data in sorted(index.items()):
        if d >= today:
            continue
        planned = set(data.get("planned_tasks", []))
        completed = set(data.get("completed_tasks", []))
        for task_id in planned - completed:
            overdue.append({"task_id": task_id, "original_date": d})
    return overdue


# ---------------------------------------------------------------------------
# 写入接口
# ---------------------------------------------------------------------------

def log_event(event):
    """
    记录一次事件。同时更新 index.json 和追加 events.jsonl。

    事件类型：
      session_start  — 开始学习，含 topics
      session_end    — 结束学习，含 duration_minutes
      task_complete  — 完成任务，含 task_id, topic (可选)
      mistake        — 答题出错，含 topic
      insight        — 重要理解，含 topic, content
      reschedule     — 改计划，含 task_id, from, to
    """
    append_event(event)

    ts = event.get("ts", datetime.now().isoformat(timespec="minutes"))
    event_date = ts[:10]  # YYYY-MM-DD
    event_type = event.get("type", "")

    index = load_index()
    day = ensure_day(index, event_date)

    # 根据事件类型更新 index
    topic = event.get("topic", "")
    if topic and topic not in day["topics"]:
        day["topics"].append(topic)

    if event_type == "task_complete":
        task_id = event.get("task_id", "")
        if task_id and task_id not in day["completed_tasks"]:
            day["completed_tasks"].append(task_id)

    elif event_type == "mistake":
        ref = f".course/memory/mistakes/{event_date}_{topic}.json"
        if ref not in day["refs"]["mistakes"]:
            day["refs"]["mistakes"].append(ref)

    elif event_type == "insight":
        ref = f".course/memory/insights/{event_date}_{topic}.json"
        if ref not in day["refs"]["insights"]:
            day["refs"]["insights"].append(ref)

    elif event_type == "reschedule":
        # 从原日期移除，加到新日期
        task_id = event.get("task_id", "")
        from_date = event.get("from", "")
        to_date = event.get("to", "")
        if from_date and from_date in index:
            planned = index[from_date].get("planned_tasks", [])
            if task_id in planned:
                planned.remove(task_id)
        if to_date:
            to_day = ensure_day(index, to_date)
            if task_id not in to_day["planned_tasks"]:
                to_day["planned_tasks"].append(task_id)

    save_index(index)


def plan_day(target_date, task_ids):
    """为某天设置计划任务列表（覆盖已有计划）。"""
    index = load_index()
    day = ensure_day(index, target_date)
    day["planned_tasks"] = task_ids
    save_index(index)

    append_event({
        "ts": datetime.now().isoformat(timespec="minutes"),
        "type": "plan_set",
        "date": target_date,
        "tasks": task_ids,
    })


def migrate_ids(id_map):
    """
    将 calendar/index.json 中所有 task ID 按 id_map 批量替换。
    id_map: {old_id: new_id}，new_id 为 None 表示从 calendar 中移除该 ID。
    影响字段：planned_tasks、completed_tasks。
    返回实际替换的次数。
    """
    index = load_index()
    changed = 0
    for day_data in index.values():
        for field in ("planned_tasks", "completed_tasks"):
            old_list = day_data.get(field, [])
            new_list = []
            for tid in old_list:
                if tid in id_map:
                    new_id = id_map[tid]
                    if new_id is not None:
                        new_list.append(new_id)
                    changed += 1
                else:
                    new_list.append(tid)
            day_data[field] = new_list
    save_index(index)
    return changed


def reschedule(task_id, new_date):
    """
    找到 task_id 所在的最早日期，移到 new_date。
    """
    index = load_index()
    from_date = None
    for d in sorted(index.keys()):
        if task_id in index[d].get("planned_tasks", []):
            from_date = d
            break

    if not from_date:
        return {"error": f"task {task_id} not found in any planned day"}

    log_event({
        "type": "reschedule",
        "task_id": task_id,
        "from": from_date,
        "to": new_date,
    })
    return {"ok": True, "moved": task_id, "from": from_date, "to": new_date}


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def output(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python calendar.py <command> [args...]")
        print("命令: get_day, get_range, get_topic, get_overdue, log, reschedule, plan_day, migrate_ids")
        sys.exit(1)

    cmd = args[0]

    if cmd == "get_day":
        d = args[1] if len(args) > 1 else date.today().isoformat()
        output(get_day(d))

    elif cmd == "get_range":
        if len(args) < 3:
            print("用法: python calendar.py get_range <start> <end>")
            sys.exit(1)
        output(get_range(args[1], args[2]))

    elif cmd == "get_topic":
        if len(args) < 2:
            print("用法: python calendar.py get_topic <topic_name>")
            sys.exit(1)
        output(get_topic_history(args[1]))

    elif cmd == "get_overdue":
        output(get_overdue())

    elif cmd == "log":
        if len(args) < 2:
            print("用法: python calendar.py log '<json_event>'")
            sys.exit(1)
        event = json.loads(args[1])
        log_event(event)
        print("EVENT_LOGGED")

    elif cmd == "reschedule":
        if len(args) < 3:
            print("用法: python calendar.py reschedule <task_id> <new_date>")
            sys.exit(1)
        output(reschedule(args[1], args[2]))

    elif cmd == "plan_day":
        if len(args) < 3:
            print("用法: python calendar.py plan_day <date> '<json_task_ids>'")
            sys.exit(1)
        task_ids = json.loads(args[2])
        plan_day(args[1], task_ids)
        print("PLAN_SET")

    elif cmd == "migrate_ids":
        if len(args) < 2:
            print("用法: python calendar.py migrate_ids '{\"old_id\": \"new_id\", ...}'")
            print("      new_id 为 null 表示从 calendar 中删除该 ID")
            sys.exit(1)
        id_map = json.loads(args[1])
        n = migrate_ids(id_map)
        print(f"MIGRATE_OK: 替换了 {n} 处 task ID 引用")

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
