# course-skill

本科课程学习助手 skill。支持文件解析、学期规划、每日对话、复习、出题。

## 快速使用

```bash
cd ~/courses/你的课程文件夹
/course
```

首次使用先初始化：
```
/setting init
```

## 命令一览

| 命令 | 功能 |
|------|------|
| `/setting` | 查看 / 修改课程配置 |
| `/setting init` | 初始化新课程目录 |
| `/plan` | 查看学期规划和日历 |
| `/review` | 错题复习模式 |
| `/quiz` | 题目生成模式 |
| `/help` | 打印命令列表 |

---

## AI 维修指南

> 如果你是 AI，正在修复或扩展这个 skill，先读这一节再动手。

### 第一步：看工程日志

所有架构决策、模块依赖、已知问题和改动历史都在：

**[DEVLOG.md](./DEVLOG.md)**

改动前先查一下有没有相关记录，避免重复踩坑。改完之后在 DEVLOG.md 末尾追加一条记录。

### 第二步：理解两个路径

整个 skill 的路径逻辑只有两个变量，搞清楚就不会乱：

```
SKILL_DIR  = bootstrap.py 所在目录（skill 代码）
COURSE_DIR = os.getcwd()  （用户 cd 到的课程文件夹）
```

skill 代码在 `SKILL_DIR`，所有课程数据在 `COURSE_DIR`。两者不能混。

### 第三步：文件职责速查

```
skill.md                  主入口：对话流 + 命令路由 + 格式规则
bootstrap.py              启动读状态 → 输出上下文摘要
commands/settings.py      /setting 命令：初始化目录 + 显示/修改配置
ui/progress_bar.py        进度条字符串生成
ui/calendar.py            ASCII 日历生成
prompts/question_gen.md   出题 prompt 模板
prompts/evaluator.md      答案评估 prompt 模板
```

课程数据文件（在 COURSE_DIR 里）：

```
config.json                    课程元信息
state/session.json             当日缓存（跨日自动重置）
state/semester_plan.json       整学期分层规划
state/progress.json            当前进度指针
memory/index.json              长期记忆索引
memory/mistakes/{date}_{topic}.json   错题记录
processed/knowledge_base/{topic}.json 结构化知识点
```

### 常见改动入口

- **改对话逻辑 / 命令行为** → `skill.md`
- **改启动加载的内容** → `bootstrap.py`
- **改设置页面字段** → `commands/settings.py` 的 `CONFIG_DEFAULTS`
- **加新命令** → `commands/` 下新建文件，在 `skill.md` 命令路由表里登记
- **改知识点存储格式** → `skill.md` 的"知识点存储格式"节 + `bootstrap.py` 的读取逻辑需同步更新
- **改错题记录格式** → `skill.md` 的"记忆写入规则"节

### 外包依赖

文件解析不在本 skill 内实现，委托给官方 skill：

| 文件类型 | 委托 skill |
|----------|-----------|
| PDF | `anthropic-skills:pdf` |
| PPT/PPTX | `anthropic-skills:pptx` |
| DOCX | `anthropic-skills:docx` |

如果官方 skill 接口有变更，只需修改 `skill.md` 中"文件处理"节的委托指令。
