# 最终内容归档

## 必要输入

- 最终口播脚本
- 实际发布标题、正文和 Tags
- 对应 Project
- 可选的发布时间与发布链接
- 若实际发布配文来自截图，同时保存原始截图与人工核对后的结构化转写；截图作为视觉原件，转写用于差异计算

允许先保存其中一种，但两者齐全后才能标记归档完整。

## 双轨对比

分别比较：

1. Approved Outline 与最终口播脚本。
2. Approved Publication Copy 与实际发布标题、正文和 Tags。

这里的 Approved 指品牌确认的 Submission 快照，而不是内部源对象。若 Submission 保存了品牌模板实际文件的提取文本，以品牌真正收到的文件内容为最高优先级基准。

提取新增、删除、重排、弱化和强化，并标记可能来源：品牌审核、博主创作、拍摄执行或无法判断。

## 学习闸门

先生成 Learning Candidate，不直接修改 Baseline。只有用户确认、多个项目重复出现或发布数据验证后，才能显式创建新的 Baseline 版本。

## 归档执行约束

- 允许先归档最终口播脚本或实际发布配文其中一种；后补另一种时更新同一个 Bundle。
- 已归档原件不可被不同文件覆盖。发现上传错误时，保留历史并走后续校正流程，不静默替换。
- 发布截图与结构化转写分别保存并记录 SHA-256，不能只保留转写后丢弃原始视觉证据。
- 实际发布配文必须结构化为唯一的最终标题、正文和 Tags；品牌审核阶段的标题候选不等于实际发布标题。
- 口播脚本和实际发布配文分别生成 `oral_script` 与 `published_copy` Evidence。
- AI 只写 archive candidate；由 `published finalize` 校验差异类型、Evidence 和候选经验后落盘。
- 单项目经验默认优先使用 `project_only`。提高到 `commercial`、`organic` 或 `global` 必须有明确理由，但仍只生成 `proposed` Candidate。
- Learning Review 只允许接受或拒绝；接受不等于升级 Baseline。升级必须是后续显式操作。
