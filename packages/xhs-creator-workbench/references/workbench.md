# 重建和查看本地 Workbench

## 重建

运行：

```text
python scripts/run_xhs_agent.py workbench build --json
```

只从 `.xhs-agent/` 读取结构化事实，将页面和必要静态资产写入 `workbench/`。不要在 HTML 中创建、确认或修改业务对象。

## 交付给用户

- 将命令返回的 `index_path` 作为本地入口。
- 页面可以直接用浏览器打开，不要求启动服务器或安装前端工具。
- Baseline 页面包含打印/保存 PDF 按钮，可用于分享只读副本。
- 用户的确认、否定和修改意见仍通过 Codex 对话写回结构化数据；不要读取网页表单状态。

## 重建规则

- 每次结构化数据变化后重建。
- 保留所有 Baseline 历史版本页面。
- 只清理上一次 manifest 记录、且本次不再生成的页面；不得递归删除 `workbench/`。
- 如果某个对象损坏，跳过该对象、在首页显示警告，并继续生成其他有效页面。
