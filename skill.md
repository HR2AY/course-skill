---
name: course
description: 本科课程学习助手 - 文件解析、学期规划、每日对话、复习出题全流程管理
---

# 课程学习助手

## 路径约定

启动时，两个路径始终需要区分：

- `SKILL_DIR`：本 skill 所在目录（bootstrap.py 用 `__file__` 自动解析）
- `COURSE_DIR`：用户当前工作目录（`os.getcwd()`），即课程文件夹

所有课程数据（config、state、memory、uploads、processed）均在 `COURSE_DIR` 下。
所有 skill 代码（ui/、commands/、prompts/）均在 `SKILL_DIR` 下。

---

## 启动流程

**每次被调用，第一步必须执行：**

```bash
python {SKILL_DIR}/bootstrap.py
```

bootstrap.py 会：
1. 检测 `COURSE_DIR` 是否是合法课程文件夹（存在 `config.json`）
2. 读取 `state/session.json`（当日缓存）
3. 读取 `memory/index.json`（长期记忆索引）
4. 输出一段结构化的上下文摘要供本 skill 注入

将 bootstrap 输出视为隐含上下文，不直接展示给用户，但所有回答都基于它。

**若 bootstrap 报错 `NOT_A_COURSE_DIR`：**
提示用户：
```text
当前目录不是课程文件夹。
请先 cd 到课程目录，或输入 /setting 初始化新课程。
```

---

## 命令路由

用户输入以 `/` 开头时，进入对应模式，不走普通对话流：

| 命令 | 行为 |
|------|------|
| `/setting` | 运行 `commands/settings.py`，展示设置面板，读写 `config.json` |
| `/plan` | 运行 `commands/plan.py`，展示学期规划视图 + 当前进度 + 逾期任务 |
| `/review` | 进入错题复习模式，从 `memory/mistakes/` 加载薄弱知识点 |
| `/quiz` | 进入题目生成模式，基于 `processed/knowledge_base/` 出题 |
| `/help` | 打印命令列表和当前课程基本信息 |

其他所有输入进入**学习对话流**。

---

## 学习对话流

正常对话时按以下优先级使用上下文：

1. bootstrap 注入的 `session.json`（今天做了什么、薄弱点）
2. `memory/index.json` 中匹配的长期记忆条目
3. `processed/knowledge_base/` 中对应话题的结构化知识点

回答具体问题时，若 `knowledge_base/` 有对应 `{topic}.json`，优先从其 `d`/`e`/`t` 字段组织回答，而不是凭空生成。

**每轮对话结束前判断：**
- 用户完成了某个任务 → 更新 `state/session.json` 的 `completed` 列表
- 发现新的理解薄弱点 → 更新 `session.json` 的 `weak_topics`，同时写入 `memory/mistakes/`
- 当日对话结束 → 更新 `session.json` 的 `summary`

---

## 文件处理

用户上传文件或要求处理 `uploads/` 下的文件时，根据类型委托对应官方 skill：

| 文件类型 | 委托 skill | 处理目标 |
|----------|-----------|---------|
| `.pdf` | `anthropic-skills:pdf` | `processed/knowledge_base/` |
| `.pptx` / `.ppt` | `anthropic-skills:pptx` | `processed/knowledge_base/` |
| `.docx` / `.doc` | `anthropic-skills:docx` | `processed/knowledge_base/` |

处理完成后，将提取内容按下方 Evoldown 格式写入 `processed/knowledge_base/{topic}.json`。

**若文件是 syllabus（用户明确标注或文件名含 syllabus/课程大纲）：**

在知识库写入之外，执行学期规划生成流程：

1. 从提取的文本中识别：章节/主题列表、考试日期、作业 deadline、周计划安排
2. 读取 `config.json` 获取学期起止日期和每周学习时长
3. 生成 `state/semester_plan.json`（格式见下方"学期规划格式"节）
4. 对有明确日期的任务调用 `calendar.py plan_day` 注册到日历
5. 运行 `commands/plan.py` 展示学期规划视图

---

## 学期规划格式

`state/semester_plan.json` 是整个学期的粗粒度主计划。

粒度原则：计划线按 **周/天** 粒度，不强制到小时级。历史线（calendar/events.jsonl）自动记录实际粒度。

```json
{
  "course": "信号与系统",
  "generated_from": "uploads/syllabus/syllabus.pdf",
  "generated_at": "2026-04-09",
  "weeks": [
    {
      "week": 1,
      "start_date": "2026-02-17",
      "theme": "信号基础概论",
      "topics": ["信号分类", "系统分类", "基本运算"],
      "tasks": [
        {"id": "w01_t01", "content": "阅读 Lecture 1-2", "type": "read"},
        {"id": "w01_t02", "content": "完成 Problem Set 1", "type": "assignment", "deadline": "2026-02-23"}
      ]
    }
  ],
  "deadlines": [
    {"date": "2026-04-20", "type": "midterm", "content": "期中考试"},
    {"date": "2026-06-20", "type": "final", "content": "期末考试"}
  ]
}
```

字段说明：
- `weeks[].tasks[].id`：格式 `w{周数}_t{序号}`，在整个规划内唯一
- `weeks[].tasks[].type`：`read` / `assignment` / `review` / `practice`
- `weeks[].tasks[].deadline`：可选，有截止日期的任务才填
- `deadlines[]`：考试和重要截止日期的汇总，便于快速查询

生成规划后，对所有有 deadline 的 task，调用：
```bash
python {SKILL_DIR}/calendar.py plan_day {deadline} '["task_id"]'
```
将任务注册到日历索引。

---

## 知识点存储格式（Evoldown 风格）

每个知识点存为独立 JSON 文件 `processed/knowledge_base/{topic}.json`：

```json
{
  "topic": "概念名称",
  "source": "来源文件名",
  "d": "定义/描述（是什么）",
  "e": ["具体示例1", "具体示例2"],
  "t": "迁移应用场景（能用在哪）",
  "v": "验证题（怎么检验掌握了）",
  "tags": ["所属模块标签"],
  "weak": false
}
```

`weak: true` 表示用户在这个知识点上出现过错误或标记不懂，复习和出题模块优先处理。

---

## 输出格式规则

状态信息、进度、日历等 UI 内容放在 ` ```text ``` ` 代码块内，正常对话回答直接输出文本。

只在以下情况输出代码块 UI：
- 命令触发（`/plan`、`/setting` 等）
- 每日启动时的状态摘要
- 任务完成时的进度更新

状态摘要标准样式（由 `ui/progress_bar.py` 生成）：

```text
📚 信号与系统 | Week 5 · Day 3
进度  [████████████░░░░░░░░] 60%
当前  Lecture 8 - 卷积定理
薄弱  傅里叶变换、频域概念
```

---

## 记忆写入规则

写入 `memory/mistakes/{date}_{topic}.json` 的触发条件：
- 用户答题出错
- 用户输入"不懂"、"没理解"、"再解释"等信号词
- 对话中发现用户对某概念的理解存在偏差

写入格式：
```json
{
  "date": "2026-04-08",
  "topic": "卷积定理",
  "error_context": "将卷积和乘法的频域关系搞反",
  "correction": "时域卷积 = 频域相乘，时域相乘 = 频域卷积",
  "source_knowledge": "processed/knowledge_base/卷积定理.json"
}
```

同步更新 `memory/index.json`，追加一条索引记录，供 bootstrap 快速检索。
