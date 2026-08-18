# 领域模型与术语

状态：阶段 0 已通过；阶段 2 对 Baseline 字段补充

## 1. 核心术语

### Creator

被持续服务的博主。Creator 是身份容器，不直接保存某一时刻的分析结论。

### Baseline

某个时间点对 Creator 的版本化创作模型。它包含定位、受众、认知层、策略层、自然内容基因、商业内容基因、语言、视觉缺口、护栏、证据引用和置信度。

Baseline 不是原始数据，也不是 HTML 报告。

AI 首次蒸馏产生的 Baseline 状态为 `pending_confirmation`。只有后续人工确认记录能让它成为可默认用于项目的稳定 Baseline。

### Evidence

支持事实或判断的证据单元，例如一篇笔记、一条评论、一段口播、一次人工确认、一次品牌反馈或一份最终发布内容。

### Project

一次具体内容合作的容器。它把 Brief、路线、大纲版本、品牌审核、发布文案、最终口播脚本、实际发布配文和学习候选串在一起。

### Brief

品牌输入的结构化表达。它同时保存原始文件引用、提取文本、明确事实、推断和待确认项。

### Content Route

在写详细大纲之前提出的内容策略方向。路线描述“为什么这样讲”，而不是完整脚本。

### Outline

某条 Content Route 下的版本化内容设计。默认沿用旧 scripts-agent 的 7 段分镜骨架，每段逐行保存秒数、镜头、大致口播、花字、品牌露出和约束覆盖情况；Brief 明确要求其他结构时可调整段数。

### Brand Submission

助理实际提交给品牌方的不可修改快照。大纲提交和发布文案提交属于两条独立版本链。

### Brand Feedback

品牌针对某个 Brand Submission 给出的原始意见和结构化修改项。它首先属于品牌、品类或项目经验，不属于 Creator 稳定规律。

### Approved Outline

品牌明确确认的某次大纲 Submission。它是后续博主创作和最终口播脚本对比的基准。

### Publication Copy

大纲确认后提供给品牌审核的标题、正文和 Tags。它有自己的草稿、提交、反馈和确认版本。

### Approved Publication Copy

品牌明确确认的标题、正文和 Tags 快照。它是实际发布配文对比的基准。

### Final Publication Bundle

项目发布后的归档组合，至少包含最终口播脚本和实际发布配文。它们是项目事实，不天然代表长期规律。

### Internal Feedback

助理针对内部 Outline 或 Publication Copy 版本给出的原始修改意见。必须原样保留，并关联修改前后的版本。它与品牌方针对 Submission 的 Brand Feedback 分开保存。

### Learning Candidate

从品牌审核、最终内容差异、人工反馈或发布结果中提炼出的候选经验。它在被确认或验证前不能进入稳定 Baseline。

### Benchmark Snapshot

对标博主在特定采样窗口内的只读分析快照。它不是主博主 Baseline。

### Run

一次命令或工作流执行记录，保存输入、输出、步骤状态、错误和恢复点。
`waiting_for_agent` 表示确定性命令已结束、等待宿主 AI 按任务契约继续；`waiting_for_user` 只用于真正的人工确认闸门。

### Workbench

供人查看的静态 HTML 投影。Workbench 不拥有业务事实。

## 2. 关系图

```text
Creator
  ├── Baseline v1
  ├── Baseline v2
  └── Project
        ├── Brief
        ├── Baseline Snapshot Reference
        ├── Content Route 1..n
        ├── Outline v1..n
        ├── Outline Brand Submission 0..n
        ├── Outline Brand Feedback 0..n
        ├── Approved Outline 0..1
        ├── Publication Copy v1..n
        ├── Copy Brand Submission 0..n
        ├── Copy Brand Feedback 0..n
        ├── Approved Publication Copy 0..1
        ├── Final Publication Bundle 0..1
        └── Learning Candidate 0..n

Evidence
  ├── supports Baseline Claim
  ├── supports Content Route
  └── supports Learning Candidate

Benchmark Snapshot
  └── informs Content Route, but never mutates Baseline directly
```

## 3. 对象最小字段

### Creator

| 字段 | 说明 |
|---|---|
| `creator_id` | 稳定内部 ID，不使用昵称作主键 |
| `display_name` | 当前显示名 |
| `platform_accounts` | 平台、账号 ID、主页地址 |
| `is_primary` | 是否为当前默认主博主 |
| `created_at` | 创建时间 |

### Baseline

| 字段 | 说明 |
|---|---|
| `baseline_id` | 版本 ID |
| `creator_id` | 所属博主 |
| `source_run_id` | 本版本对应的采集与蒸馏 Run |
| `version` | 单调递增版本 |
| `review_status` | 待确认、已确认、已拒绝或已取代 |
| `sample_window` | 数据采样范围 |
| `summary` | 四项有 Evidence 的定位摘要 |
| `sections` | 九类画像对应的 Claim ID |
| `claims` | 带认识状态、证据、反证、置信度、适用范围与限制的结论 |
| `missing_dimensions` | 样本没有覆盖的维度 |
| `human_review_questions` | 需要助理或本人确认的问题 |
| `source_candidate_ids` | 本版本吸收的候选规律 |
| `created_at` | 生成时间 |

### Evidence

| 字段 | 说明 |
|---|---|
| `evidence_id` | 稳定 ID |
| `creator_id` | 归属博主 |
| `kind` | profile/collection-quality/note/comment/transcript/oral-script/published-copy/brand-feedback/human-confirmation/performance |
| `source_id` | 平台内容 ID 或本地内容 ID |
| `captured_at` | 采集时间 |
| `published_at` | 原内容发布时间，可为空 |
| `content_excerpt` | 最小必要摘录 |
| `metrics` | 当时采集到的互动指标 |
| `source_ref` | 原始记录位置 |
| `quality` | 完整性和可用性 |

### Project

| 字段 | 说明 |
|---|---|
| `project_id` | 稳定 ID |
| `creator_id` | 服务的博主 |
| `title` | 人类可读项目名 |
| `brand` / `product` | 品牌与产品 |
| `workflow_state` | 多轨状态：outline、publication_copy、creator_production、publication、archive |
| `baseline_id` | 项目创建时绑定的 Baseline |
| `created_at` / `updated_at` | 时间 |

`workflow_state` 不使用单个线性状态，因为大纲确认后，博主创作与发布文案品牌审核可能并行：

```json
{
  "outline": "approved",
  "publication_copy": "brand_review",
  "creator_production": "in_progress",
  "publication": "not_published",
  "archive": "incomplete"
}
```

### Brief

| 字段 | 说明 |
|---|---|
| `brief_id` | 稳定 ID |
| `project_id` | 所属项目 |
| `source_files` | 原始文件及摘要 |
| `brand` / `product` | 品牌与产品 |
| `platform` / `deliverable` | 平台和交付物 |
| `audience` / `pain_points` | 受众和问题 |
| `selling_points` | 卖点列表 |
| `must_include` / `forbidden` | 硬约束 |
| `scene` / `campaign` / `deadline` | 场景和节点 |
| `facts` | 原文明确事实 |
| `inferences` | 系统推断及置信度 |
| `open_questions` | 待确认问题 |

### Content Route

| 字段 | 说明 |
|---|---|
| `route_id` | 稳定 ID |
| `project_id` | 所属项目 |
| `premise` | 一句话内容命题 |
| `conflict` | 核心矛盾或张力 |
| `scene` | 内容发生场景 |
| `emotional_arc` | 情绪路径 |
| `product_role` | 产品如何进入叙事 |
| `creator_fit` | 博主适配理由及证据 |
| `brief_coverage` | Brief 覆盖结果 |
| `risks` | 主要风险 |
| `recommended` | 是否为系统推荐 |

### Outline

| 字段 | 说明 |
|---|---|
| `outline_id` | 稳定 ID |
| `project_id` / `route_id` | 所属项目和路线 |
| `version` | 版本号 |
| `working_titles` / `hooks` | 选题名、暂定标题和开头候选；正式发布标题属于 Publication Copy |
| `estimated_duration_seconds` | 各段秒数相加得到的预计总时长范围 |
| `sections` | 顺序对应的段落名称、秒数、目标、镜头、大致口播、花字和品牌露出 |
| `brief_coverage` | 硬约束覆盖矩阵 |
| `creator_fit_checks` | 人设适配检查 |
| `assumptions` | 本版假设 |
| `created_from_feedback_id` | 触发本版的反馈，可为空 |

### Brand Submission

| 字段 | 说明 |
|---|---|
| `submission_id` | 稳定 ID |
| `project_id` | 所属项目 |
| `track` | outline / publication_copy |
| `round` | 对外提交轮次，如 S1 或 C1 |
| `source_object_id` | 对应 Outline 或 Publication Copy 版本 |
| `submitted_content` | 品牌真正收到的快照 |
| `source_file` | 可选的品牌模板文件及摘要 |
| `submitted_at` | 提交时间 |

### Brand Feedback

| 字段 | 说明 |
|---|---|
| `feedback_id` | 稳定 ID |
| `project_id` / `submission_id` | 所属项目和目标 Submission |
| `raw_sources` | 粘贴文本、批注文档或截图 |
| `items` | 位置、要求、类型和歧义状态 |
| `resolution_status` | 每条意见的处理结果 |
| `received_at` | 收到时间 |

### Approval

| 字段 | 说明 |
|---|---|
| `approval_id` | 稳定 ID |
| `project_id` / `submission_id` | 所属项目和被确认 Submission |
| `track` | outline / publication_copy |
| `approved_at` | 确认时间 |
| `confirmation_source` | 确认方式或来源 |
| `note` | 助理备注 |

### Publication Copy

| 字段 | 说明 |
|---|---|
| `copy_id` | 稳定 ID |
| `project_id` | 所属项目 |
| `version` | 版本号 |
| `approved_outline_id` | 生成依据 |
| `title_options` | 标题候选；提交快照需明确实际提交项 |
| `body` | 小红书正文 |
| `tags` | Tags 列表 |
| `brief_coverage` | 必提、禁用词和活动信息检查 |
| `created_from_feedback_id` | 触发本版的品牌反馈，可为空 |

### Final Publication Bundle

| 字段 | 说明 |
|---|---|
| `bundle_id` | 稳定 ID |
| `project_id` | 所属项目 |
| `oral_script_source` | 最终口播脚本原件及摘要 |
| `oral_script` | 标准化口播脚本 |
| `published_copy_source` | 实际发布配文原件及摘要 |
| `published_title` / `published_body` | 实际标题与正文 |
| `published_tags` | 实际 Tags |
| `approved_outline_diff` | 确认大纲到最终口播脚本的差异 |
| `approved_copy_diff` | 确认文案到实际发布配文的差异 |
| `published_at` / `published_url` | 可选发布时间和链接 |
| `completeness` | partial / complete |

### Learning Candidate

| 字段 | 说明 |
|---|---|
| `candidate_id` | 稳定 ID |
| `creator_id` / `project_id` | 归属范围 |
| `scope` | project-only / commercial / organic / global |
| `statement` | 候选规律 |
| `reason` | 为什么提出 |
| `evidence_refs` | 支持证据 |
| `counter_evidence_refs` | 反例证据 |
| `confidence` | 置信度 |
| `status` | proposed/accepted/rejected/promoted/superseded |
| `review_note` | 人工结论 |

## 4. 关键不变量

1. 昵称变化不能改变 `creator_id`。
2. 历史 Project 始终引用创建时的 `baseline_id`。
3. Workbench 文件不能作为唯一事实源。
4. 每个 Outline 版本不可被覆盖，只能创建下一版本。
5. Internal Feedback 必须关联内部版本；Brand Feedback 必须关联它针对的 Submission。
6. Brand Submission 一旦创建不可覆盖；真正提交内容与内部源版本必须分别保留。
7. 大纲与发布文案拥有独立的 Submission、Feedback 和 Approval 链。
8. Approved Outline 与 Approved Publication Copy 不可被后续草稿覆盖。
9. Final Publication Bundle 必须保留最终口播脚本和实际发布配文的原件摘要。
10. Learning Candidate 不能在 `proposed` 状态下进入 Baseline。
11. Brand Feedback 默认不能直接进入 Creator Baseline。
12. Benchmark Snapshot 不能直接写入本人 Baseline。
13. AI 推断必须与原文事实分栏保存。
14. 所有外部采集指标必须保留采集时间。
15. Project 的整体展示状态由多轨状态推导，不能反过来覆盖任一轨道。

## 5. 需要后续 Schema 明确的问题

- 多附件 Brief 的覆盖与冲突规则。
- 发布表现数据的统一观察窗口。
- 实际发布配文发生临时修改时，如何记录修改来源。
- 图片类品牌反馈的 OCR 和人工校验方式。
