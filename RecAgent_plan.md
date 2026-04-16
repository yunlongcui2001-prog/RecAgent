# RecAgent Auto-Research 架构规划

## 一、角色到 Claude Code 原语的映射

| 角色 | 推荐原语 | 理由 |
|---|---|---|
| ① Planner | Subagent (`.claude/agents/planner.md`) | 需要被 Controller 调用，需要隔离上下文（避免被实验细节污染） |
| ② Translator | Subagent | 输入 Planner 的结构化方案，输出 JSON / TODO list；天然适合隔离 + 结构化返回 |
| ③ Coder | Subagent（带 Read/Write/Bash 权限） | 需要实际改代码；隔离上下文避免污染主对话 |
| ④ Reviewer | Subagent + Hook 触发 | Hook 在 Coder 写完文件后**自动**触发 Reviewer subagent，不依赖人或主 agent 想起来调用 |
| ⑤ Runner | Subagent（封装 `bash run.sh` + 指标收集） | 长任务，可以 `run_in_background` |
| ⑥ Analyzer | Subagent（带 KB 写权限） | 输出结构化结论 + 更新 KB |
| ⑦ Logger | Hook（PreToolUse + PostToolUse 写 JSONL） | 完全被动，没必要起 LLM；纯文件追加 |
| ⑧ Controller | Skill（人启动）+ 主对话循环 OR 外部脚本 | 入口在哪决定了交互/自主模式 |
| ⑨ Guardian | Hook（SessionStart）+ 定时 cron | 周期/事件触发，不需要常驻 LLM |

### 关键原则

- **Skill ≠ Agent**：Skill 是"人按一下按钮"，Subagent 才是"agent 调 agent"。流水线角色之间需要互相调用，这是 Subagent 的活，不是 Skill 的活。
- **横切关注点用 Hook**：Logger / Reviewer 的自动触发 / Guardian 的周期校验，都属于横切，不应该写成顺序步骤。
- **Controller 是入口**：决定整套系统是"交互式"（主对话当指挥）还是"自主式"（脚本调 API）。建议先做交互式跑通，再迁移自主式。

---

## 二、具体目录骨架

```
RecAgent/
├── .claude/
│   ├── agents/                    # 5 个流水线 + Reviewer 的 subagent 定义
│   │   ├── planner.md
│   │   ├── translator.md
│   │   ├── coder.md
│   │   ├── reviewer.md
│   │   ├── runner.md
│   │   └── analyzer.md
│   └── settings.json              # Hook 配置（Logger / Reviewer 触发 / Guardian）
├── skills/
│   ├── graphify/                  # 已有
│   └── auto-research/             # 人类入口
│       └── SKILL.md               # /auto-research start / status / kb-query
├── scripts/
│   ├── logger_hook.py             # PostToolUse 写入 logs/<loop_id>.jsonl
│   ├── guardian_check.py          # SessionStart baseline 校验
│   └── controller.py              # 可选：完全自主模式的外层 loop
├── knowledge/                     # 已有，KB 读写源
├── experiments/                   # 每轮 loop 产物（lineage / snapshots）
│   └── 2026-04-17-loop-001/
│       ├── plan.json
│       ├── translation.json
│       ├── diff.patch
│       ├── review_*.json
│       ├── metrics.json
│       └── analysis.md
└── CLAUDE.md
```

---

## 三、Coder 详细设计

### 3.1 角色拆分：orchestrator + executor + checker

Coder 内部拆成三个 subagent（`.claude/agents/` 下三个定义文件），职责单一、互不嵌套：

| Subagent | 定义文件 | 职责 | Tools |
|---|---|---|---|
| **coder-orchestrator** | `coder.md` | 外部入口；读 `tasks.json`、驱动 per-task 循环、维护 `status.json`、跑 smoke、最终 commit | Read, Write, Bash, Task |
| **coder-executor** | `coder-executor.md` | 实现**单个** task：改文件、跑该 task 的单元测试、返回 `{diff, test_log}` | Read, Edit, Write, Bash |
| **coder-checker** | `coder-checker.md` | 拿到 `{task_spec, diff, test_log}`，判断是否**真·实现了 spec**，抓"假测试 / hack" | Read only |

**为什么要 checker**：纯机械防御（`tasks.json` 只读、exit code 不可伪造）挡不住"测试能跑但逻辑错"这种 LLM reward-hacking 模式。checker 是专门的 skeptic，prompt 里强制质询：
- 这个 diff 解决的是 `task.spec` 说的问题吗？
- 测试是在验证业务逻辑，还是 `assert True == True`？
- 有没有新增 try/except 吞掉异常？
- 有没有 mock / monkey-patch 绕过真实路径？
- 变量名 / 函数名跟 spec 对齐吗？

### 3.2 生命周期（单次 Coder invocation）

```
orchestrator 入口
  │
  ▼
读 tasks.json（不可变）+ status.json + 可选的 review_issues
  │
  ▼
┌──── Per-task 循环（对每个 unit_test=false 的 task）────┐
│   attempt = 0                                         │
│   repeat (attempt < 3):                               │
│     attempt += 1                                      │
│     Task(executor, {task, prior_checker_concerns})    │
│       → {diff, unit_stdout, exit_code}                │
│     if exit_code != 0: continue                       │
│     Task(checker, {task_spec, diff, test_log})        │
│       → {verdict, concerns}                           │
│     if verdict == "real_impl":                        │
│        status.json: t.unit_test=true                  │
│        break                                          │
│     else: concerns 传给下一轮 executor                 │
│   若 3 次仍非 real_impl → exit(failed_task_retries)    │
└───────────────────────────────────────────────────────┘
  │
  ▼ 所有 task.unit_test == true
  │
  ▼
orchestrator 亲自跑 success_criteria.smoke_cmd
  │
  ├── exit == 0 → status.smoke_test=true, overall_complete=true
  │               git add -A && git commit
  │               写 coder_report (status=success)
  │               exit to Controller
  │
  └── exit != 0 → smoke_round += 1
                  if smoke_round > M (=2):
                     dump coder_failed_r<ctlr_round>.patch
                     exit(failed_smoke_retries)
                  else:
                     dump round_<smoke_round-1>/diff.patch
                     git reset --hard <base_commit>
                     status.tasks[*] 重置为 {unit_test:false, verdict:pending}
                     把上一轮 smoke_log 拼进 executor 的 extra_context
                     重跑 per-task 循环
```

**三个上限**（Coder 内部）：
- 单 task 的 executor+checker 自修：**3 次**
- smoke 自修（即 smoke_round 上限）：**M = 2**（首次 + 2 次重试 = 最多 3 次 smoke 尝试）
- Controller 层的 loop 总轮次 **N = 3** 是 Controller 的事，Coder 不感知

**失败不 commit**：worktree 最终 diff 落到 `coder_failed_r<ctlr_round>.patch`，Controller 决定是找 Reviewer 诊断还是中断整个 loop。

### 3.3 输入契约

Coder 被 Controller 调用时有两种 mode，但**复用同一个 orchestrator**（不拆成两个 subagent）。

**Mode A — 首次实现**：
```json
{
  "mode": "implement",
  "loop_id": "2026-04-17-loop-001",
  "controller_round": 1,
  "base_commit": "a1b2c3d",
  "tasks": [
    { "id": "t1", "op": "create", "path": "models/LSTM4REC.py", "spec": "..." },
    { "id": "t2", "op": "modify", "path": "train_model.py",    "spec": "..." }
  ],
  "success_criteria": {
    "smoke_cmd": "bash scripts/run.sh --epochs 1 --batch_size 64 --model lstm",
    "asserts": ["stdout 含 'hit@5'", "exit code == 0"]
  }
}
```

**Mode B — fixup（Reviewer 打回后）**：
```json
{
  "mode": "fixup",
  "loop_id": "...",
  "controller_round": 2,
  "base_commit": "a1b2c3d",
  "previous_commit": "e4f5g6h",
  "review_issues": [
    { "id": "i1", "severity": "error", "path": "...", "line_hint": 42, "issue": "..." }
  ],
  "tasks": [ ... ],
  "success_criteria": { ... }
}
```

**Mode B 语义**：orchestrator 检测 `review_issues` 非空时，
1. `status.json` 整体重置（上一轮的 true 字段被 Reviewer 证伪，不可信）
2. worktree `git reset --hard <base_commit>`
3. 跟 Mode A 进同一个循环，executor 的 `extra_context` 多带 `review_issues`

### 3.4 不变量 & `status.json` 规则

**`tasks.json` 只读**：Translator 产出，Coder 全家（orchestrator/executor/checker）一律不可写。

**`status.json` schema**：

```json
{
  "loop_id": "...",
  "controller_round": 1,
  "smoke_round": 0,
  "tasks_total": 3,
  "tasks": [
    { "id": "t1", "unit_test": true,  "verdict": "real_impl", "checker_rounds": 1 },
    { "id": "t2", "unit_test": false, "verdict": "pending",   "checker_rounds": 0 }
  ],
  "all_units_pass": false,          // derived: all(t.unit_test)
  "smoke_test": false,
  "overall_complete": false
}
```

**append-forward-only 规则**（orchestrator 每次写入前 self-validate，违反即 abort）：
- 字段单向 `false → true`；反向**仅**在跨 smoke_round 的**整体 reset** 时允许（批量重置，不是单字段翻回）
- `task.unit_test: false → true` 需同时满足 `executor.exit==0` AND `checker.verdict=="real_impl"`
- `smoke_test: false → true` 需 `all_units_pass==true` AND orchestrator 亲自跑 `smoke_cmd` 返回 exit 0
- `overall_complete: false → true` 需 `smoke_test==true`
- `tasks` 数组的长度和 `id` 集合必须与 `tasks.json` 一致，不允许增删

### 3.5 权限与作用域

| Subagent | Read 范围 | Write 范围 | Bash 允许 |
|---|---|---|---|
| orchestrator | `experiments/<loop_id>/**`，`knowledge/**`（只读参考） | `experiments/<loop_id>/{status.json, round_*/**, coder_report_r*.json, coder_failed_r*.patch}`；**禁写 `tasks.json`** | git（status / diff / reset --hard / add -A / commit / rev-parse / merge-base）+ `success_criteria.smoke_cmd` 原文；禁 push / checkout / rebase / force / clean -f / rm -rf / 网络 |
| executor | `experiments/<loop_id>/code/**`，`tasks.json`（只读） | `experiments/<loop_id>/code/**` only；**禁写 status.json / round_\*/ / tasks.json** | python、pytest（预留）、ls、cat；**禁 git / 网络 / rm -rf**（executor 不碰 git） |
| checker | `experiments/<loop_id>/code/**` + 本轮 executor 产物 json | — | — |

**实施手段**：
- Tool 级：`.claude/agents/<name>.md` frontmatter 的 `tools:` 字段显式列
- Bash / 文件路径级：PreToolUse Hook 调 `scripts/bash_allowlist.py`，按 subagent 名 + 命令 prefix + 路径 prefix 匹配 allowlist；不匹配即 deny
- worktree 创建 / 销毁：**Controller 负责**（Coder 入口时 worktree 已存在；退出后 worktree 保留，Controller 在 merge 或 abort 时清理）

### 3.6 输出：commit、报告、artifacts

#### commit message（只在 `status=success` 时发生，整个 invocation 只 commit 一次）

```
[loop-<loop_id>][ctlr-r<controller_round>][coder] <goal 前 60 字>

tasks: t1, t2, t3
smoke: pass (3.2s)
smoke_rounds: 1
checker_rejections: 2
base: a1b2c3d
```

第一行 `[loop-<id>][ctlr-r<n>][coder]` 是 Logger Hook 的正则锚点。

#### `experiments/<loop_id>/` 完整目录结构

```
experiments/<loop_id>/
├── plan.json                               ← Planner 产物（只读）
├── tasks.json                              ← Translator 产物（只读，Coder 不可写）
├── status.json                             ← Coder orchestrator 维护
├── coder_report_r<ctlr_round>.json         ← Coder 每次被调用后写一份
├── coder_failed_r<ctlr_round>.patch        ← 仅失败时写（worktree 最终 diff）
├── round_0/                                ← Coder 内部第 1 次 smoke 尝试
│   ├── task_<tid>_executor_a<k>.json
│   ├── task_<tid>_checker_a<k>.json
│   ├── smoke.log
│   └── diff.patch                          ← reset 前 dump
├── round_1/                                ← 第 2 次 smoke 尝试（reset 后重做）
├── round_2/
├── review_r<ctlr_round>.json               ← Reviewer 产物（Reviewer 设计时定）
├── metrics.json                            ← Runner 产物
├── analysis.md                             ← Analyzer 产物
└── code/                                   ← git worktree（分支 loop-<loop_id>）
```

#### `coder_report_r<ctlr_round>.json` schema

```json
{
  "loop_id": "2026-04-17-loop-001",
  "controller_round": 1,
  "mode": "implement",                       // implement | fixup
  "status": "success",                       // success | failed_task_retries | failed_smoke_retries | input_invalid
  "base_commit": "a1b2c3d",
  "head_commit": "e4f5g6h",                  // null if not committed
  "smoke_rounds_used": 1,                    // 0 = smoke 首次通过
  "tasks": [
    { "id": "t1", "final_verdict": "real_impl", "checker_rounds": 1, "executor_attempts": 1 },
    { "id": "t2", "final_verdict": "real_impl", "checker_rounds": 2, "executor_attempts": 2 }
  ],
  "failure": null,
  /* 若 status != success，failure 字段形如：
     {
       "smoke_round": 2,
       "failed_task_id": "t2",               // 仅 failed_task_retries
       "last_smoke_log_tail": "...",         // 仅 failed_smoke_retries
       "last_checker_concerns": [...]        // 仅 failed_task_retries
     }
  */
  "started_at": "2026-04-17T10:00:00Z",
  "finished_at": "2026-04-17T10:03:21Z"
}
```

### 3.7 与其他角色的接口（Coder 不负责但要对齐）

- **Translator → Coder**：Translator 产出 `tasks.json`（schema 同 3.3 Mode A 的 `tasks` + `success_criteria`），Coder 只读
- **Coder → Logger (Hook)**：Logger Hook 监听 PostToolUse(Bash) 里的 `git commit`，按 commit message 第一行正则解析 `loop_id` / `ctlr_round`，追加到 `experiments/<loop_id>/events.jsonl`
- **Coder → Controller**：Coder 退出时 stdout 返回 `coder_report_r<ctlr_round>.json` 路径；Controller 读 report 决定下一步
- **Coder ↔ Reviewer**：**Coder 不直接调 Reviewer**。Reviewer 两种 mode，由 Controller 按 Coder status 分派：
  - `review_commit`（`status=success`）：对比 `base..head` 做全量 review，产出 `{verdict, root_cause, issues, recommendation}`
  - `diagnose_failure`（`status=failed_*`）：读 `coder_report + coder_failed_r*.patch + tasks.json + plan.json`，指认 `root_cause: coder|translator|planner`，`recommendation: approve|coder_fixup|redo_translation|redo_planning|abort`

### 3.8 默认参数汇总

| 参数 | 默认值 | 说明 |
|---|---|---|
| 单 task 的 executor+checker 自修上限 | 3 | 超过则 `failed_task_retries` |
| smoke 自修上限 M | 2 | 意味着最多 3 次 smoke 尝试 |
| Controller loop 总轮次 N | 3 | Controller 维护，Coder 不感知 |
| checker 模型 | claude-opus-4-7 | skeptic 角色 |
| executor 模型 | claude-opus-4-7 | 代码生成主力 |
| orchestrator 模型 | claude-opus-4-7 | 流程驱动 |
