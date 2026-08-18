# 建立或更新 Creator Baseline

## 输入闸门

采集前确认：

- 平台为小红书。
- 提供明确主页 URL、分享文本或账号 ID；同名账号不可猜测。
- 本任务是本人分析，不是对标分析。
- 采集数量为 30、50 或 80 篇。只做当前画像可用 30；需要近期／历史／转型视角时优先采集 80，实际以主页可获得数量为准。
- 确认评论采集范围；评论在落盘前去除用户 ID、昵称、头像和位置。

## 执行链

1. 运行 `creator analyze`，生成标准化 Evidence、确定性分析和 `distillation-task.json`。
2. 检查任务中的 `status`：
   - `blocked_by_quality_gate`：展示警告并停止，请求补采。
   - `ready`：继续。
3. 完整读取 [creator-baseline-distillation.md](creator-baseline-distillation.md)、任务指向的 Notes、Evidence 和 Candidate Schema。
4. 按协议生成纯 JSON candidate，写入任务指定的私有路径。
5. 运行 `creator baseline-finalize`。校验失败时只修订 candidate，不重新采集。
6. 返回 `pending_confirmation` Baseline；不得当作本人已确认事实。
7. 运行 `workbench build --json`，返回本地页面并收集人工确认。
8. 若反馈包含目标定位或期望受众，运行 `creator baseline-calibrate` 创建新版本；不要覆盖旧 Baseline，也不要伪造 Note Evidence。

## 命令

```text
python scripts/run_xhs_agent.py creator analyze \
  --account "<主页分享文本、URL 或账号 ID>" \
  --sample-size 30 \
  --comment-note-limit 20 \
  --comments-per-note 20 \
  --json
```

AI 写出 candidate 后：

```text
python scripts/run_xhs_agent.py creator baseline-finalize \
  --run-id "<run-id>" \
  --candidate "<candidate-output-path>" \
  --json
```

人工目标校准：

```text
python scripts/run_xhs_agent.py creator baseline-calibrate \
  --baseline-id "<baseline-id>" \
  --desired-positioning "<希望塑造的定位>" \
  --target-audience "<希望吸引的人群>" \
  --accept-question 1 \
  --json
```

`human_context` 是团队确认的创作目标，不是公开数据推断。已有受众画像继续保留，避免把“希望吸引的人”写成“当前粉丝已经是”。

人工否定某个待确认问题时使用 `--reject-question <序号>`。若反馈形成可复用商业边界，同时写入 `--commercial-guardrail "<约束>"`；例如品牌强硬要求下的硬广写法应记录为少见例外，而不是默认路线。

为已有 Baseline 增加时间画像时，先以 80 篇主页样本运行 `creator analyze`，再将其确定性纵向分析绑定为新版本：

```text
python scripts/run_xhs_agent.py creator baseline-attach-history \
  --baseline-id "<baseline-id>" \
  --run-id "<80篇分析 run-id>" \
  --json
```

该操作只替换时间画像来源，不重写原 Baseline Claims 或已确认的自然／商业划分。

所有结果只写入 `.xhs-agent/`。当前阶段不生成 HTML。

## 不变量

- 只使用 TikHub 小红书 App V2，不使用已下线接口 fallback。
- 不保存 API 原始响应、头像或媒体文件。
- 没有图片、镜头或口播 Evidence 时，不生成视觉与口播规律。
- 商业笔记只作为候选，必须由助理确认。
- 不用互动相关性解释因果。
- 不覆盖旧 Baseline；每次成功 finalize 都创建新版本。
- 人工目标校准也创建新版本，并将来源 Baseline 标为已取代。
- 时间画像只使用主页时间序列：最新至多 30 篇定义近期基线，更早主页内容定义历史能力，相邻窗口用于判断转型；不得用关键词搜索结果补齐历史窗口。
- 历史能力不得直接升级为当前定位。只有近期仍稳定出现，或团队明确要求恢复时，才能进入当前创作主轴。
