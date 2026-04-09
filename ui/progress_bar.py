#!/usr/bin/env python3
"""
ui/progress_bar.py - 进度条字符串生成

给 skill.md 和 bootstrap.py 提供进度条渲染，输出纯文本，
由调用方放进 ```text ``` 代码块。

用法：
  python progress_bar.py --done 3 --total 5
  python progress_bar.py --done 3 --total 5 --label "今日进度"
  python progress_bar.py --done 3 --total 5 --width 30
  python progress_bar.py --multi '[{"label":"信号","done":3,"total":5},{"label":"高数","done":7,"total":10}]'
"""

import sys
import json

sys.stdout.reconfigure(encoding="utf-8")


def bar(done, total, width=20, label=None):
    """生成单行进度条。"""
    if total <= 0:
        filled = 0
        pct_str = "--"
    else:
        pct = done / total
        filled = int(pct * width)
        pct_str = f"{int(pct * 100)}%"

    blocks = "█" * filled + "░" * (width - filled)
    count = f"{done}/{total}"
    line = f"[{blocks}] {pct_str}  {count}"

    if label:
        line = f"{label}  {line}"

    return line


def multi_bar(items, width=20):
    """生成多行进度条，label 右对齐。"""
    if not items:
        return ""

    max_label = max(len(item.get("label", "")) for item in items)
    lines = []
    for item in items:
        label = item.get("label", "").rjust(max_label)
        lines.append(bar(
            done=item.get("done", 0),
            total=item.get("total", 0),
            width=width,
            label=label,
        ))
    return "\n".join(lines)


def main():
    args = sys.argv[1:]

    # 多课程模式
    if "--multi" in args:
        idx = args.index("--multi")
        items = json.loads(args[idx + 1])
        width = 20
        if "--width" in args:
            width = int(args[args.index("--width") + 1])
        print(multi_bar(items, width=width))
        return

    # 单进度条模式
    done = 0
    total = 0
    width = 20
    label = None

    if "--done" in args:
        done = int(args[args.index("--done") + 1])
    if "--total" in args:
        total = int(args[args.index("--total") + 1])
    if "--width" in args:
        width = int(args[args.index("--width") + 1])
    if "--label" in args:
        label = args[args.index("--label") + 1]

    print(bar(done, total, width=width, label=label))


if __name__ == "__main__":
    main()
