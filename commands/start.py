#!/usr/bin/env python3
"""
commands/start.py - /start 命令数据层

收集当日启动所需的全部上下文，输出给 prompts/start.md 使用：
  - 昨日学习摘要（memory/daily 或 calendar 昨日记录）
  - 今日已完成 + 待完成任务（含详情、截止日期）
  - 本周主题和薄弱点（供 AI 推荐最佳启动任务）

用法：
  python start.py
"""

import os
import json
import sys
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8")

COURSE_DIR = os.getcwd()
COURSE_DATA = os.path.join(COURSE_DIR, ".course")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_PATH = os.path.join(SKILL_DIR, "session.json")

sys.path.insert(0, SKILL_DIR)
from calendar import load_index as load_calendar_index


def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default if default is not None else {}


def build_task_lookup(plan):
    """从 semester_plan 建立 task_id → task 详情的索引。"""
    lookup = {}
    for week in plan.get("weeks", []):
        for task in week.get("tasks", []):
            tid = task.get("id")
            if tid:
                lookup[tid] = {
                    "content": task.get("content", ""),
                    "type": task.get("type", ""),
                    "deadline": task.get("deadline", ""),
                    "week": week.get("week"),
                    "theme": week.get("theme", ""),
                }
    return lookup


def find_current_week(plan, today):
    """找到今天所在的周。"""
    weeks = plan.get("weeks", [])
    for w in weeks:
        start = w.get("start_date", "")
        if not start:
            continue
        week_start = date.fromisoformat(start)
        week_end = week_start + timedelta(days=6)
        if week_start <= today <= week_end:
            return w
    # 找最近未来周
    for w in weeks:
        start = w.get("start_date", "")
        if start and date.fromisoformat(start) >= today:
            return w
    return weeks[-1] if weeks else None


def format_task(tid, detail, completed_set, today_str):
    """格式化单条任务行。"""
    if not detail:
        status = "✓" if tid in completed_set else "·"
        return f"  {status} {tid}  （详情未知）"

    icon = "✓" if tid in completed_set else "·"
    content = detail.get("content", "")
    ttype = detail.get("type", "")
    deadline = detail.get("deadline", "")

    line = f"  {icon} {tid}  {content}  [{ttype}]"
    if deadline:
        days_left = (date.fromisoformat(deadline) - date.fromisoformat(today_str)).days
        if days_left < 0:
            line += f"  ⚠ 已逾期({deadline})"
        elif days_left <= 3:
            line += f"  ⚡截止:{deadline}({days_left}天)"
        else:
            line += f"   截止:{deadline}"
    return line


def main():
    today = date.today()
    today_str = today.isoformat()
    yesterday_str = (today - timedelta(days=1)).isoformat()

    # 加载各数据源
    cal_index = load_calendar_index()
    plan = load_json(os.path.join(COURSE_DATA, "state", "semester_plan.json"), default={})
    config = load_json(os.path.join(COURSE_DATA, "config.json"), default={})
    session_all = load_json(SESSION_PATH, default={})
    session = session_all.get("courses", {}).get(COURSE_DIR, {})

    task_lookup = build_task_lookup(plan)
    current_week = find_current_week(plan, today)

    # 今日 calendar 数据
    today_cal = cal_index.get(today_str, {})
    planned_ids = today_cal.get("planned_tasks", [])
    completed_ids = set(today_cal.get("completed_tasks", []))

    # 昨日摘要
    yesterday_daily = load_json(
        os.path.join(SKILL_DIR, "memory", "daily", f"{yesterday_str}.json")
    )
    yesterday_cal = cal_index.get(yesterday_str, {})

    lines = []
    lines.append("START_CONTEXT:")
    lines.append(f"课程: {config.get('name', '未命名课程')}")
    lines.append(f"今日: {today_str}" + (
        f" | Week {current_week['week']}" if current_week else ""
    ))
    lines.append("")

    # 昨日摘要
    lines.append("== 昨日学习 ==")
    if yesterday_daily and yesterday_daily.get("courses"):
        for c in yesterday_daily["courses"]:
            if c.get("course_dir") == COURSE_DIR or not yesterday_daily["courses"][1:]:
                topics = c.get("topics", [])
                completed = c.get("completed_tasks", [])
                summary = c.get("summary", "")
                if summary:
                    lines.append(f"  摘要: {summary}")
                if topics:
                    lines.append(f"  话题: {', '.join(topics)}")
                if completed:
                    lines.append(f"  完成: {len(completed)} 项任务")
    elif yesterday_cal.get("completed_tasks"):
        done = yesterday_cal["completed_tasks"]
        lines.append(f"  完成了 {len(done)} 项任务: {', '.join(done)}")
    else:
        lines.append("  （无昨日记录）")
    lines.append("")

    # 今日计划
    lines.append("== 今日计划 ==")
    if not planned_ids:
        lines.append("  （calendar 中暂无今日计划，将从学期规划推断）")
        if current_week:
            pending = [
                t for t in current_week.get("tasks", [])
                if t.get("id") not in completed_ids
            ]
            for t in pending[:5]:
                lines.append(format_task(t["id"], task_lookup.get(t["id"]), completed_ids, today_str))
    else:
        pending = [tid for tid in planned_ids if tid not in completed_ids]
        done_today = [tid for tid in planned_ids if tid in completed_ids]

        if pending:
            lines.append(f"待完成 ({len(pending)}):")
            for tid in pending:
                lines.append(format_task(tid, task_lookup.get(tid), completed_ids, today_str))
        if done_today:
            lines.append(f"已完成 ({len(done_today)}):")
            for tid in done_today:
                lines.append(format_task(tid, task_lookup.get(tid), completed_ids, today_str))
    lines.append("")

    # 本周主题
    if current_week:
        lines.append("== 本周主题 ==")
        lines.append(f"  Week {current_week.get('week')}: {current_week.get('theme', '')}")
        topics = current_week.get("topics", [])
        if topics:
            lines.append(f"  涉及: {', '.join(topics)}")
        lines.append("")

    # 薄弱点（供 AI 推荐任务时参考）
    weak = session.get("weak_topics", [])
    if weak:
        lines.append("== 当前薄弱点 ==")
        lines.append(f"  {', '.join(weak)}")
        lines.append("")

    lines.append(f"COURSE_DIR: {COURSE_DIR}")
    lines.append(f"SKILL_DIR: {SKILL_DIR}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
