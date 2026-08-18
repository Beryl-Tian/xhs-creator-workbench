# Creator Baseline AI 蒸馏协议

## 目录

1. 目标与输入
2. 事实、推断与确认
3. 蒸馏步骤
4. 九类画像要求
5. Evidence 与置信度规则
6. Candidate JSON 契约
7. 自检清单

## 1. 目标与输入

把确定性数据底稿蒸馏成“博主本人 Baseline candidate”，用于后续选题、商业路线、大纲和发布文案。不要生成模仿博主的独立 Skill，不要生成 HTML，不要把候选画像标记为本人已确认。

必须完整读取：

- `distillation-task.json`
- 任务中 `normalized_notes_path` 指向的完整标准化笔记
- 任务中 `evidence_path` 指向的 Evidence
- `baseline-candidate.schema.json`

若任务状态为 `blocked_by_quality_gate`，停止蒸馏，展示质量警告并请求补采；不得绕过。

## 2. 事实、推断与确认

严格区分：

- `observed`：可以从公开文本或确定性统计直接验证。
- `inferred`：从多篇内容归纳出的解释，仍需本人或助理确认。
- `confirmed`：只有后续人工确认流程可以写入；AI candidate 不得使用。
- `rejected`：只有后续人工否定流程可以写入；AI candidate 不得使用。

不要把高频词自动称为价值观，不要把正文格式自动称为思维方式，不要把互动相关性解释成因果。没有证据就写入 `missing_dimensions`。

博主或助理明确提供的目标定位、目标人群属于后续人工校准，不进入 AI candidate，也不需要伪造公开 Evidence。它与“当前内容呈现出的定位、当前受众信号”并列保存。

## 3. 蒸馏步骤

1. 先读质量闸门、样本窗口和限制。
2. 逐篇阅读正文，建立 Note Evidence ID 对照；聚合数字只能辅助定位，不能代替原文。
3. 阅读 TOP10 与相对异常笔记，同时检查低表现或反例，不只看爆款。
4. 读取 `longitudinal`：用 `current` 定义当前身份，用 `historical_capability_candidates` 记录历史能力，用 `transition` 判断上升、稳定或回落；不得把历史能力直接写成当前支柱。
5. 先分析自然内容，再分析商业候选，最后比较二者差异。
6. 从评论中提取受众问题和理解偏差；不得恢复评论者身份。
7. 形成九类 findings，并为每条绑定真实 Evidence ID 和适用场景。
8. 主动寻找反证，写入 `counter_evidence_refs`。
9. 将不确定、没有覆盖或需要本人回答的事项分别写入 `limitations`、`missing_dimensions` 和 `human_review_questions`。
10. 只写 Candidate JSON 到任务指定的 `candidate_output`，再调用确定性 finalize 命令。

## 4. 九类画像要求

### 4.1 定位 `positioning`

- 一句话定位必须体现内容对象、主要价值和辨识度，不能复述简介。
- 提炼 2-5 个内容支柱；区分稳定支柱与偶发话题。
- 判断均为公开内容画像，不等同于博主私下身份。

使用 `finding_type`：`positioning`、`content_pillar`。

### 4.2 受众 `audience`

- 受众是谁、处于什么情境、希望解决什么问题。
- 评论能支持“受众常问什么”，但不能代表全部粉丝。
- 不根据昵称、头像或位置推断人口属性。

使用 `finding_type`：`audience_need`。

### 4.3 认知层 `cognition`

- 核心信念：必须在至少 3 篇不同笔记中复现；目标 3-8 条，但证据不足时宁缺毋滥。
- 观点张力：只记录真实存在的相反或情境化观点，至少 2 篇不同笔记；不为满足格式制造矛盾。
- 思维框架：回答博主如何解释问题，不是“喜欢反问开头”这类写作格式。
- 价值立场：必须有原文行为或判断支持，不能从高频词直接得出。

使用 `finding_type`：`core_belief`、`viewpoint_tension`、`mental_model`、`value_stance`。

### 4.4 策略层 `strategy`

- 固定系列、系列之间的关系与发布节奏。
- 热点或时效策略只在时间和内容证据充分时提炼。
- 运营判断必须标为 `inferred`，因为公开发布行为不等于本人策略说明。
- If-Then 决策只在跨多篇内容重复时提出。

使用 `finding_type`：`content_series`、`topical_strategy`、`operating_hypothesis`、`publishing_cadence`。

### 4.5 自然内容基因 `organic`

- 哪些选题、结构和表达构成非商业内容的稳定基线。
- 标题公式要给出可填空结构和原始标题证据，而不只是“数字型”。
- 开头、正文结构、情感弧线必须从完整正文归纳。
- 不把单篇爆款特征称为稳定公式。

使用 `finding_type`：`title_formula`、`opening_pattern`、`body_structure`、`emotional_arc`。

### 4.6 商业内容基因 `commercial`

- TikHub 文本标记产生的只是商业候选；candidate 中必须重复声明需人工确认。
- 分析产品如何进入叙事、卖点密度、体验证据、品牌信息与本人表达的连接方式。
- 比较自然内容与商业候选在标题、开头、结构、语气、互动数据上的差异。
- 提炼“商业大纲必须保留什么”与“什么表达容易出戏”。
- 商业类 confidence 上限由引擎限制为 0.65，直到人工确认笔记属性。

使用 `finding_type`：`commercial_integration`、`commercial_difference`。

### 4.7 语言与互动 `voice`

- 语言 DNA：高频用语、力量短语、句式节奏、人称策略、对话感。
- CTA：类型、位置、典型原文和使用条件。
- 评论回复风格只能基于已采集到的作者回复。

使用 `finding_type`：`language_dna`、`cta_pattern`、`tag_strategy`。

### 4.8 视觉 `visual`

- Emoji 和文本排版不等于封面、画面或镜头分析。
- 当前没有图片/视频视觉证据时，必须生成 `unknown_visual`，引用本 Run 的 `collection_quality` Evidence 并明确缺失；不得补写构图、色彩或镜头规律。

### 4.9 创作护栏 `guardrail`

- `must_keep`：进入商业大纲仍必须保留的本人特征。
- `avoid`：有重复反例或明显内容差异支持的出戏风险。
- “样本中零次出现”只能作为弱信号，不能单独证明本人绝不使用。
- 护栏要注明适用于路线、大纲、发布文案还是复审。

## 5. Evidence 与置信度规则

- 除 `unknown_visual` 外，所有 finding 至少引用一个 Note Evidence；仅引用评论不够。`unknown_visual` 必须引用 `collection_quality` Evidence。
- `core_belief` 至少引用 3 篇不同笔记。
- `viewpoint_tension` 至少引用 2 篇不同笔记。
- 稳定内容模式和商业差异通常至少引用 2 篇不同笔记。
- 反证存在时必须写入 `counter_evidence_refs`；没有反证可写空数组。
- 少于 20 篇样本时 confidence 最高 0.65；20-49 篇最高 0.8；50 篇以上最高 0.9。
- AI 推断最高 0.85；商业候选最高 0.65。finalize 会再次执行上限。
- `applicable_to` 只能使用 Schema 允许的场景，避免把描述性结论错误用于所有下游任务。

## 6. Candidate JSON 契约

输出必须是单个 JSON 对象，不要使用 Markdown 围栏：

```json
{
  "schema_version": 1,
  "creator_id": "creator_...",
  "run_id": "run_...",
  "summary": {
    "one_line_positioning": {"statement": "...", "evidence_refs": ["ev_...", "ev_...", "ev_..."], "limitations": []},
    "audience": {"statement": "...", "evidence_refs": ["ev_..."], "limitations": ["评论样本有限"]},
    "content_identity": {"statement": "...", "evidence_refs": ["ev_...", "ev_...", "ev_..."], "limitations": []},
    "commercial_identity": {"statement": "...", "evidence_refs": ["ev_...", "ev_..."], "limitations": ["商业属性待确认"]}
  },
  "findings": [
    {
      "category": "cognition",
      "finding_type": "core_belief",
      "statement": "...",
      "epistemic_status": "inferred",
      "confidence": 0.72,
      "evidence_refs": ["ev_...", "ev_...", "ev_..."],
      "counter_evidence_refs": [],
      "applicable_to": ["commercial_route", "commercial_outline"],
      "limitations": ["只在当前采样窗口观察到"]
    }
  ],
  "missing_dimensions": ["没有图片与镜头证据"],
  "human_review_questions": ["这些商业候选是否都是已报备合作？"],
  "limitations": ["公开发布内容不等于本人全部真实想法"]
}
```

## 7. 自检清单

- 是否把账号画像写成了任何博主都适用的通用话术？
- 每条核心信念是否真的跨 3 篇不同笔记？
- 是否区分了认知框架与写作格式？
- 是否先分析自然内容，再比较商业候选？
- 商业候选是否明确等待人工确认？
- 是否引用了低表现、例外或反证？
- 是否把 Emoji 排版误称为视觉风格？
- 是否从“没有出现”推断了绝对禁区？
- 是否把相关性写成因果？
- 是否留下了具体、可回答的人工确认问题？
