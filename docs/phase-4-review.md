# 阶段 4 Review：Brief、路线、大纲与品牌审核闭环

状态：等待用户 Review

## 本阶段验收范围

```text
Confirmed Baseline → Project → Brief 原件与结构化结果
→ 内容路线 → 人工选择 → Outline V1..n → HTML Preview
→ Outline Submission / Feedback / Approval
→ Publication Copy V1..n → Copy Submission / Feedback / Approval
```

本阶段没有实现最终口播脚本与实际发布配文归档，也没有进入候选学习和对标博主分析。

## 需要重点 Review 的产品决策

1. Project 只能绑定已经人工确认的 Baseline，并永久保留该版本引用。
2. Brief 原件按 SHA-256 保存到 `.xhs-agent/projects/<project-id>/brief/source/`，不进入 Git。
3. MD、TXT、PDF、DOCX 和 XLSX 的提取保留行号、页码、段落或单元格 Locator；文本提取不冒充版式、图片、批注或公式验证。
4. Brief 结构化严格分为原文事实、带置信度推断和待确认问题。品牌、产品与 Project 不一致时停止，不静默覆盖。
5. 默认生成一条最推荐路线。用户明确要求多条时生成 2–3 条，且任意两条至少在核心张力、场景、产品角色或情绪路径中的两个维度不同。
6. 路线必须引用项目绑定 Baseline 中真实存在的 Evidence；路线生成后停在人工选择闸门。
7. 大纲默认使用旧 scripts-agent 的 7 段分镜骨架，每段对应秒数、镜头、大致口播、花字和品牌露出；Brief 可覆盖段数与时长。版本不可覆盖，内部反馈保存原文并指向修改前版本。
8. HTML 是只读 Preview，没有弹出式 Review UI。用户仍在 Codex 对话中选择、反馈和确认。
9. 大纲与标题/正文/Tags 使用两条独立的品牌 Submission、Feedback 和 Approval 链。
10. 只有品牌确认某个大纲 Submission 后，才能生成 Publication Copy；系统不替博主写最终口播脚本。

## Workbench 页面

- 首页：Creator 与品牌项目入口
- 项目页：品牌、产品、绑定 Baseline 与各轨道状态
- Brief 页：事实、推断、问题、卖点、必提与禁用
- 路线页：三条策略对比、推荐与已选状态
- 大纲页：选题、Hook、总时长，以及逐段对应的秒数、镜头、大致口播、花字、品牌露出与覆盖检查
- 发布文案页：标题候选、正文、Tags 与 Brief 覆盖

所有页面都可以离线打开、打印或保存 PDF。HTML 可以删除后重建，不能作为唯一事实源。

## 数据与隐私边界

- 真实 Brief、博主信息、反馈、提交文件与结构化业务对象只写入 `.xhs-agent/`。
- HTML 只写入 `workbench/`；两者均由 `.gitignore` 排除。
- Repo 内测试和 Review 示例只使用合成数据。
- Token 仍只从环境变量或用户级配置读取。

## 验证结果

- JSON Schema 自检：27 个 Schema 通过。
- 自动测试：42 项通过。
- 覆盖：Baseline 确认、项目创建、Brief 导入、DOCX/XLSX/PDF Locator、多路线差异、Evidence 引用、路线选择、大纲版本、内部反馈、双品牌审核链、发布文案和 Workbench 链接。
- Skill frontmatter、名称、reference 路径与 `agents/openai.yaml` 已人工核对。
- `skill-creator` 的 `quick_validate.py` 未能执行，因为系统及工作区 Python 均缺少其未声明依赖 `PyYAML`；未为此修改用户环境。
- 自动化浏览器因安全策略禁止 `file://` 页面，未完成浏览器截图验收；页面链接与资源由 HTML 解析测试验证。

## Review 建议路径

1. Workbench 首页是否能区分“博主档案”和“合作项目”。
2. 项目页的信息密度是否适合助理日常使用。
3. Brief 页的事实/推断/待确认三分法是否直观。
4. 三条路线是否方便比较并做选择。
5. 大纲 Preview 是否便于复制到品牌模板，以及打印成 PDF。
6. 标题、正文、Tags 是否应该继续作为独立页面和审核链。

回复“阶段 4：通过，commit”，或按页面/流程给出修改意见。在通过前不开始阶段 5，也不提交本阶段代码。
