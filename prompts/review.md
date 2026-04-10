# 复习流程（/review）

`/review` 有两个入口，共用同一套**答案判断**子流程。

---

## 功能一：答案判断（接 /quiz）

quiz 出完题、用户提交答案后，自动进入此流程，无需用户显式调用 `/review`。

### 判断规则

| 题型 | 正确标准 |
|------|---------|
| 选择题 | 选项字母完全吻合 |
| 判断题 | 对/错吻合 |
| 计算题 | 最终数值或结论正确（过程有小误差可接受，但须指出） |

### 答对时

```text
✓ 正确！{一句话强化核心要点}
```

继续下一题，或询问是否继续出题。

### 答错时

**第一步**：告知正确答案和原因：

```text
✗ 答错了。

正确答案：{answer}
解析：{explanation，指向 knowledge_base 中的具体字段}
```

**第二步**：将错题写入 `.course/memory/mistakes/`：

文件名格式：`{YYYYMMDD}_{topic}.json`（topic 中的空格替换为下划线）

若该文件已存在（同一知识点今日再次答错）：
- 读取现有文件
- `call_count +1`，`last_reviewed` 更新为当前时间
- 其余字段保持不变
- 调用 `python {SKILL_DIR}/commands/review.py --bump {filepath}`

若不存在，写入新文件：

```json
{
  "question": "题干原文",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "user_answer": "用户的回答",
  "correct_answer": "正确答案",
  "explanation": "解析文本",
  "topic": "知识点名称",
  "chapter": "所属章节",
  "source_knowledge": ".course/processed/knowledge_base/{topic}.json",
  "created_at": "ISO时间戳（精确到分钟）",
  "last_reviewed": "ISO时间戳（精确到分钟）",
  "call_count": 1
}
```

注：`options` 字段仅选择题填写，其他题型省略。

**第三步**：更新 `SKILL_DIR/session.json` 中当前课程条目的 `weak_topics`（若该 topic 不在列表中则追加）。

---

## 功能二：回忆错题

### 入口：用户显式调用 `/review`

首先询问调用方式：

```text
请选择复习范围：
  1. 按时间范围（跨学科）
  2. 按学科 / 章节
```

等待用户选择后执行对应命令：

**方式一：时间范围（跨课程）**

```bash
python {SKILL_DIR}/commands/review.py --list \
  --since {start_date} --until {end_date} \
  --all-courses --sort-by-count
```

**方式二：学科 / 章节**

```bash
# 当前课程全部错题
python {SKILL_DIR}/commands/review.py --list --sort-by-count

# 指定章节
python {SKILL_DIR}/commands/review.py --list --chapter "{章节名}" --sort-by-count
```

---

### 回忆流程（对 MISTAKES_LIST 中每条错题依次执行）

输出以 `MISTAKES_LIST:` 开头的列表后，按 call_count 从高到低逐题处理：

#### 第一步：重放原题

直接展示错题记录中的原始题目（`question` + `options` 字段），不显示答案：

```text
━━━ 错题回顾 [{topic}] ━━━
{question}
{A/B/C/D 选项，若有}

（该题你曾答错 {call_count} 次，上次复习：{last_reviewed[:10]}）

请作答：
```

等待用户回答 → 进入**功能一：答案判断**。

#### 第二步：出相似题

无论原题答对还是答错，原题处理完毕后，从 knowledge_base 加载该知识点：

```bash
python {SKILL_DIR}/commands/quiz.py --topic "{topic}"
```

基于返回的 `QUIZ_CONTEXT`，按 `prompts/quiz.md` 第五步的规则生成一道**不同于原题**的相似题（同一知识点，改换题干或数值）。

```text
━━━ 相似练习 ━━━
{新题}

请作答：
```

等待用户回答 → 再次进入**功能一：答案判断**。

#### 第三步：进入下一条错题

当前知识点的原题 + 相似题均处理完毕后，询问：

```text
继续下一道错题？(y/n)
```

- `y` → 处理列表中下一条
- `n` → 输出本次复习小结：

```text
本次复习 {N} 道，答对 {M} 道。
仍需加强：{答错的 topic 列表}
```
