# DEVLOG — course-skill 工程日志

记录架构决策、模块依赖关系、已知问题和每次改动的原因。
维修或扩展前先读，改完后追加记录。

---

## 格式规范

每条记录包含：日期、改动内容、原因、影响的文件。

```
## YYYY-MM-DD  标题

**改动**：做了什么
**原因**：为什么这么做（不是显而易见的才需要写）
**影响文件**：哪些文件涉及
**注意**：有坑或后续要注意的地方（可选）
```

---

## 2026-04-08  初始架构建立

**改动**：建立 skill 基础结构，完成 `skill.md`、`bootstrap.py`、`commands/settings.py`

**原因**：
- 选择 Claude Code skill 形态而非独立脚本：便于分发、依赖少、可复用官方 skill
- 代码与数据分离：`SKILL_DIR`（代码）vs `COURSE_DIR`（课程数据），支持一个 skill 管理多门课
- 每次启动执行 `bootstrap.py` 读状态文件，解决 skill 无状态执行问题
- 文件解析外包给 `anthropic-skills:pdf/pptx/docx`，不在本 skill 内实现

**影响文件**：`skill.md`、`bootstrap.py`、`commands/settings.py`

**注意**：
- `COURSE_DIR` 完全依赖 `os.getcwd()`，用户必须先 `cd` 到课程目录再调用 skill
- `session.json` 跨日时 `pending` 和 `weak_topics` 自动延续，`completed` 和 `summary` 清零（见 `bootstrap.py` 第 50-58 行）

---

## 2026-04-08  输出格式决策：去掉边框文本框

**改动**：将原设计的 `╔══╗` 边框 ASCII 文本框改为直接使用 ` ```text ``` ` 代码块

**原因**：边框字符增加生成复杂度，代码块已能满足"视觉分区"需求，维护成本更低

**影响文件**：`skill.md`（输出格式规则节）

**注意**：`ui/box_renderer.py` 因此未创建，`ui/` 目录目前只计划包含 `progress_bar.py` 和 `calendar.py`

---

## 知识点格式（Evoldown 风格）— 参考来源

知识点 JSON 格式借鉴自渐构（modevol.com）的 Evoldown 段落分类系统：

```
d = Definition  定义/描述
e = Example     具体示例
t = Transfer    迁移应用
v = Validation  验证题
```

原始 Evoldown 是文档标记语言（类 Markdown），这里简化为 JSON 存储。
`weak` 字段是本 skill 新增的，标记用户薄弱知识点，供复习和出题模块优先处理。

---

---

## 2026-04-09  日历系统重新定义 + 跨课程同步机制

**改动**：
- 日历从"展示组件"重定义为"时间索引系统"，连接计划线与历史线
- 新增 `COURSE_DIR/calendar/index.json`（按日期的稀疏索引）和 `calendar/events.jsonl`（只追加事件流）
- 新增 `COURSE_DIR/sync/daily/YYYY-MM-DD.json`（课程级日摘要）
- 新增 `SKILL_DIR/registry.json`（已知课程注册表）
- 新增 `SKILL_DIR/memory/daily/YYYY-MM-DD.json`（跨课程聚合摘要）
- 新增 `sync.py`（同步逻辑）
- `settings.py --init` 现在同时初始化 calendar/ 和 sync/ 目录，并注册课程到 registry.json

**原因**：
- 计划线（semester_plan.json）是粗粒度主计划，calendar/index.json 是细粒度操作视图，两者分离
- 历史线（events.jsonl）只追加，保证可回溯；计划线可变，支持改计划
- 跨课程问题（"这周学了什么"）需要一个 skill 级聚合层，registry.json 是课程发现机制

**影响文件**：`commands/settings.py`、`sync.py`（新增）

**注意**：
- `events.jsonl` 中 `summary` 字段留空，由 skill.md 在对话结束时负责填写
- `sync.py --read` 只读不写，跨课程查询时用这个避免副作用
- `calendar/index.json` 的 `planned_tasks` 来源于 `semester_plan.json`，两者需保持一致，改计划时要同步更新两个文件

---

## 2026-04-09  calendar.py + ui/progress_bar.py 完成

**改动**：
- 新增 `calendar.py`：日历时间索引系统的查询/写入接口
  - 查询：`get_day`、`get_range`、`get_topic`、`get_overdue`
  - 写入：`log_event`（追加事件 + 自动更新索引）、`plan_day`、`reschedule`
  - CLI 入口供 skill.md 通过 Bash 工具调用
- 新增 `ui/progress_bar.py`：单进度条 + 多课程对比进度条
- 所有 Python 文件添加 `sys.stdout.reconfigure(encoding="utf-8")`（Windows GBK 兼容）

**注意**：
- `log_event` 的事件记录在实际发生的日期（ts 时间戳），不是任务原计划日期。plan 线和 history 线分别独立追踪，这是双时间线设计的核心——计划线显示"应该做什么"，历史线显示"实际做了什么"
- `calendar.py` 依赖 `COURSE_DIR = os.getcwd()`，必须在课程目录下调用

---

## 2026-04-09  /plan 命令 + semester_plan 格式规范

**改动**：
- 新增 `commands/plan.py`：三种视图模式 — 完整规划、单周详情（`--week N`）、截止日期（`--deadlines`）
- 在 `skill.md` 中定义 `semester_plan.json` 完整格式，包括任务 ID 命名规则（`w{周}_t{序号}`）和类型枚举
- 在 `skill.md` 中补充 syllabus 解析后的日历注册流程（`calendar.py plan_day`）

**影响文件**：`commands/plan.py`（新增）、`skill.md`（文件处理节 + 新增学期规划格式节）

**注意**：
- `plan.py` 通过 `from calendar import load_index` 复用 calendar.py 的索引读取，因此 calendar.py 不能改名
- 周数显示 `Week N/total` 中的 total 取 `weeks` 数组长度，测试数据如果跳周会显示不对，真实 syllabus 生成的完整周序列不会有此问题

---

## 待完成模块（按优先级）

- [x] `ui/progress_bar.py` — 进度条字符串生成
- [x] `calendar.py` — 日历查询/写入接口
- [x] `/plan` 命令 + `semester_plan.json` 格式规范
- [x] syllabus 解析流程（`skill.md` 中定义，委托官方 skill + Claude 推理）
- [ ] `memory/` 读写逻辑（Phase 3）
- [ ] `prompts/question_gen.md`（Phase 4）
- [ ] `prompts/evaluator.md`（Phase 4）
