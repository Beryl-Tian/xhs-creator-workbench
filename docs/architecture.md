# MVP 架构与仓库边界

状态：阶段 0、1 已通过；阶段 2 待 Review

## 1. 架构目标

- 助理只需要 Codex 对话和 `workbench/`。
- AI 负责高自由度判断，脚本负责可重复、可验证的操作。
- 事实层与展示层分开，HTML 可以随时重建。
- Skill 保持精简，按任务渐进读取协议，不把所有业务知识一次装入上下文。
- 旧项目按能力迁移，不按原目录复制。

## 2. 四层结构

```text
用户层       Codex 对话 + workbench HTML
编排层       Skill 入口 + 任务协议
应用层       Python CLI + 领域服务
数据层       .xhs-agent 事实库 + 原始附件
```

### 用户层

负责发起任务、阅读、选择路线、反馈和确认。HTML 只读；交互状态通过 Codex 回写。

### 编排层

Skill 判断用户意图，读取对应协议并调用稳定命令。Skill 不实现采集、统计或文件格式解析。

### 应用层

Python 引擎执行采集、校验、版本、差异、索引、渲染和运行恢复。AI 产出的结构化内容也必须经 Schema 校验后落盘。

### 数据层

保存原始证据、版本化领域对象、Run 和缓存。Workbench 由数据层投影生成。

## 3. 目标仓库结构

```text
xhs-creator-workbench/
├── README.md                       # 面向安装者的仓库说明
├── AGENTS.md                       # 仓库开发和执行约束
├── pyproject.toml
├── docs/                           # 产品设计与开发决策，不打包进 Skill
├── packages/
│   └── xhs-creator-workbench/      # 可安装 Skill 包
│       ├── SKILL.md
│       ├── agents/openai.yaml
│       ├── references/             # 按任务渐进读取的协议
│       │   ├── creator-baseline.md
│       │   ├── brief-to-outline.md
│       │   ├── archive-final.md
│       │   └── benchmark.md
│       ├── scripts/                # 调用已安装 CLI 的薄入口
│       └── assets/                 # HTML 模板和静态资产
├── src/
│   └── xhs_agent/                  # 确定性运行引擎
│       ├── cli.py
│       ├── creator/
│       ├── brief/
│       ├── outline/
│       ├── archive/
│       ├── benchmark/
│       ├── integrations/
│       ├── renderers/
│       └── common/
├── schemas/                        # JSON Schema；AI 与引擎共用
├── scripts/                        # 环境检查、迁移、验证等维护入口
├── tests/
├── .xhs-agent/                     # 本机事实与运行状态，默认不提交
└── workbench/                      # 人类可见 HTML，默认不提交
```

`packages/xhs-creator-workbench/` 是可安装 Skill 的源码边界。这样可以保持 Skill 自包含和精简，同时让 repo 的测试、产品文档和 Python 工程不会被当成 Skill 上下文。

## 4. Skill 与运行引擎的职责

### Skill 负责

- 识别本人分析、写大纲、归档和对标意图
- 决定本次需要读取哪个 reference
- 收集缺失但不可安全推断的信息
- 调用 CLI
- 读取 CLI 产生的 AI Task Contract
- 生成需要创作判断的结构化内容
- 调用校验和渲染命令
- 在阶段性结果后等待用户反馈

### Python 引擎负责

- TikHub 和平台接口
- 文档文本提取
- 原始文件保存和摘要
- 确定性统计与质量报告
- ID、版本和索引
- JSON Schema 校验
- 大纲、发布文案、品牌提交、反馈和确认的独立版本链
- Approved Outline 到最终口播脚本的差异计算
- Approved Publication Copy 到实际发布配文的差异计算
- Run 状态和恢复点
- HTML 渲染
- 隐私过滤和日志脱敏

### 不允许的边界穿透

- Skill 不手写或覆盖内部索引。
- HTML JavaScript 不直接修改 `.xhs-agent/`。
- Renderer 不生成新的业务判断，只展示已保存事实。
- 采集器不直接更新 Baseline。
- 归档动作不自动 Promote 候选规律。

## 5. 本地数据结构

```text
.xhs-agent/
├── registry.json
├── creators/<creator-id>/
│   ├── creator.json
│   ├── baselines/<baseline-id>.json
│   ├── evidence/
│   ├── learning-candidates.json
│   └── raw/
├── projects/<project-id>/
│   ├── project.json
│   ├── brief/
│   ├── routes/
│   ├── outlines/
│   ├── brand-review/
│   │   ├── outline-submissions/
│   │   ├── outline-feedback/
│   │   ├── copy-submissions/
│   │   ├── copy-feedback/
│   │   └── approvals/
│   ├── publication-copy/
│   ├── published/
│   └── learnings/
├── benchmarks/<snapshot-id>/
├── runs/<run-id>.json
├── cache/
└── logs/
```

以下内容默认加入 `.gitignore`：

- `.xhs-agent/`
- `workbench/`
- `.env`
- Token、原始 Brief 和可能包含个人信息的附件

TikHub Token 保存到环境变量或用户级配置，不进入 repo：

```text
~/.config/xhs-agent/config.json
```

## 6. Workbench 投影

```text
workbench/
├── index.html
├── assets/                         # 离线 CSS 和少量增强 JS
├── creators/<creator-id>/
│   ├── index.html
│   └── baselines/<baseline-id>.html
├── projects/<year>/<project-slug>/
│   ├── index.html
│   ├── brief.html
│   ├── routes.html
│   ├── outline-v1.html
│   ├── brand-review.html
│   ├── publication-copy.html
│   └── final.html
├── benchmarks/
└── exports/
```

页面路径可使用易读 slug，但所有关联必须依赖稳定 ID，不能依赖文件夹名。

阶段 3 首先实现 Creator 和 Baseline 页面；Project 与 Benchmark 页面分别随对应业务阶段加入。页面不依赖 CDN、前端构建工具或本地服务器，可以通过 `file://` 直接打开。生成文件清单保存在 `.xhs-agent/cache/workbench-manifest.json`，不把机器状态混入面向人的 `workbench/`。

Baseline 页面固定展示：

- 待确认状态和人工问题
- 四项带 Evidence 的画像摘要
- 样本与核心数据指标
- 自然内容与商业内容对照
- 九类 Claims、置信度、适用范围、限制、支持证据和反证
- 缺失维度与分析边界

Workbench 只提供阅读、搜索、折叠证据和打印，不提供审核表单。人工反馈仍通过 Codex 对话写入结构化对象。

## 7. 数据流

### Baseline

```text
TikHub → Normalized Evidence → Deterministic Analysis Substrate
       → AI Task Contract → AI Structured Findings
       → Evidence/Schema Validation → Pending Baseline Version → Human Review → HTML
```

### Brief、大纲与品牌审核

```text
Brief File → Extracted Text → Structured Brief
           → Baseline Snapshot + Historical Evidence
           → Routes → Selected Route → Outline Version → HTML
           → Outline Submission → Brand Feedback → Revised Outline
           → Approved Outline
```

### 发布文案

```text
Approved Outline → Title + Body + Tags → Publication Copy Version
                 → Copy Submission → Brand Feedback
                 → Approved Publication Copy
```

### 外部创作、归档与学习

```text
Approved Outline → Creator writes oral script and shoots outside system
Final Oral Script → Approved Outline Diff ┐
Actual Published Copy → Approved Copy Diff ├→ Learning Candidates
                                           → User Review
                                           → Explicit Baseline Update
```

## 8. 旧项目迁移映射

| 旧能力 | 新位置 | 迁移策略 |
|---|---|---|
| TikHub Client 与旧 endpoint fallback | `integrations/` | 仅迁移稳定客户端逻辑；旧接口已下线，改为 App V2 单一路径并补边界测试 |
| 小红书采集 | `creator/collector` | 统一输出 Evidence，不直接写报告 |
| 确定性统计 | `creator/analyzer` | 拆开统计与 AI 提示生成 |
| 深度蒸馏任务 | Skill reference + Task Contract | 删除巨型输出模板，改结构化契约 |
| Brief Intake | `brief/` | 扩展事实、推断、问题三分法 |
| 硬编码品类路由 | `outline/` | 降级为历史模式检索，不作为唯一规则 |
| Review Server | 不迁移 | 使用静态 HTML + Codex 对话反馈 |
| 定稿 Skill 文件 | Learning Candidate | 不再每稿生成独立 Skill；按来源区分品牌与博主经验 |
| Archives | Project Import | 保留原文件，转成项目事实 |

## 9. 运行接口方向

CLI 面向 Skill 保持稳定，具体参数在阶段 1 确定：

```text
xhs-agent creator analyze
xhs-agent creator baseline-finalize
xhs-agent creator show
xhs-agent project create
xhs-agent brief import
xhs-agent routes generate
xhs-agent outline generate
xhs-agent outline revise
xhs-agent brand submit
xhs-agent brand feedback
xhs-agent brand approve
xhs-agent copy generate
xhs-agent published archive
xhs-agent learning review
xhs-agent baseline promote
xhs-agent workbench build
```

每个命令至少支持机器可读输出，并返回：

- `run_id`
- 当前状态
- 产生的对象 ID
- 下一步建议
- 错误码与可恢复信息

## 10. 阶段边界

- 阶段 1 只搭骨架、Schema 和空流程，不接 TikHub。
- 阶段 2 跑通 Baseline 事实链。
- 阶段 3 才实现 Workbench 页面。
- 阶段 4 已实现 Brief、大纲、品牌审核和发布文案，等待用户 Review。
- 阶段 5 正在实现最终口播脚本、实际发布配文归档与候选学习。
- 阶段 6 使用真实项目端到端验收。
- 阶段 7 再加入对标分析。
