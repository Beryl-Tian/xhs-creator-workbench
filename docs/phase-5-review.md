# 阶段 5 Review：最终发布归档与候选学习

状态：等待用户 Review

## 本阶段验收范围

```text
Approved Outline Submission ──→ 最终口播脚本 ──→ 差异 A
Approved Copy Submission ─────→ 实际发布配文 ──→ 差异 B
最终口播 + 实际配文 ──────────→ Final Publication Bundle
差异 A + 差异 B + Evidence ───→ Proposed Learning Candidate
Proposed Candidate ────────────→ 人工接受或拒绝
```

阶段 5 不替博主生成最终口播脚本，也不因为归档或接受候选经验自动修改 Creator Baseline。

## 需要重点 Review 的产品决策

1. 最终口播脚本与实际发布配文允许分两次上传，始终更新同一个 Bundle。
2. 已保存的归档原件不可被不同文件静默覆盖。
3. 只有两类文件齐全、对应 Outline 和 Publication Copy 都有品牌 Approval 后，才生成完整差异。
4. 差异基准使用品牌真正确认的 Submission 快照；若助理上传了实际品牌模板，以其提取文本优先。
5. 实际发布配文结构化为唯一的最终标题、正文和 Tags，不继承品牌审核阶段的“候选标题”语义。
6. 双轨差异仅使用新增、删除、重排、弱化和强化五类变化。
7. 每条变化标注可能来源：品牌审核、博主创作、拍摄执行或无法判断；不确定时不能强行归因。
8. 最终口播脚本与实际发布配文分别生成 Evidence，候选经验必须引用本次归档 Evidence。
9. 单项目候选默认优先 `project_only`，置信度最高 0.75，避免把一次变化过度概括为稳定规律。
10. Candidate Review 只支持接受或拒绝；接受仍不等于升级 Baseline。

## Workbench 页面

项目页新增“最终发布归档”入口，归档页包含：

- 最终标题、正文和 Tags
- 最终口播脚本
- Approved Outline → 最终口播脚本差异
- Approved Publication Copy → 实际发布配文差异
- 候选经验、范围、状态和置信度

部分归档也会显示页面，但明确提示还缺少的材料，不会显示为完成。

归档所引用的 Approved Outline 继续使用品牌审核熟悉的分镜结构：每段逐行对应秒数、镜头、大致口播、花字和品牌露出。默认是旧 scripts-agent 的 7 段骨架，Brief 明确要求其他结构时可调整。

## 数据与隐私边界

- 原件、提取文本、Evidence、Bundle 和 Learning Candidate 只写入 `.xhs-agent/`。
- Workbench 仍只是可删除、可重建的 HTML 投影。
- 仓库测试和 Review 示例只使用人工合成内容。
- 发布链接仅接受 HTTP/HTTPS；不会自动访问或上传任何内容。

## 验证结果

- JSON Schema 自检：29 个 Schema 通过。
- 自动测试：52 项通过。
- 隐私扫描通过。
- 覆盖部分归档、后补文件、原件防覆盖、品牌 Approval 前置、双轨差异、Evidence 引用、候选置信度上限、人工 Review 和归档 HTML。

## Review 建议

1. 部分归档的状态是否容易理解。
2. 双轨差异的分类与来源是否符合实际复盘习惯。
3. 归档页是否应该完整展示口播和正文，还是默认折叠。
4. 候选经验的 `project_only / brand / category / commercial / organic / global` 范围是否够用。
5. “接受候选但不升级 Baseline”的边界是否清晰。

回复“阶段 5：通过，commit”，或按页面/流程给出修改意见。在通过前不开始后续阶段，也不提交本阶段代码。
