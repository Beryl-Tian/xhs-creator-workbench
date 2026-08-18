# 阶段 3 Review 清单

状态：待 Review

本阶段只验收面向助理的 Creator Workbench：本地首页、博主页和 Baseline 历史版本页。没有进入 Brief、大纲或项目页面。

## 已交付

- `workbench build` CLI 与可追踪 Run
- 无 Creator 时的非技术用户空状态
- Workbench 首页：博主数、Baseline 数和博主入口
- Creator 页面：当前定位与不可变 Baseline 历史版本
- Baseline 页面：
  - `pending_confirmation / confirmed / rejected / superseded` 状态
  - 人工确认问题
  - 四项带 Evidence 的画像摘要
  - 点赞中位数、藏赞比、发布间隔和 Evidence 数量
  - 数据快照：质量闸门、互动统计、高频话题、标题模式和 TOP10
  - 自然内容与商业内容对照
  - 九类 Claims、认识状态、置信度、适用场景与限制
  - 支持证据与 Counter Evidence 折叠查看
  - 缺失维度与分析限制
- 中文搜索、打印/保存 PDF、手机响应式和打印样式
- 完全离线，不使用 CDN、远程字体或网页服务器
- HTML 全量转义，避免博主正文被当作可执行标签
- 生成 manifest 放在 `.xhs-agent/cache/`；`workbench/` 只保存页面和必要静态资产
- 重建只删除旧 manifest 明确记录的过期生成文件，不递归清空目录
- 单个损坏对象可跳过并显示警告，不阻断其他页面

## 页面结构

```text
workbench/
├── index.html
├── assets/
│   ├── workbench.css
│   └── workbench.js
└── creators/<creator-id>/
    ├── index.html
    └── baselines/<baseline-id>.html
```

## 产品决策

1. Workbench 是阅读界面，不是新的审核 UI；反馈继续在 Codex 对话中完成。
2. 页面默认优先显示“待确认问题”和画像摘要，而不是通用 Dashboard 导航。
3. 使用暖灰纸张、深色文字、砖红与橄榄绿的档案式视觉；不依赖网络字体。
4. 所有版本保留独立页面，后续项目可绑定并链接到指定 Baseline。
5. 页面可以直接双击打开，也可以用浏览器打印为 PDF 发给内部同事。

## 建议重点 Review

1. 首页到 Creator，再到 Baseline 版本的层级是否容易理解。
2. Baseline 首屏是否把“它仍待本人确认”表达得足够明显。
3. 四项摘要和自然/商业对照是否符合助理最先阅读的顺序。
4. 九类 Claims 是否需要默认全部展开，还是维持当前“结论展开、Evidence 折叠”。
5. 是否接受搜索与打印，但不加入网页反馈表单。
6. 档案式视觉是否适合长期作为本人工作台，而不是一次性报告。
7. 阶段 4 是否沿用同一视觉系统制作 Brief、路线和大纲页面。

## 本地验收命令

```text
PYTHONPATH=src pytest -q
python3 scripts/validate_schemas.py
python3 scripts/check_privacy.py
python3 packages/xhs-creator-workbench/scripts/run_xhs_agent.py workbench build --json
```

## Review 结论格式

回复“阶段 3：通过，继续”，或按编号给出修改意见。在通过前不进入 Brief 与大纲实现。
