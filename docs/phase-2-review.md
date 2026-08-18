# 阶段 2 Review 清单

状态：已通过

本阶段验收：`公开采集 → 标准化 Evidence → 确定性数据底稿 → AI 三层画像蒸馏 → Evidence/规则校验 → pending_confirmation Baseline`。没有调用真实账号，没有生成 HTML，也没有进入 Brief 与大纲功能。

## 已交付

- TikHub 小红书 App V2 的主页、笔记详情与评论分页采集
- 评论入库前去标识；不落盘 API 原始响应、头像或媒体
- distiller 确定性指标：TOP10、话题/内容形态候选、阶段变化、标题模式与长度、开头/结尾、CTA、正文结构、观点句、高频表达、Emoji 文本排版、发布节奏、藏赞比、相对异常表现
- 自然内容与商业候选分组及对比底稿；商业属性仍需人工确认
- 质量闸门：至少 10 篇有效笔记，详情成功率和内容完整率均不低于 80%
- 独立 AI 蒸馏协议：定位、受众、认知、策略、自然内容、商业内容、语言、视觉缺口、创作护栏
- Candidate 与 Baseline Schema；摘要和所有 Claim 都必须引用 Evidence
- 核心信念至少跨 3 篇笔记，观点张力至少跨 2 篇，稳定模式通常至少跨 2 篇
- 反证、适用场景、限制、缺失维度和人工确认问题
- 样本量、AI 推断与商业候选的置信度硬上限
- Candidate 校验失败可原地修订重试，不重新采集
- Baseline 版本不可覆盖，初始状态固定为 `pending_confirmation`
- 稳定 Creator ID、原子 JSON 写入、Run 恢复记录和 Registry

## 与旧 distiller 的关系

保留并升级：

- “脚本保下限、AI 冲上限”的两层结构
- 认知层、策略层、内容层
- 标题、正文、语言 DNA、CTA、节奏和 Evidence 要求
- 核心信念跨笔记验证与局限性自检

不迁移：

- 已下线接口 fallback、自动 `git pull`、交互安装、命令行 Token
- 每个博主生成独立模仿 Skill
- 没有证据的因果推断、绝对禁区和视觉规律

新增加：

- 本人自然内容与商业内容基因分离
- 商业大纲适用范围、必须保留项和出戏风险
- `observed / inferred / confirmed / rejected` 认识状态
- Counter Evidence 与人工确认问题

## 私有落盘结构

```text
.xhs-agent/
├── registry.json
├── runs/<run-id>.json
└── creators/<creator-id>/
    ├── creator.json
    ├── source/runs/<run-id>/
    │   ├── profile.json
    │   ├── notes.json
    │   ├── analysis.json
    │   ├── distillation-task.json
    │   ├── baseline-candidate.json
    │   └── baseline-candidate.validated.json
    ├── evidence/<run-id>.json
    └── baselines/<baseline-id>.json
```

## 建议重点 Review

1. 是否接受 10 篇与 80% 完整度的正式蒸馏最低闸门。
2. 是否接受核心信念必须有 3 篇不同笔记，其他稳定规律通常至少 2 篇。
3. 是否接受 Baseline 第一次生成只能是 `pending_confirmation`，阶段 3 再通过 HTML 完成人工确认。
4. 是否接受商业笔记继续作为候选，商业结论置信度最高 0.65。
5. 是否接受没有媒体 Evidence 时强制生成 `unknown_visual`，而不是把 Emoji 当视觉风格。
6. 是否接受 AI 输出必须经过第二条 `baseline-finalize` 命令才能成为版本化 Baseline。
7. 是否接受不保留 TikHub 原始响应带来的隐私收益与接口排错成本。

## 本地验收命令

```text
PYTHONPATH=src pytest -q
python3 scripts/validate_schemas.py
python3 scripts/check_privacy.py
python3 packages/xhs-creator-workbench/scripts/run_xhs_agent.py info --json
```

真实账号冒烟测试需要本机 Token 和明确账号，本 Review 前不会自动执行。

## Review 结论格式

回复“阶段 2：通过，继续”，或列出需要修改的编号和内容。在通过前不进入 Workbench HTML。
