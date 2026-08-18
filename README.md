# 小红书创作工作台

把「了解博主 → 消化 Brief → 生成大纲 → 品牌审核 → 发布归档 → 沉淀经验」放进一个可追溯的本地工作流。

这是一个面向博主助理和内容团队的 Codex Skill。你主要通过 Codex 对话发起任务，通过本地 Workbench 阅读完整结果；不需要手工编辑 JSON，也不需要启动网页服务。

> 当前状态：**P0 MVP 主闭环已完成**，并已用一个真实、已发布的商业合作项目完成回放式端到端验收。对标博主分析和发布后数据回采暂未开放。

## 它能完成什么

- 分析博主公开笔记，建立带证据、置信度和版本记录的 Creator Baseline
- 将已确认的 Baseline 转成可直接指导选题、路线和大纲的 Creator Playbook
- 导入 Markdown、TXT、PDF、DOCX 或 XLSX 品牌 Brief，识别硬约束和待确认项
- 结合 Brief、Baseline、Playbook 和历史证据生成内容路线与分镜大纲
- 分别管理大纲和发布文案的提交快照、品牌反馈、修改版本与确认结果
- 归档博主最终口播脚本和实际发布配文，生成两条差异分析
- 把复盘结论保存为候选经验，经人工确认后再决定是否长期使用
- 将全部结果渲染为可离线打开、可重建的只读 Workbench

## Baseline 和 Playbook 是什么

可以把它们理解为“博主画像底座”和“创作执行手册”：

| | Creator Baseline（博主画像底座） | Creator Playbook（创作执行手册） |
| --- | --- | --- |
| 回答的问题 | 这个博主是谁，哪些判断有证据？ | 面对新的 Brief，怎样创作才像她？ |
| 主要内容 | 当前定位、内容支柱、自然与商业内容规律、表达习惯、禁区、证据和置信度 | 可用选题方向、内容路线模板、标题公式、正文结构、语言工具箱、商业植入方式和出稿检查清单 |
| 如何产生 | 从公开样本中分析，再由本人或团队确认 | 从已确认的 Baseline 提炼为可执行规则，再由本人或团队确认 |
| 如何更新 | 创建新版本并保留旧版本；不会因单次项目自动改变 | Baseline 或创作策略发生变化时重新生成新版本 |

简单来说，**Baseline 负责保存“我们对博主的认识”**，**Playbook 负责把这些认识翻译成“下一篇具体怎么做”**。二者分开可以避免把 AI 推断当成事实，也避免每次收到 Brief 都重新摸索博主风格。

首次使用时，工作台会先生成一份待确认的 Baseline。你可以纠正定位、受众和商业边界；确认后再生成 Playbook。创建品牌项目时，项目会绑定当时确认的版本，因此以后更新画像也不会悄悄改变历史项目。

完整闭环如下：

```text
公开内容 → Baseline → Playbook
                         ↓
品牌 Brief → 内容路线 → 大纲 → 品牌审核
                              ↓
                    标题 / 正文 / Tags → 品牌审核
                              ↓
最终口播 + 实际发布配文 → 双轨差异 → 候选经验 → 人工 Review
```

工具不会替博主生成最终逐字口播稿，不会自动发布内容，也不会因为一次项目复盘就改写长期 Baseline。

## 开始使用

### 1. 准备环境

你需要：

- Codex Desktop
- Python 3.11 或更高版本
- TikHub API Token（仅在采集小红书公开账号数据时需要）

克隆仓库并安装本地运行引擎：

```bash
git clone https://github.com/Beryl-Tian/xhs-creator-workbench.git
cd xhs-creator-workbench
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

将 Skill 链接到 Codex 的本地 Skills 目录，然后重新打开 Codex Desktop：

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/packages/xhs-creator-workbench" ~/.codex/skills/xhs-creator-workbench
```

如果目标路径已经存在，说明 Skill 已安装，不要直接覆盖；先确认它是否指向当前仓库。随后在 Codex Desktop 中打开这个仓库。

### 2. 配置 TikHub Token

推荐通过环境变量提供：

```bash
export TIKHUB_API_TOKEN="replace-with-your-token"
```

也可以写入用户级配置 `~/.config/xhs-agent/config.json`：

```json
{
  "tikhub_api_token": "replace-with-your-token"
}
```

不要把 Token 写入仓库、项目配置或对话产物。

### 3. 检查运行环境

```bash
xhs-agent info --json
```

也可以使用 Skill 自带的入口：

```bash
python packages/xhs-creator-workbench/scripts/run_xhs_agent.py info --json
```

### 4. 从 Codex 对话开始

不需要记忆底层命令。可以直接告诉 Codex：

```text
使用 $xhs-creator-workbench 分析我的小红书账号：<主页链接>，采集 30 篇。
```

建立并确认 Baseline / Playbook 后，可以继续：

```text
这是品牌 Brief，帮我创建项目并给出一条最推荐的内容路线。
```

```text
我选择这条路线，请生成品牌可读的分镜大纲。
```

```text
这是品牌方对 S1 的反馈，请记录并生成修订版。
```

```text
这是最终口播脚本和实际发布配文，帮我归档并复盘差异。
```

路线选择、品牌确认和候选经验升级都是人工闸门。Skill 会在这些节点停下来等待你的明确决定。

## Workbench

每次数据变化后，Skill 会重建 Workbench。也可以手动执行：

```bash
xhs-agent workbench build --json
```

打开返回的 `index_path` 即可查看，无需运行 Web Server。Workbench 支持阅读、搜索、证据折叠和打印，但不直接修改业务数据；选择、反馈和确认仍在 Codex 对话中完成。

## 数据与隐私

这是一个本地优先工具：

| 目录 | 内容 | 是否提交 Git |
| --- | --- | --- |
| `.xhs-agent/` | 结构化事实、版本、运行记录和原始附件 | 否 |
| `workbench/` | 从事实数据生成的本地 HTML | 否 |
| `tests/fixtures/` | 人工构造、已脱敏的测试数据 | 是 |

关键原则：

- JSON 数据是事实源，HTML 只是可删除、可重建的阅读投影
- Baseline、Outline、Submission 和 Publication Copy 都保留历史版本，不静默覆盖
- AI 生成的 Candidate 必须经过确定性校验后才能成为正式对象
- 单项目复盘只生成候选经验，未经明确确认不会进入 Creator Baseline
- 不模拟登录、不注入 Cookie、不绕过平台访问控制

## 开源与责任边界

本项目是独立开源项目，与小红书运营主体及 TikHub 不存在官方隶属、合作或背书关系。“小红书”等名称仅用于说明兼容场景，其相关商标和品牌归各自权利人所有。

使用者应自行确认其数据采集、内容处理和发布行为符合适用法律、平台条款、API 服务条款及对合作方的保密义务。本项目只处理使用者主动提供的数据和公开可访问内容，不提供绕过登录、访问控制或平台风控的能力。

不要向公开 Issue、Pull Request、测试 fixture 或提交记录粘贴真实 Token、Cookie、博主资料、评论、品牌 Brief、反馈、口播稿或发布文案。安全问题请按照 [`SECURITY.md`](SECURITY.md) 私下报告。

## 当前范围

P0 已覆盖：本人账号分析、Baseline / Playbook、Brief 解析、内容路线、分镜大纲、双轨品牌审核、发布文案、最终内容归档、差异复盘、候选经验 Review 和本地 Workbench。

后续计划：

- P0.5：1–3 个同类博主的独立 Snapshot、归一化比较与选题空白分析
- P1：发布后 7/30 天数据回采、预测与实际表现对比、经验证规律升级

已知验证边界见 [`docs/phase-6-review.md`](docs/phase-6-review.md)。产品范围和流程分别见 [`docs/product-contract.md`](docs/product-contract.md) 与 [`docs/user-flows.md`](docs/user-flows.md)。

## 开发与验证

```bash
python -m pip install -e ".[dev]"
python -m pytest
python scripts/validate_schemas.py
python scripts/check_privacy.py
```

提交代码前必须运行隐私检查。真实博主资料、Brief、反馈、口播稿、发布文案、Token、Cookie 和凭证都不得进入 Git；测试只能使用 `tests/fixtures/` 中的合成脱敏数据。

项目结构：

- [`packages/xhs-creator-workbench/`](packages/xhs-creator-workbench/)：Codex Skill 与分任务协议
- [`src/xhs_agent/`](src/xhs_agent/)：确定性 Python 运行引擎
- [`schemas/v1/`](schemas/v1/)：结构化对象和 Candidate 契约
- [`docs/`](docs/)：产品契约、用户流程、架构和阶段验收记录

贡献代码前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。行为变更需要配套测试，所有提交都必须通过测试、Schema 校验和隐私检查。

## License

本项目采用 [MIT License](LICENSE)。
