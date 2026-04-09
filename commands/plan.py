#!/usr/bin/env python3
"""
commands/plan.py - /plan 命令：展示学期规划视图

读取 state/semester_plan.json + calendar/index.json，输出：
  1. 学期总览（进度条）
  2. 本周详情（任务状态）
  3. 近期截止日期
  4. 逾期任务

用法：
  python plan.py                   显示完整规划视图
  python plan.py --week 6          只显示指定周
  python plan.py --deadlines       只显示截止日期
"""

import os
import json
import sys
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8")

COURSE_DIR = os.getcwd()
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


def progress_bar(done, total, width=20):
    if total <= 0:
        return "[" + "░" * width + "] --"
    filled = int(done / total * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(done / total * 100)
    return f"[{bar}] {pct}%"


def find_current_week(weeks, today):
    """根据 start_date 找到当前属于哪一周。"""
    for w in weeks:
        start = w.get("start_date", "")
        if not start:
            continue
        week_start = date.fromisoformat(start)
        week_end = week_start + timedelta(days=6)
        if week_start <= today <= week_end:
            return w
    # 如果没有精确匹配，找最近的未来周
    for w in weeks:
        start = w.get("start_date", "")
        if start and date.fromisoformat(start) >= today:
            return w
    # 都过了就返回最后一周
    return weeks[-1] if weeks else None


def get_completed_tasks(cal_index):
    """从日历索引中收集所有已完成的 task_id。"""
    completed = set()
    for day_data in cal_index.values():
        for tid in day_data.get("completed_tasks", []):
            completed.add(tid)
    return completed


def get_overdue_tasks(weeks, cal_index, today):
    """找出已过截止日期但未完成的任务。"""
    completed = get_completed_tasks(cal_index)
    overdue = []
    for w in weeks:
        for task in w.get("tasks", []):
            dl = task.get("deadline", "")
            if dl and dl < today.isoformat() and task["id"] not in completed:
                overdue.append(task)
    return overdue


def render_full(plan, cal_index, today):
    """渲染完整规划视图。"""
    weeks = plan.get("weeks", [])
    deadlines = plan.get("deadlines", [])
    course = plan.get("course", "未命名课程")
    completed = get_completed_tasks(cal_index)

    total_tasks = sum(len(w.get("tasks", [])) for w in weeks)
    done_tasks = sum(
        1 for w in weeks
        for t in w.get("tasks", [])
        if t["id"] in completed
    )
    current_week = find_current_week(weeks, today)
    current_week_num = current_week.get("week", "?") if current_week else "?"

    lines = []

    # --- 总览 ---
    lines.append(f"📚 {course}")
    if weeks:
        sem_start = weeks[0].get("start_date", "?")
        sem_end = weeks[-1].get("start_date", "?")
        lines.append(f"学期  {sem_start} ~ {sem_end}")
    lines.append(f"进度  {progress_bar(done_tasks, total_tasks)}  Week {current_week_num}/{len(weeks)}")
    lines.append("")

    # --- 本周详情 ---
    if current_week:
        lines.append(f"== 本周 (Week {current_week.get('week', '?')}) ==")
        lines.append(f"主题  {current_week.get('theme', '无')}")
        if current_week.get("topics"):
            lines.append(f"知识点  {', '.join(current_week['topics'])}")
        tasks = current_week.get("tasks", [])
        if tasks:
            lines.append("任务:")
            for t in tasks:
                icon = "✅" if t["id"] in completed else "⬜"
                dl = f" (截止: {t['deadline']})" if t.get("deadline") else ""
                lines.append(f"  {icon} {t['id']}  {t['content']}{dl}")
        lines.append("")

    # --- 近期截止 ---
    upcoming = [
        d for d in deadlines
        if d.get("date", "") >= today.isoformat()
    ]
    upcoming.sort(key=lambda d: d["date"])
    upcoming = upcoming[:5]
    if upcoming:
        lines.append("== 近期截止 ==")
        for d in upcoming:
            days_left = (date.fromisoformat(d["date"]) - today).days
            marker = f"⚡{days_left}天" if days_left <= 7 else f"{days_left}天"
            lines.append(f"  {d['date']}  {d['content']} ({marker})")
        lines.append("")

    # --- 逾期任务 ---
    overdue = get_overdue_tasks(weeks, cal_index, today)
    if overdue:
        lines.append("== 逾期任务 ==")
        for t in overdue:
            lines.append(f"  ⚠ {t['id']}  {t['content']} (原定: {t.get('deadline', '?')})")
        lines.append("")

    return "\n".join(lines)


def render_week(plan, cal_index, week_num):
    """渲染指定周的详情。"""
    weeks = plan.get("weeks", [])
    completed = get_completed_tasks(cal_index)

    target = None
    for w in weeks:
        if w.get("week") == week_num:
            target = w
            break

    if not target:
        return f"未找到 Week {week_num}"

    lines = []
    lines.append(f"== Week {week_num}: {target.get('theme', '无')} ==")
    lines.append(f"开始  {target.get('start_date', '?')}")
    if target.get("topics"):
        lines.append(f"知识点  {', '.join(target['topics'])}")

    tasks = target.get("tasks", [])
    done = sum(1 for t in tasks if t["id"] in completed)
    lines.append(f"进度  {progress_bar(done, len(tasks))}  {done}/{len(tasks)}")

    if tasks:
        lines.append("任务:")
        for t in tasks:
            icon = "✅" if t["id"] in completed else "⬜"
            dl = f" (截止: {t['deadline']})" if t.get("deadline") else ""
            lines.append(f"  {icon} {t['id']}  {t['content']}{dl}")

    return "\n".join(lines)


def render_deadlines(plan, today):
    """只渲染截止日期列表。"""
    deadlines = sorted(plan.get("deadlines", []), key=lambda d: d.get("date", ""))
    if not deadlines:
        return "无截止日期记录"

    lines = ["== 所有截止日期 =="]
    for d in deadlines:
        dl_date = d.get("date", "?")
        if dl_date < today.isoformat():
            status = "已过"
        else:
            days_left = (date.fromisoformat(dl_date) - today).days
            status = f"{days_left}天后"
        lines.append(f"  {dl_date}  [{d.get('type', '')}] {d['content']} ({status})")

    return "\n".join(lines)


def main():
    plan_path = os.path.join(COURSE_DIR, "state", "semester_plan.json")
    plan = load_json(plan_path)

    if not plan or not plan.get("weeks"):
        print("NO_PLAN: 尚未生成学期规划。请先上传 syllabus 文件。")
        sys.exit(0)

    cal_index = load_calendar_index()
    today = date.today()
    args = sys.argv[1:]

    if "--week" in args:
        idx = args.index("--week")
        week_num = int(args[idx + 1])
        print(render_week(plan, cal_index, week_num))
    elif "--deadlines" in args:
        print(render_deadlines(plan, today))
    else:
        print(render_full(plan, cal_index, today))


if __name__ == "__main__":
    main()
