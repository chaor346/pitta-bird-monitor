# 案例模板：目标存在性录像（非固定时长）

**类型**：工程模板（case template）
**适用场景**：检测到目标才录、目标离开才停的场景：野生动物监测、安防、运动捕捉、
产线异物。适用前提是"有可用的逐帧或准逐帧目标检测"。
**不适用**：目标出现时间已知且固定（直接定时录即可）、或没有检测手段。

---

## 为什么不固定时长

| 方案 | 存储 | 漏录风险 | 适用性 |
|------|------|----------|--------|
| 固定录 10 s | 大量空画面 | 目标停留 15 s → 后 5 s 丢失 | 差 |
| 触发即录到手动停 | 最优 | 依赖人工 | 不可自动化 |
| **存在性录像** | 只录目标相关段 | 由 `absence_hits`/`absence_sec` 控制 | 好 |

衡量指标用**有效帧占比** = 含目标帧数 / 总帧数，而不是只看文件大小。

---

## 核心逻辑

```python
# 伪代码：录像循环与推理线程解耦
state = WAITING
last_seen = None      # 最近一次"新鲜且命中"的时间
misses = 0            # 连续无目标计数
first_miss = None     # 本轮首次无目标时间

on_new_result(result, ts):            # 推理线程投递的结果，必须带时间戳
    if now() - ts > stale_sec:        # ← 关键：过期结果直接丢弃
        return
    if result.hit:
        last_seen = ts
        misses = 0
        first_miss = None
        if state == SEARCHING:
            state = RECORDING
            start_writer()
    else:
        if state == RECORDING:
            misses += 1
            if first_miss is None:
                first_miss = ts
            if misses >= absence_hits and (ts - first_miss) >= absence_sec:
                state = WAITING
                stop_writer()

on_tick():                            # 主循环
    if state == RECORDING and now() - last_result_time > vision_timeout:
        stop_writer()                 # 推理彻底断流时的保护
        state = WAITING
```

三条必须写死的规则：

1. **过期结果不算"无目标"**：只丢弃，不能 `misses += 1`。否则推理一慢就提前结束。
2. **双条件结束**：`misses >= absence_hits` 且 `跨度 >= absence_sec`，抗单帧漏检。
3. **断流保护**：超过 `vision_timeout` 没有新鲜结果，强制结束并回 WAITING，避免无限录像。

## 参数调优（按推理耗时反推）

| 单次推理耗时 | `absence_hits` | `absence_sec` | 实际后滚 |
|--------------|----------------|---------------|----------|
| < 1 s | 3 | 2 | 约 3–5 s |
| 5–7 s | 2 | 6 | 约 10–15 s |
| > 10 s | 2 | 12 | 约 20 s |

后滚时间 ≈ `max(absence_hits, absence_sec / 推理周期) × 推理周期`。

## 写盘不要阻塞检测

- 用独立线程/进程写帧，检测线程只投递结果；
- 写帧队列设上限，满则丢最旧帧（宁可丢帧，不要卡死检测）；
- 结束录像时先停写入再关文件，避免生成半截 MP4。

## 自检方法

1. 目标入画 → 出画，确认录像起止时间与预期后滚一致；
2. 人为让推理变慢（降 `detect-hz`），确认不会提前结束；
3. 直接杀掉推理进程，确认 `vision_timeout` 能收尾；
4. 统计有效帧占比，与固定时长方案对比；
5. 录像期间观察检测端耗时，确认没有因为写盘而恶化（若恶化，用锁文件暂停检测端推理）。

## 已验证效果

本项目（仙八色鸫）：检测到鸟开始录像、鸟消失后延迟结束，实测后滚约 12 s
（`absence-hits=3`、`absence-sec=6`），录像期间通过锁文件暂停音频推理，
避免 CPU 争抢导致音频端漏检。

## 失效条件

- 检测模型本身漏检率高：再好的状态机也救不了，先解决 mAP/召回。
- 推理耗时远大于目标停留时间：只能录到"曾经有"，需要提高帧率或换更轻的模型。
- 多个目标交替出现：需要按目标 ID 分别维护 `last_seen`，否则会互相"续命"。
- 存储极慢（SD 卡）：写盘成为瓶颈时，必须降分辨率或录前压缩。
