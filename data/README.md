# data/ 测试数据目录

## test_images/ 图像测试集（精选子集，145 张，14.43MB）

> **这是从完整数据集挑选的演示子集，且全部取自训练池（模型训练时见过）。** 完整数据集：`raw_pitta` 1,302 正样本 + `neg` 380 负样本（321 其他鸟 + 59 纯背景），原始池合计 1,682 张，体积约 600MB，未随包提供。

整合后的清晰结构：

| 目录 | 内容 | 数量 |
|------|------|------|
| `positive/raw/` | 补充正样本带框（中小距离），`pitta_raw_*.jpg` | 30 |
| `positive/annotated/close/` | **近景**带框（框面积 ≥50%，鸟明显大），`pitta_close_*.jpg` | 20 |
| `positive/annotated/medium/` | **中景**带框（框面积 20%–30%），`pitta_medium_*.jpg` | 20 |
| `positive/annotated/far/` | **远景**带框（框面积 3%–8%，鸟明显小），`pitta_far_*.jpg` | 20 |
| `negative/background/` | 纯森林背景（无鸟），`neg_background_*.jpg` | 20 |
| `negative/other_birds/` | 其他鸟类难负样本（均含鸟，验证不误报），`neg_bird_*.jpg` | 30 |
| `board_captured/` | 板端推理输出画面（屏幕翻拍，640×480 PNG），`board_*.png` | 5 |

- 命名统一为 `类别_分组_序号.jpg`（板端图为 `board_序号.png`），工整可排序。
- 正样本：best.onnx 对 1,302 张 raw_pitta 批量标注（conf 0.52、letterbox 320），2026-10-25 复算检出 1,090 张（83.7%）；只在有标注的 1,061 张上算为 99.2%。近/中/远按框面积取明显三档（≥50% / 20–30% / 3–8%）。
- 特异性：380 张负样本（321 其他鸟 + 59 纯背景）2026-10-25 复算 0 误报、最高分 0.0。
- **图像指标口径**：训练池数字（99.2% 检出、86.7% mAP）为模型见过的图自测；`images/val` 260 张中 221 张与训练集字节相同，不构成独立测试集。独立测试见 `test_images/independent/`（266 张网络公开图，图像级召回 96.2%）。完整重算过程见 `test_images/eval_val/README.md`。
- **详细的来源、筛选方法、完整数据集对比、命名规范、复现方法见 `test_images/README.md`。**

## test_audio/ 音频测试集（9 段正样本 + 18 段负样本）

| 目录 | 内容 | 段数 | 时长 |
|------|------|-----:|-----:|
| `positive/` | 仙八色鸫鸣声（Xeno-canto / Macaulay 原始录音，按质量指标筛选） | 9 | 753.2 s |
| `negative/ambient/` | 环境音（室内嗡声、雨、风、树叶、脚步、人群、键盘、车流） | 10 | 485.0 s |
| `negative/other_birds/` | 其他鸟鸣（8 个不同属 / 种，从原始包 54 种中优选） | 8 | 575.0 s |

- 正样本 1,474 个 2 s 窗口（跳 0.5 s），score≥0.5 的 724 个，板端阈值 0.985 下 500 个，候选事件 150 个。
- 负样本 2,063 个窗口，**全部低于 0.5，误报 0 个，最高分 0.0329**。
- 每段配 `_predictions.csv`（逐窗 score / rms）与 `_events.csv`（候选事件），由 `src/ps/audio_numpy.py` 在 PC 上生成。
- 命名规则 `<split>_<class>_<detail>`（`pos_pitta_nympha_*` / `neg_ambient_*` / `neg_bird_*`），全目录清单见 `test_audio/manifest.csv`。
- 音频保留原始码流（mp3 / wav），未做重采样或降噪；推理时才重采样到 32 kHz。环境音负样本本身是 32 kHz 单声道 WAV，与板端采样率一致。
- 筛选规则（正样本 7 条阈值、负样本体积/动态范围/频带规则）、排除清单、误报结果见 `test_audio/README.md`。
- 仍待补：板端 32000 Hz 实测录音（`/home/xilinx/results_av/*.wav`），以及 46 种未导入的鸟（体积/质量原因）。
- 事件级召回率：9 段 155 个人耳核对事件，`eval_recall.py` 实测 **97.4%**（板端阈值 0.985）
  / 98.1%（0.5），窗口级 90.6% / 95.4%；4 处漏检中 2 处在 `xc188359`。
  真值是录音母本口径（不是板端实录），明细与限制见 `positive/recall_results/README.md`。

## gemm/ GEMM 加速器测试数据

| 文件 | 内容 |
|------|------|
| `bird_sample.wav` | 32 kHz 单声道测试音频（2 s） |
| `a.bin` / `b.bin` / `c_ref.bin` | 全量 GEMM 输入 A/B 与参考输出 C（M=12864 K=9 N=16，int16 Q12） |
| `a_small.bin` / `b_small.bin` / `c_ref_small.bin` | 小数据档（M=32），用于快速验证 |

- 由 `src/ps/make_board_data.py` 在 PC 端生成；板端 `gemm_board.py` 用 a/b 跑出 C 并与 c_ref 对拍，`e2e_board.py` 用 bird_sample.wav 做端到端验证。
- 构建产物与已实测结果见 `build/gemm/README.md`。

## comparison.csv 指标口径

| 列 | 说明 |
|----|------|
| 指标名称 / 类别 | 指标名 + 类别（核心/AI/FPGA/可靠性） |
| 数值 / 单位 | 实测值（FPGA 资源来自 build/*.rpt） |
| 测量条件 | 测试时的参数与环境 |
| 测试次数 | 实测样本数 |
| 证据文件 | 支撑证据的相对路径 |

## 第三方素材来源与许可证（重要）

仓库根目录的 MIT 许可证**只覆盖本项目自写的代码与文档**，不覆盖下列第三方素材；
公开仓库/提交包里保留这些文件时，请按各自原始许可标注来源。

| 素材 | 来源 | 许可状态 |
|---|---|---|
| `test_images/` 全部图片、训练用 `raw_pitta` / `neg` | iNaturalist 公开观测记录（`src/ps/01_collect_images.py` 等采集脚本） | 逐条目不同（CC BY / CC BY-NC / 保留所有权利），以原观测页为准；本仓库未逐张附带许可声明 |
| `test_audio/positive/` 9 段 | Xeno-canto（文件名 `xc*`）与 Macaulay Library（文件名 `ml*`）原始录音 | 按各录音条目页的许可使用；XC 多为 CC BY-NC-SA 系列，ML 逐条不同 |
| `test_audio/negative/other_birds/` 8 段 | 同上（XC / ML 记录的**其他鸟种**） | 同上 |
| `test_audio/negative/ambient/` 10 段 | 公共音效素材与自录，导入时的压缩包内未逐条标注来源页 | **待补来源链接与许可**，公开发布前需补齐 |
| `src/ps/best_ncnn.*`、`audio_model.npz` | 本项目训练产物（YOLOv8n / 三层 CNN） | 随本仓库 MIT 发布；YOLOv8 训练框架本身为 AGPL-3.0（Ultralytics），仅作依赖使用、未重新分发其代码 |

> 交付前建议：在仓库 README 或 `data/README.md` 里补一张"录音编号 → 原始页面链接"的对照表
> （27 段音频共 27 行即可），这是开源合规最容易被打回的一点，也是评委核对数据来源最直接的入口。
