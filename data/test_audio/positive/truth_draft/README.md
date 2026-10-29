# 事件级召回率真值

由 `src/ps/label_audio_events.py` 自动生成草稿，再经人耳核对成最终真值。

## 文件

| 文件 | 说明 |
|---|---|
| `events_truth_draft.csv` | RMS 能量自动检测的候选事件（草稿） |
| `events_truth.csv` | 人耳核对后的最终真值：9 段、155 个事件 |

核对记录：对照草稿删除 33 处、改边界/替换 10 处，复核时再剔除 1 处环境声。
召回率结果见 `../recall_results/`。

## 为什么必须人工核对

真值不能用模型高分窗口代替（否则循环论证，召回率必然虚高）。
草稿用独立于模型的能量信号，但能量分不清鸟叫/风声/其他鸟，最终以人耳确认为准。

## 重算

```powershell
D:\python\python.exe src\ps\eval_recall.py `
  --positive data\test_audio\positive `
  --truth data\test_audio\positive\truth_draft\events_truth.csv `
  --out data\test_audio\positive\recall_results
```
