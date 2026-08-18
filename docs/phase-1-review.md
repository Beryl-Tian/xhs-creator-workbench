# 阶段 1 Review 清单

状态：待 Review

本阶段只验收工程骨架、隐私边界、Skill 路由、CLI 入口和 v1 数据契约。TikHub 采集、真实 Baseline、Workbench 页面和品牌工作流尚未实现。

## 已交付

- 可安装 Skill 源码和 UI 元数据
- 五条按需加载的工作流 reference
- Python 3.11+ 包与 `xhs-agent` CLI 骨架
- 16 个 JSON Schema
- `.gitignore` 私密目录、密钥和用户附件保护
- Git 可见文件隐私扫描脚本
- Schema、CLI 和隐私测试

## 建议重点 Review

1. 是否接受所有真实运行数据只存放在 `/.xhs-agent/`，所有本地 HTML 只存放在 `/workbench/`，且两者都不进 Git。
2. 是否接受 PDF、Word、Excel、截图、视频和音频在仓库中默认忽略，只允许显式审核过的 assets 和脱敏 fixtures。
3. Skill 的五类触发任务和渐进式 reference 是否清楚。
4. 大纲与发布文案的独立 Submission / Feedback / Approval Schema 是否符合业务。
5. 最终归档必须同时包含最终口播脚本和实际标题、正文、Tags，是否正确。
6. 多轨 Project 状态是否能表达发布文案审核与博主创作并行。
7. CLI 命令命名是否易懂。

## Review 结论格式

回复“阶段 1：通过，继续”，或列出需要修改的编号和内容。在通过前不进入 TikHub 与 Baseline 能力迁移。
