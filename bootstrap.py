#!/usr/bin/env python3
"""
bootstrap.py - 每次 skill 启动时执行
读取课程状态，输出结构化上下文供 skill.md 注入。

路径约定：
  SKILL_DIR = 本文件所在目录（skill 代码）
  COURSE_DIR = 当前工作目录（用户 cd 到的课程文件夹）
"""

import os
import json
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
COURSE_DIR = os.getcwd()


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


def find_today_tasks(plan, today):
    """从学期规划中找出今天的任务列表和当前周数。"""
    for week in plan.get("weeks", []):
        for day in week.get("days", []):
            if day.get("date") == today:
                tasks = [
                    task
                    for session_block in day.get("sessions", [])
                    for task in session_block.get("tasks", [])
                ]
                return tasks, week.get("week")
    return [], None


def make_progress_bar(done, total, width=20):
    if total == 0:
        return "[" + "░" * width + "] --"
    filled = int(done / total * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(done / total * 100)
    return f"[{bar}] {pct}%"


def main():
    # 1. 验证是否为合法课程目录
    config_path = os.path.join(COURSE_DIR, "config.json")
    if not os.path.exists(config_path):
        print("NOT_A_COURSE_DIR")
        sys.exit(1)

    config = load_json(config_path)
    today = date.today().isoformat()

    # 2. 读取 session，跨日则重置当日字段、保留延续字段
    session_path = os.path.join(COURSE_DIR, "state", "session.json")
    session = load_json(session_path, default={})

    if session.get("date") != today:
        session = {
            "date": today,
            "completed": [],
            "pending": session.get("pending", []),      # 未完成任务延续到今天
            "weak_topics": session.get("weak_topics", []),  # 薄弱点跨日保留
            "summary": "",
        }
        save_json(session_path, session)

    # 3. 读取长期记忆索引
    memory_index_path = os.path.join(COURSE_DIR, "memory", "index.json")
    memory_index = load_json(memory_index_path, default={"mistakes": [], "insights": []})

    # 4. 读取学期规划，找今日任务
    plan_path = os.path.join(COURSE_DIR, "state", "semester_plan.json")
    plan = load_json(plan_path, default={})
    today_tasks, current_week = find_today_tasks(plan, today)

    done_count = sum(1 for t in today_tasks if t.get("status") == "done")
    total_count = len(today_tasks)

    # 5. 组装上下文摘要输出
    lines = []
    lines.append("=== COURSE CONTEXT START ===")
    lines.append(f"课程名称: {config.get('name', '未命名课程')}")
    lines.append(f"今日日期: {today}" + (f" | Week {current_week}" if current_week else ""))
    lines.append(f"今日进度: {done_count}/{total_count} {make_progress_bar(done_count, total_count)}")

    if session.get("completed"):
        lines.append(f"已完成任务: {', '.join(session['completed'])}")

    if session.get("pending"):
        lines.append(f"待完成任务: {', '.join(session['pending'])}")

    if session.get("weak_topics"):
        lines.append(f"当前薄弱点: {', '.join(session['weak_topics'])}")

    if session.get("summary"):
        lines.append(f"上次摘要: {session['summary']}")

    recent_mistakes = memory_index.get("mistakes", [])[-5:]
    if recent_mistakes:
        topics = [m.get("topic", "") for m in recent_mistakes if m.get("topic")]
        lines.append(f"近期错题: {', '.join(topics)}")

    lines.append(f"COURSE_DIR: {COURSE_DIR}")
    lines.append(f"SKILL_DIR: {SKILL_DIR}")
    lines.append("=== COURSE CONTEXT END ===")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
