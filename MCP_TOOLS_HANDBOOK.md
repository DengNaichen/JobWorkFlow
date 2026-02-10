# JobWorkFlow MCP 工具手册

本手册详细介绍了 JobWorkFlow 项目中 7 个核心 MCP 工具的功能、执行逻辑及数据流。这些工具共同协作，实现了从职位抓取到简历投递的全自动化流程。

---

## 工具流概览

1. **抓取** (`scrape_jobs`) → 存入数据库 `status='new'`
2. **读取** (`bulk_read_new_jobs`) → 获取待筛选队列
3. **筛选** (`bulk_update_job_status`) → 更新状态 (`shortlist`/`reject`)
4. **初始化** (`initialize_shortlist_trackers`) → 生成 Obsidian 追踪文件与工作空间
5. **定制** (`career_tailor`) → 生成 `ai_context.md` 并编译 `resume.pdf`
6. **完结** (`finalize_resume_batch`) → 终结流程，批量更新数据库审计字段并同步追踪文件状态
7. **维护** (`update_tracker_status`) → 可选步骤，用于手动调整或自动化校验追踪文件状态

---

## Skill 与 MCP 工具协作模型

本项目采用"大脑 + 手脚"的混合编排架构：

- **Skill（领域知识）**：纯推理与知识规范，不执行任何 I/O 操作。Agent 通过读取 `skills/xxx/SKILL.md` 来加载领域知识。
- **MCP 工具（执行能力）**：负责数据库读写、文件操作、API 调用等实际执行动作。

两者协作流程：
1. Agent 读取 Skill 获取决策规则
2. Agent 在内存中完成推理和决策
3. Agent 调用 MCP 工具执行落库或文件写入

**项目中的两个核心 Skill：**
- `job-matching-expertise`：职位筛选的评估标准和决策框架
- `resume-crafting-expertise`：简历定制的内容策略和质量守则

---

## 通用特性

### 预览模式 (dry_run)

大多数写入型工具支持 `dry_run=true` 参数，可预览结果而不执行实际写入：
- `scrape_jobs`：预览将要插入的记录
- `initialize_shortlist_trackers`：预览将要创建的 tracker 文件
- `update_tracker_status`：预览状态变更
- `finalize_resume_batch`：预览 finalization 结果

### 结构化错误响应

所有工具采用统一的错误响应格式：
```json
{
  "error": {
    "code": "VALIDATION_ERROR | FILE_NOT_FOUND | DB_NOT_FOUND | INTERNAL_ERROR | COMPILE_ERROR",
    "message": "人类可读的错误描述",
    "retryable": true
  }
}
```

| 错误码 | 含义 | 是否可重试 |
|--------|------|------------|
| `VALIDATION_ERROR` | 输入参数校验失败 | 否（需修正参数） |
| `FILE_NOT_FOUND` | 文件不存在 | 否（需创建文件） |
| `DB_NOT_FOUND` | 数据库文件不存在 | 否（需初始化 DB） |
| `INTERNAL_ERROR` | 未预期的内部错误 | 是 |
| `COMPILE_ERROR` | LaTeX 编译失败 | 视情况 |

---

## 1. scrape_jobs (职位抓取)

**工作流顺序**：第 1 步 (入口)

执行外部源 (LinkedIn) 的职位搜索、数据清洗与去重入库。

**具体做什么**：
- 基于搜索词 (`terms`) 和地点 (`location`) 搜索职位。
- 自动过滤掉没有 URL 或描述的无效记录。
- 执行**幂等性去重**：如果职位 URL 已存在，则忽略；否则插入，默认状态为 `new`。
- 支持 `dry_run` 预览模式。
- 每个搜索词独立处理，单个词失败不阻塞其他词（部分成功模式）。

**关键数据结构**：
- **输入**：
  - `terms` (数组, 必需): 搜索关键词列表
  - `location` (字符串): 地点过滤
  - `results_wanted` (整数): 每个词的期望结果数量
  - `hours_old` (整数): 时间窗口（小时）
  - `dry_run` (布尔): 预览模式
- **输出**：
  - `run_id`: 批次运行标识符
  - `results`: 每个搜索词的详细结果
  - `totals`: 汇总统计 (`inserted_count`, `duplicate_count`, `fetched_count` 等)

---

## 2. bulk_read_new_jobs (批量读取新职位)

**工作流顺序**：第 2 步

从 SQLite 数据库中提取处于 `new` 状态的职位（只读操作）。

**具体做什么**：
- 使用基于光标 (`cursor`) 的分页，确保在大数据量下的检索效率和确定性顺序。
- 每次请求返回最多 `limit` 条记录及分页信息。

**关键数据结构**：
- **输入**：
  - `limit` (整数, 默认 50): 每页数量 (1-1000)
  - `cursor` (字符串): 分页标记
  - `db_path` (字符串): 数据库路径覆盖
- **输出**：
  - `jobs`: 职位列表 (包含完整详情)
  - `count`: 本页记录数
  - `next_cursor`: 下一页光标
  - `has_more`: 是否有更多页

---

## 3. 职位筛选与状态更新 (Triage & Status Update)

这一步是"大脑"与"手脚"协作过程：

### 3a. Skill 执行：AI 逻辑分类 (Triage)

Agent 加载 `job-matching-expertise` Skill 对读取到的新职位进行打分。

**具体做什么**：
- **内存推理**：AI 在一次对话中读完所有职位描述，根据 Skill 里的 Matching Rubric 判定每个职位属于 `shortlist` (入围), `reviewed` (待定) 还是 `reject` (拒绝)。
- **批量决策**：AI 在大脑中形成一份完整的"修改清单"，暂存分类结果和判断理由。

### 3b. MCP 工具：bulk_update_job_status (执行落库)

将 3a 的决策结果一次性原子化写入数据库。

**具体做什么**：
- **单次交互执行**：AI 将 3a 形成的清单塞进一个 JSON 数组，调用此工具发起更新。
- **原子性保证**：采用 All-or-Nothing 机制，确保数据库状态 (SSOT) 的绝对一致，并记录分类理由 (`notes`)。

**关键数据结构**：
- **输入**：
  - `updates` (数组, 必需): 更新项列表，每项包含 `id`, `status`, `notes`
  - `db_path` (字符串): 数据库路径覆盖
- **输出**：
  - `updated_count`: 成功更新数量
  - `failed_count`: 失败数量
  - `results`: 每项的详细结果

---

## 4. initialize_shortlist_trackers (初始化入围追踪)

**工作流顺序**：第 4 步

为入围职位于 `trackers/` 目录生成对应的 Markdown 文件与存储目录。

**具体做什么**：
- 读取数据库中 `status='shortlist'` 的职位。
- 生成遵循特定命名规范的 `.md` 文件 (如 `YYYY-MM-DD-company-id.md`)。
- 自动创建文件所需的父目录及相关的简历/封信存储文件夹。
- **去重逻辑**：基于 `reference_link` (即职位 URL) 检测已有 tracker，避免重复创建。

**关键数据结构**：
- **输入**：
  - `limit` (整数, 默认 50): 处理数量 (1-200)
  - `force` (布尔): 覆盖模式
  - `dry_run` (布尔): 预览模式
  - `trackers_dir` (字符串): tracker 目录路径覆盖
- **输出**：
  - `created_count`: 创建数量
  - `skipped_count`: 跳过数量（已存在）
  - `failed_count`: 失败数量
  - `results`: 每项的详细结果

---

## 5. 简历定制与编译 (Resume Tailoring & Compilation)

这一步是典型的"混合式编排"，工具与 Agent 需要**迭代交互**直至成功：

### 交互模型：Try → Fail → Fix → Retry

```
Agent 调用 career_tailor
    ↓
[若 tex 中存在占位符] → 返回 VALIDATION_ERROR (item 失败)
    ↓
Agent 使用文件编辑工具填充占位符
    ↓
Agent 再次调用 career_tailor
    ↓
[若无占位符] → 触发 pdflatex 编译 → 成功
```

### 5a. 首次调用：Bootstrap + 占位符检测

调用 `career_tailor` 创建应用工作区。

**具体做什么**：
- **备料汇总**：批量建立目录、准备 `.tex` 模板并汇总生成的 `ai_context.md`。
- **占位符拦截**：工具扫描 tex 文件，若检测到占位符模式则抛出 `VALIDATION_ERROR`，该 item 失败。

**已知的占位符模式**：
- `WORK-BULLET-POINT-*`
- `PROJECT-AI-*`
- `PROJECT-BE-*`
- `TODO: fill this in`
- `[Description goes here]`

### 5b. Agent 端：内容创作 (Crafting)

加载 `resume-crafting-expertise` Skill 并在内存中构思适配内容。

**具体做什么**：
- **内容翻译**：Agent 读取 `ai_context.md`，将你的原始经历"翻译"成专业 Bullet Points。
- **源码注入**：Agent 使用文件编辑工具，将构思好的内容写回 `resume.tex`，必须**抹除所有占位符**。

### 5c. 再次调用：最终渲染 (Final Compile)

再次调用 `career_tailor` 渲染 PDF 成果。

**具体做什么**：
- **门禁扫描**：工具再次扫描 `.tex` 文件。若无占位符，正式触发 `pdflatex`。
- **成果交接**：编译成功后，生成的 PDF 路径会进入 `successful_items` 载荷，作为 `finalize_resume_batch` 的**输入契约**。

**关键数据结构**：
- **输入**：
  - `items` (数组, 必需): 批次项，每项包含 `tracker_path` 和可选的 `job_db_id`
  - `force` (布尔): 是否覆盖已有 resume.tex
  - `full_resume_path`, `resume_template_path`, `applications_dir`, `pdflatex_cmd`: 可选覆盖路径
- **输出**：
  - `run_id`: 批次运行标识符
  - `total_count`, `success_count`, `failed_count`: 汇总统计
  - `results`: 每项的详细结果
  - `successful_items`: 成功项列表（供 finalize 使用）
  - `warnings`: 非致命警告列表

---

## 6. finalize_resume_batch (流程批量完结)

**工作流顺序**：第 6 步 (落库完结)

提交定制成果到数据库并同步追踪文件状态。

**具体做什么**：
- **级联写入**：
  1. 更新数据库职位状态为 `resume_written` 并记录 `resume_pdf_path`
  2. 同步更新追踪文件的 Frontmatter 状态
- **错误补偿机制**：如果 tracker 文件同步失败，数据库状态会回滚到 `reviewed` 并记录 `last_error`。
- **per-item 继续执行**：单个 item 失败不阻塞其他 items。

**关键数据结构**：
- **输入**：
  - `items` (数组, 必需): 包含 `id`, `tracker_path`, 可选 `resume_pdf_path`
  - `run_id` (字符串): 批次标识符（可选，自动生成）
  - `db_path` (字符串): 数据库路径覆盖
  - `dry_run` (布尔): 预览模式
- **输出**：
  - `run_id`: 批次运行标识符
  - `finalized_count`: 成功完结数量
  - `failed_count`: 失败数量
  - `dry_run`: 是否为预览模式
  - `results`: 每项的详细结果

---

## 7. update_tracker_status (可选维护：追踪文件状态微调)

**工作流顺序**：实用工具/辅助步骤

安全更新 Markdown 追踪文件的 Frontmatter 状态。

**具体做什么**：
- **手动微调**：这是一个低频工具，主要用于用户手动调整状态（如从"简历已写"改为"面试中"）。
- **状态转换策略**：内置状态机，防止非法状态转换。可使用 `force=true` 绕过（会产生警告）。
- **Resume Written 守门检查**：当状态变为 `Resume Written` 时，会强制执行**物理校验**：
  - 检查 `resume.pdf` 是否存在且非空
  - 检查 `resume.tex` 是否存在
  - 扫描 tex 中是否残留占位符

**关键数据结构**：
- **输入**：
  - `tracker_path` (字符串, 必需): tracker 文件路径
  - `target_status` (字符串, 必需): 目标状态
  - `dry_run` (布尔): 预览模式
  - `force` (布尔): 强制绕过状态转换策略
- **输出**：
  - `tracker_path`: 操作的文件路径
  - `previous_status`: 原状态
  - `target_status`: 目标状态
  - `action`: 操作结果 (`updated`, `noop`, `would_update`, `blocked`)
  - `success`: 是否成功
  - `guardrail_check_passed`: 守门检查是否通过（仅限 Resume Written）
  - `warnings`: 警告列表
