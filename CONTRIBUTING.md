# Contributing

感谢你帮助改进小红书创作工作台。本项目接受缺陷修复、测试、文档和小范围功能改进。

## 开始之前

- 对较大的功能或架构调整，请先创建 Feature Request 讨论范围。
- 安全漏洞请按照 [`SECURITY.md`](SECURITY.md) 私下报告。
- 不要在 Issue、Pull Request、commit 或测试数据中提交任何真实业务数据或凭据。

## 本地开发

需要 Python 3.11 或更高版本：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

运行完整验证：

```bash
python -m pytest
python scripts/validate_schemas.py
python scripts/check_privacy.py
```

## 隐私要求

- 真实博主资料、笔记、评论、转录、品牌 Brief、反馈、口播稿和发布文案只能保存在被 Git 忽略的 `.xhs-agent/` 中。
- 生成的本地页面只能保存在被 Git 忽略的 `workbench/` 中。
- Token、Cookie、密钥和凭据不得进入仓库；TikHub Token 只能来自 `TIKHUB_API_TOKEN` 或用户级配置。
- 测试 fixture 必须是人工构造、匿名且无法反推出真实主体的数据。
- 截图、日志、导出文件和失败样例也必须先脱敏。

提交前必须运行：

```bash
python scripts/check_privacy.py
```

## 代码与产品边界

- 确定性的文件、校验、版本、Diff 和渲染行为放在 `src/xhs_agent/`。
- AI 工作流指令放在 `packages/xhs-creator-workbench/`。
- `.xhs-agent/` 中的 JSON 是事实源，HTML 是可重建投影。
- 不覆盖历史项目版本或提交快照。
- 未经使用者明确确认，不把候选经验升级为 Creator Baseline。
- 行为变更必须增加或更新测试。

## Pull Request

请保持 PR 聚焦，并在描述中说明：

- 改了什么以及为什么
- 对使用者或数据格式的影响
- 已运行的验证命令
- 是否涉及 Schema、迁移、隐私边界或兼容性变化

提交 PR 即表示你同意按本仓库的 MIT License 提供该贡献。
