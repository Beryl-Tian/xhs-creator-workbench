---
name: xhs-creator-workbench
description: Local-first Xiaohongshu creator workbench for analyzing a creator's public content, maintaining and rendering an evidence-backed creator baseline, turning brand briefs into content routes and outlines, tracking brand submissions and feedback, generating titles/body/tags, and archiving final oral scripts and published copy. Use when the user asks to analyze or update their Xiaohongshu account, build or view the local creator workbench, write or revise a branded-content outline from a brief, process brand review feedback, prepare publication copy, archive a finished collaboration, or analyze comparable creators.
---

# 小红书创作工作台

将账号分析、品牌内容生产和最终归档组织成可追踪的本地闭环。把结构化事实保存在 `.xhs-agent/`，把给人看的页面生成到 `workbench/`。

## 先保护隐私

- 只将博主数据、Brief、品牌反馈、口播脚本和发布配文写入 `.xhs-agent/`。
- 只将渲染后的本地页面写入 `workbench/`。
- 只从 `TIKHUB_API_TOKEN` 或用户级配置读取 Token；不得把 Token 写入仓库。
- 不模拟登录、不注入 Cookie、不绕过平台访问控制。

## 按任务加载协议

只读取当前任务需要的 reference：

- 建立或更新博主画像：先读取 [references/creator-baseline.md](references/creator-baseline.md)；收到蒸馏任务后再完整读取 [references/creator-baseline-distillation.md](references/creator-baseline-distillation.md)。
- 把已确认画像转成选题、路线和大纲可用的执行指南：读取 [references/creator-playbook.md](references/creator-playbook.md)。
- 上传 Brief、生成路线或大纲：读取 [references/brief-to-outline.md](references/brief-to-outline.md)。
- 记录品牌提交、处理反馈、确认大纲，或生成标题/正文/Tags：读取 [references/brand-review.md](references/brand-review.md)。
- 上传最终口播脚本和实际发布配文：读取 [references/archive-final.md](references/archive-final.md)。
- 分析同类博主：读取 [references/benchmark.md](references/benchmark.md)。
- 重建或查看本地页面：读取 [references/workbench.md](references/workbench.md)。

不要为一个任务加载所有 reference。

## 执行规则

1. 先运行 `python scripts/run_xhs_agent.py info --json`，确认运行引擎和隐私目录。
2. 读取对应协议，收集不可安全推断的缺失信息。
3. 调用确定性命令创建或更新结构化对象。
4. 需要 AI 判断时，生成符合 Schema 的结构化结果，再交给引擎校验和落盘。
5. 生成或重建 Workbench 页面。
6. 在路线选择、品牌确认、候选学习升级等人工闸门前停下等待用户确认。

人工 Review 中出现“希望塑造的定位”或“希望吸引的人群”时，使用 Baseline 校准创建新版本。将其保存为团队确认的 `human_context`，不得改写成公开数据已经证明的现有画像。

需要时间画像时，使用扩展主页样本生成纵向分析并绑定到新 Baseline 版本。近期身份仍由最新窗口决定；较早主页内容只作为能力和转型证据。

CLI 返回 AI Task 时，完整读取 Task 指向的协议与输入文件，严格按 `candidate_output_path` 写 JSON，再调用对应 finalize 命令。不得跳过 deterministic finalize 直接写正式对象。

路线 finalize 后必须停下让用户选择；没有 Route Selection 不得生成 Outline。品牌确认必须针对真实发出的 Submission，而不是内部草稿。大纲确认后才可生成标题、正文和 Tags。

最终归档可先保存口播脚本或实际发布配文其中一种；两者齐全后按 Task 生成双轨差异与 Learning Candidate。候选经验必须停在人工 Review，不得因归档或接受候选而自动修改 Baseline。

## 不变量

- 不用 HTML 代替结构化事实。
- 不覆盖历史 Outline、Publication Copy 或 Brand Submission。
- 大纲审核和发布文案审核使用独立版本链。
- 不替博主生成最终口播脚本。
- 不因单次品牌反馈或最终稿差异自动修改 Creator Baseline。
- 区分 Evidence 支持的现状画像与团队确认的目标定位；下游创作同时读取二者，但不得混写来源。
