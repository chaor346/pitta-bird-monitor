# src/ps/ PS 侧软件

本目录包含板端运行程序、PC 端训练/数据/导出工具，以及少量开发过程中的历史版本。
按用途分为四类。**板端实际部署只依赖 A 类**。

## A. 板端实际部署（运行时）

| 文件 | 用途 |
|------|------|
| `inmp441_predict_time.py` | **音频主程序（systemd 正式部署）**：DMA 采集 → mel → CNN 推理 → 写触发；录像时暂停；额外记录北京时间与 event_id（JSON 触发） |
| `inmp441_predict_pause.py` | 音频调试版（手动终端运行，参数口径不同，见根 README §4） |
| `trigger_board_presence.py` | **图像主程序**：状态机 + ncnn 推理 + 目标存在性录像 |
| `inmp441_record.py` | INMP441 DMA 连续录音驱动（MMIO 轮询，无中断） |
| `av_recording_lock.py` | 录像锁（flock），录像/转换期间持有 |
| `audio_numpy.py` | 纯 numpy 音频推理（被主程序调用，无 torch/librosa） |
| `infer_ncnn` | 板端 ncnn 推理二进制（ARM，由 `infer_ncnn.cpp` 编译） |
| `infer_ncnn.cpp` | ncnn 推理源码（IMG_SIZE=320，num_threads=2） |
| `build_board.sh` | 板端编译推理程序的脚本 |
| `audio_model.npz` | 音频 CNN 权重 |
| `mel_basis.npy` | mel 滤波器组 |
| `best_ncnn.bin` / `best_ncnn.param` | 图像 YOLOv8n ncnn 模型 |

## B. PC 端训练 / 数据 / 导出

| 文件 | 用途 |
|------|------|
| `01_collect_images.py` | 采集仙八色鸫正样本（iNaturalist） |
| `01b_collect_negatives.py` | 下载背景负样本 |
| `01e_collect_other_birds.py` | 采集其他鸟难负样本 |
| `01c_auto_label.py` | 用 COCO 预训练模型自动预标注 |
| `01d_check_labels.py` | 画框抽查标注结果 |
| `annotate.py` | 迷你标注器（纯 OpenCV，不依赖 labelImg） |
| `02_label_howto.md` | 标注教程 |
| `02b_split.py` | 按 8:2 划分训练/验证目录 |
| `check_dataset.py` | 数据集体检（损坏/过小文件） |
| `03_train.py` | YOLOv8n 训练 |
| `04_export.py` | 导出 ONNX / ncnn |
| `train_binary_fixed.py` | 音频 CNN 训练（最终版） |
| `postprocess.py` | YOLOv8 后处理（纯 numpy，可上板） |
| `pitta.yaml` | YOLO 数据集配置 |
| `config.py` | 全局参数配置 |
| `requirements.txt` | PC 端依赖 |

## C. PC 端评估 / 工具

| 文件 | 用途 |
|------|------|
| `eval_val_onnx.py` | **图像指标重算**（onnxruntime + numpy 后处理）：val 检出率 / mAP@0.5 / 负样本误报，输出到 `data/test_images/eval_val/` |
| `eval_other_birds.py` | 其他鸟误报率评估 |
| `infer_pc.py` | PC 端快速推理（ultralytics） |
| `predict_full_recordings.py` | 完整录音逐窗离线预测 |
| `split_recordings.py` | 划分完整录音 / 生成事件分组 |
| `pull_board.py` | 从 PYNQ-Z2 拉取视频和截图（paramiko/scp） |
| `best.pt` | YOLOv8n PyTorch 权重（留档） |
| `e2e_board.py` | **板端** GEMM 端到端验证（wav→硬件conv1→numpy其余→分数）；`--bench N` 测公平加速比 |
| `gemm_board.py` | **板端**裸 GEMM 对拍（a/b→硬件→c，对 c_ref） |
| `make_board_data.py` | **PC** 生成 GEMM 测试数据 a/b/c_ref.bin |
| `label_audio_events.py` | **PC** 半自动真值标注（能量检测生成事件草稿+核对图） |
| `build_truth_review.py` | **PC** 生成真值核对页面 `data/test_audio/positive/truth_draft/review_events.html`（听音 → 保留/删除/补漏 → 导出 `events_truth.csv`） |
| `eval_recall.py` | **PC** 事件级召回率评估（读人工真值 + 逐窗分数） |

## D. 历史 / 替代版本（未在最终部署使用，可删）

| 文件 | 说明 |
|------|------|
| `inmp441_predict.py` / `_bridge.py` / `_fast.py` / `_latest.py` | 音频主程序的早期版本，最终定为 `_time.py`（正式部署）/ `_pause.py`（调试） |
| `audio_listener_board.py` | sounddevice 采集方案（替代，未采用） |
| `audio_trigger.py` | 早期鸟鸣触发器 |
| `sound_board.py` | arecord 采集方案（替代，未采用） |
| `infer_board.py` | TFLite 推理方案（旧，未采用） |
| `train_binary.py` | 音频训练旧版，已被 `_fixed` 取代 |
| `debug_miss.py` | 调试辅助脚本 |
| `sound_config.json` | 旧声音配置 |

> D 类仅为开发过程留痕，不影响 A 类部署；如追求提交包精简可整体删除（均为文本，体积很小）。
