# build/ 构建产物

音频 overlay（inmp441）与 GEMM overlay 的 Vivado 构建脚本、bit/hwh 和实现报告。

## 文件

| 文件 | 说明 |
|---|---|
| `build.tcl` | 音频 overlay 一键重建（I²S 接收 + AXI-DMA S2MM） |
| `build_gemm.tcl` | GEMM overlay 一键重建（HLS GEMM 核 + 三路 AXI-DMA） |
| `inmp441.bit` / `.hwh` | 音频 overlay 比特流与硬件描述 |
| `utilization.rpt` / `timing.rpt` / `power.rpt` / `drc_routed.rpt` | 音频 overlay routed 报告 |
| `vivado_project.zip` | 音频 overlay 完整 Vivado 工程打包（可解压直接打开块图） |
| `gemm/` | GEMM overlay 的 bit/hwh、报告与说明，见 `gemm/README.md` |

## 重建

```bash
# 音频 overlay
vivado -mode batch -source build.tcl

# GEMM overlay（自动在英文临时目录建工程，规避中文路径 XIT 问题）
vivado -mode batch -source build_gemm.tcl
```

## 音频 overlay 资源（routed，100 MHz）

- LUT 3.15%，WNS +2.03 ns
- bit/hwh 由 `build.tcl` 导出到本目录
