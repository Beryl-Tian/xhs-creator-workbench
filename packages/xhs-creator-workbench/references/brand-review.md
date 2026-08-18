# 品牌审核与发布文案

## 大纲审核轨道

1. 让用户指定准备提交的 Outline 版本。
2. 生成不含内部推理和证据的纯净交付视图。
3. 如果助理在品牌模板中实质修改内容，先导入实际提交文件。
4. 发出后创建不可修改的 Outline Submission 快照。
5. 将品牌反馈原文和附件绑定到具体 Submission。
6. 生成反馈处理矩阵并创建新的 Outline 版本。
7. 品牌确认后创建 Approval，锁定 Approved Outline。

## 发布文案审核轨道

大纲确认后，根据 Approved Outline、Brief 和 Baseline 生成：

- 标题候选
- 小红书正文
- Tags

同时读取项目绑定的已确认 Creator Playbook。Baseline 提供事实和证据边界，Playbook 提供标题公式、正文组织、语言与商业护栏。生成任务只读取经过项目回测排除处理的 Creator Context，不得直接读取完整 Baseline 文件。

历史回测中，被排除的已发布笔记、最终标题、最终正文和 Tags 不得用于生成候选。先独立生成 Publication Copy，之后才允许在单独的复盘步骤中比较差异。

正文是发布配文，不是把逐镜头口播重新抄一遍。优先保留：本人当天状态、产品进入的真实场景、读者可理解的必要卖点、本人生活态度与自然互动；品牌必带 Tags 必须逐项覆盖，辅助 Tags 只保留与内容实际相关的词。

Publication Copy 使用独立的版本、Submission、Brand Feedback 和 Approval 链。不得用大纲过审状态代替发布文案过审状态。

## 反馈归因

品牌意见默认保存为品牌、品类或项目经验。除非用户明确确认，不得把品牌意见直接写入 Creator Baseline。

AI 只负责把品牌原始意见结构化为 candidate。引擎必须保留原文、绑定具体 Submission，并将歧义或与博主人设冲突的意见停在人工确认闸门。Submission 和 Approval 都不可覆盖。
