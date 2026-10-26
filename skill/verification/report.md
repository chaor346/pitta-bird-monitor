# 技能包验证报告

生成时间：2026-10-26 20:12:19　项目根目录：`D:\嵌赛\pitta_bird_monitor`

| 检查项 | 结果 | 说明 |
|---|---|---|
| hwh_probe.py --self-test | PASS | 退出码 0，耗时 0.17s |
| bd_lint.py --self-test | PASS | 退出码 0，耗时 0.16s |
| vivado_report.py --self-test | PASS | 退出码 0，耗时 0.19s |
| golden_compare.py --self-test | PASS | 退出码 0，耗时 0.57s |
| hwh 解析 | PASS | 退出码 0，耗时 0.14s |
| 块图检查 | PASS | 退出码 0，耗时 0.17s |
| DMA 测试计划 | PASS | 退出码 0，耗时 0.20s |
| 综合/实现指标 | PASS | 退出码 0，耗时 0.19s |
| 构建脚本可复现 | PASS | 2 个 add_files 引用全部存在（另有 1 个含 tcl 变量的路径未静态核对） |
| 命名规范（纯英文） | PASS | 所有目录与文件名均符合英文命名要求 |

合计：PASS=10 FAIL=0 SKIP=0 WARN=0

完整输出见同目录 `selfcheck.log`。
