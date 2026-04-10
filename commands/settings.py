#!/usr/bin/env python3
"""
commands/settings.py - /setting 命令处理器

用法：
  python settings.py          显示当前课程配置
  python settings.py --init   初始化新课程目录结构（已存在则不覆盖）
"""

import os
import json
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

COURSE_DIR = os.getcwd()
COURSE_DATA = os.path.join(COURSE_DIR, ".course")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_DEFAULTS = {
    "name": "新课程",
    "semester_start": "",
    "semester_end": "",
    "weekly_study_hours": 10,
    "exam_date": "",
    "instructor": "",
    "notes": "",
}

# 初始化时在 .course/ 下创建的目录
DIRS = [
    "uploads/syllabus",
    "uploads/slides",
    "uploads/readings",
    "uploads/exams",
    "processed/knowledge_base",
    "processed/exam_analysis",
    "state",
    "calendar",
    "memory/mistakes",
    "memory/insights",
    "sync/daily",
]


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


def init_course():
    """初始化新课程目录，已存在的文件不覆盖。"""
    for d in DIRS:
        os.makedirs(os.path.join(COURSE_DATA, d), exist_ok=True)

    config_path = os.path.join(COURSE_DATA, "config.json")
    is_new = not os.path.exists(config_path)
    if is_new:
        save_json(config_path, CONFIG_DEFAULTS)

    session_path = os.path.join(COURSE_DATA, "state", "session.json")
    if not os.path.exists(session_path):
        save_json(session_path, {
            "date": date.today().isoformat(),
            "completed": [],
            "pending": [],
            "weak_topics": [],
            "summary": "",
        })

    memory_index_path = os.path.join(COURSE_DATA, "memory", "index.json")
    if not os.path.exists(memory_index_path):
        save_json(memory_index_path, {"mistakes": [], "insights": []})

    # 初始化 calendar 索引
    calendar_index_path = os.path.join(COURSE_DATA, "calendar", "index.json")
    if not os.path.exists(calendar_index_path):
        save_json(calendar_index_path, {})

    # 注册课程到 skill 级注册表
    _register_course(config.get("name", os.path.basename(COURSE_DIR)))

    status = "新建成功" if is_new else "目录已存在，未覆盖现有配置"
    print(f"INIT_OK: {status}")
    print(f"COURSE_DIR: {COURSE_DIR}")
    print("下一步：用 /setting 填写课程信息，或上传 syllabus 开始规划。")


def _register_course(course_name):
    """将当前课程路径注册到 SKILL_DIR/registry.json。已注册则更新名称。"""
    registry_path = os.path.join(SKILL_DIR, "registry.json")
    registry = load_json(registry_path, default={"courses": []})

    courses = registry.get("courses", [])
    existing = next((c for c in courses if c.get("path") == COURSE_DIR), None)
    if existing:
        existing["name"] = course_name
    else:
        courses.append({
            "name": course_name,
            "path": COURSE_DIR,
            "added": date.today().isoformat(),
        })
    registry["courses"] = courses
    save_json(registry_path, registry)


def show_settings():
    """格式化输出当前配置，供 skill.md 包在代码块里展示。"""
    config_path = os.path.join(COURSE_DATA, "config.json")
    if not os.path.exists(config_path):
        print("NOT_A_COURSE_DIR: 当前目录没有 config.json，请先运行 /setting init")
        sys.exit(1)

    c = load_json(config_path, default=CONFIG_DEFAULTS)

    def val(key, fallback="（未设置）"):
        return c.get(key) or fallback

    lines = [
        "⚙  课程设置",
        f"   课程名称      {val('name')}",
        f"   学期开始      {val('semester_start')}",
        f"   学期结束      {val('semester_end')}",
        f"   每周学习      {c.get('weekly_study_hours', 10)} 小时",
        f"   考试日期      {val('exam_date')}",
        f"   任课老师      {val('instructor')}",
    ]
    if c.get("notes"):
        lines.append(f"   备注          {c['notes']}")

    lines += [
        "",
        "修改：直接告诉我要改哪个字段和新的值",
        "初始化新课程：/setting init",
    ]

    print("\n".join(lines))


def main():
    args = sys.argv[1:]
    if "--init" in args or "init" in args:
        init_course()
    else:
        show_settings()


if __name__ == "__main__":
    main()
