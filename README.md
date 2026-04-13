# RecAgent

推荐模型超参数调优的团队知识库，由 AI Agent 驱动。

## 目录结构

```
RecAgent/
├── knowledge/          # 团队知识库（人工维护）
│   ├── wiki/           # 经验文章：架构、超参数、训练方法、故障排查
│   ├── hp_rules/       # 结构化调参规则（YAML，供 Agent 直接解析）
│   └── paper_insights/ # 论文提炼（每篇论文一个文件）
├── graphify-out/       # 知识图谱（由 /graphify 自动生成，勿手动修改）
├── skills/             # AI Agent Skill 定义
├── templates/          # 实验配置模板
├── tools/              # 共享工具脚本（Claude Code 状态栏等）
├── CLAUDE.md           # Agent 行为约定
└── private/            # 个人工作区（.gitignore，不提交，按需自行创建）
```

> 当前仓库是初始骨架：`knowledge/` 下文件已建好但内容待填充，`graphify-out/` 首次运行 `/graphify` 后才会生成 `graph.html` / `graph.json`。

## 状态栏

仓库自带 `.claude/settings.json`，克隆后用 Claude Code 打开即生效，状态栏会显示：
`ctx XX%  5h:XX%  7d:XX%`（当前上下文用量 / 5小时 / 7天 API 用量）。

个人化配置请写到 `.claude/settings.local.json`（已 gitignore），**不要**动仓库里那份。

---

## 已集成 Skills


| Skill                                | 作用                                                                                  | 来源                                                                                      | 装法                                                          |
| ------------------------------------ | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| [graphify](skills/graphify/SKILL.md) | 把 `knowledge/` 下的 Markdown / YAML 聚合成可查询的知识图谱，支持 `query` / `explain` / `path` 三类图检索 | [safishamsi/graphify](https://github.com/safishamsi/graphify)                           | 仓库自带                                                        |
| superpowers                          | Jesse Vincent 的核心 skills 套件：TDD、系统化 debug、头脑风暴、写/执行计划、子代理并行、代码审查等 20+ 个 skill       | [obra/superpowers](https://github.com/obra/superpowers)（通过 Anthropic 官方 marketplace 分发） | 需自行运行 `/plugin install superpowers@claude-plugins-official` |


> `.claude/settings.json` 里的 `enabledPlugins` 已声明本项目启用 superpowers——克隆后如未安装，Claude Code 会提示装。

---

## 知识库使用

### 浏览知识

`knowledge/wiki/` 是 Obsidian 兼容的 Markdown 文章库，可以直接用 Obsidian 打开整个 `knowledge/` 目录浏览（当前为空骨架，内容持续沉淀中）。

### 查询知识图谱

```
/graphify query "lr 和 batch size 的关系"
/graphify explain "SeqTransformer"
/graphify path "learning_rate" "warmup"
```

### 重建知识图谱

`knowledge/` 有新内容时运行（**本项目固定带路径**，不要用 `/graphify` 或 `/graphify .`）：

```
/graphify ./knowledge
```

输出到 `graphify-out/`（`graph.html` 可交互可视化，`graph.json` 供 Agent 检索）。

## 贡献知识


| 内容类型                | 放在哪里                                       |
| ------------------- | ------------------------------------------ |
| 调参经验、架构笔记、故障记录      | `knowledge/wiki/<topic>/`                  |
| 可量化的调参规则（参数范围、缩放公式） | `knowledge/hp_rules/`                      |
| 论文洞察                | `knowledge/paper_insights/YYYY-<topic>.md` |


通过 PR 合入，合入后重建知识图谱。

## 个人工作区

在 `private/` 下创建自己的目录（已被 `.gitignore` 排除）：

```
private/<your-name>/
├── experiments/    # 实验记录
├── notes/          # 个人笔记
└── bookmarks/      # 收藏的论文和配置
```

私有实验中沉淀的有价值洞察，可通过 PR 提升到 `knowledge/` 共享给团队。