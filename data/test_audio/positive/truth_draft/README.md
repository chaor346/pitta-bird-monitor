# 真值草稿（待人工核对）

这里是计算**事件级召回率**的第一步：由 `src/ps/label_audio_events.py` 自动生成草稿，
再由人耳核对成 `events_truth.csv`。

## 文件

- `events_truth_draft.csv` —— 用 RMS 能量自动检测的候选鸟鸣事件（audio, event_id, start_sec, end_sec）
- `*_draft.png` —— 每段录音一张静态核对图（蓝线 RMS、绿块候选、虚线是模型分数，仅参考）
- `review_events.html` —— **推荐用的核对页面**（单文件、离线、双击即开），由 `src/ps/build_truth_review.py` 生成

## 现状（2026-10-26：已核对完成）

`events_truth.csv` 已经由人耳核对完成：9 段、**155 个事件**（对照草稿删除 33 处、改边界/替换 10 处，复核时再剔除 1 处环境声）。
由此算出的召回率见 `../recall_results/README.md`。以后再改真值，重跑一次 `eval_recall.py` 即可，
同时要更新 `data/comparison.csv` 与根 `README.md` 里的那两行数字。

## 推荐做法：用核对页面（听约 12 分钟 + 点选）

1. 双击 `review_events.html`（Edge / Chrome 都行，不用起服务器，也不联网）。
2. 每段分两遍：
   - **先整段扫**（空格播放，1.5×/2×）：只关心“有没有鸟叫”；草稿漏标的地方暂停，
     点“＋ 在播放头新增”或按 `N`（默认 2 s，再用“起±/止±”微调 0.2 s 一格）。
   - **再逐条判候选**（`J`/`L` 跳上/下一处，或点行内“▶ 听”）：确认是仙八色鸫就留着，
     风声、虫声、其他鸟点“保留/噪声”（`K` 留 / `D` 标噪声）。
3. 每段判完点“本段已听完 ✓”，左侧打勾，顶部“已听 x/9”是总进度。
4. 九段判完 → 点“导出 events_truth.csv”，下载同名 CSV（同时弹窗给出全文，可直接复制）。
5. 把 `events_truth.csv` 放进本目录，跑下面的命令。

细节：

- 只听“这段里有没有仙八色鸫鸣声”，**不要参考模型分数**（模型分数留作评估对照，看了会导致循环论证）。
- 起止差 0.3 s 以内不影响结果：`eval_recall.py` 的命中条件是“真值区间与某窗口有重叠，且该窗口分数 ≥ 阈值”。
- 页面把判定存在浏览器本地（localStorage），关掉再开能接着上次；换浏览器/清缓存会丢，
  建议每听 2~3 段导出一次备份（导出的是全量，覆盖旧的即可）。
- 页面用相对路径 `../` 读录音，移动页面时要连 `positive/` 一起移动。

## 备选：直接改 CSV

1. 播放 `../` 下对应的 9 段录音（共约 12 分钟），对照同名 PNG；
2. 在 `events_truth_draft.csv` 里：删掉不是鸟叫的行、补上漏掉的鸟叫、修正起止秒；
3. 核对完另存为 `events_truth.csv`（放在本目录）。

## 然后算召回

```powershell
cd D:\嵌赛\pitta_bird_monitor
D:\python\python.exe src\ps\eval_recall.py `
  --positive data\test_audio\positive `
  --truth data\test_audio\positive\truth_draft\events_truth.csv `
  --out data\test_audio\positive\recall_results
```

输出 `recall_results/recall_results.csv`，并在终端打印 0.5（评估口径）与 0.985（板端阈值）
两个阈值下的事件级 / 窗口级召回率。

## 为什么必须人工核对

召回率的真值不能用模型自己的高分窗口代替（否则是循环论证，召回率必然虚高）。
草稿用的是**独立于模型的能量信号**，但能量分不清“鸟叫 / 风声 / 其他鸟”，
所以最终以人耳确认为准。这一步在普通电脑上即可完成，不需要开发板。

## 重生成页面

改了草稿或录音（比如补了漏检候选）之后，重新生成一次页面：

```powershell
D:\python\python.exe src\ps\build_truth_review.py
```

候选事件数变化时页面版本号会变，浏览器里旧进度自动作废，不会出现新旧对不上的情况。
