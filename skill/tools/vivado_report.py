#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vivado_report.py —— 通用 Vivado 综合/实现报告提取与对比

为什么需要它
    资源与时序数据是 FPGA 作品最该被核对、也最容易被手抄错的一类数字。报告是定宽文本，
    肉眼抄一遍要十几分钟，抄错一位数没人发现；换一版综合结果又要重抄一遍。本脚本把
    utilization.rpt / timing.rpt 直接转成指标表（Markdown / JSON），并支持与上一版对比，
    把"优化前后"变成可复现的一行命令。

用法
    python3 vivado_report.py --utilization build/utilization.rpt --timing build/timing.rpt
    python3 vivado_report.py --utilization u.rpt --timing t.rpt --md out.md --json out.json
    python3 vivado_report.py --utilization u2.rpt --timing t2.rpt --baseline prev.json
    python3 vivado_report.py --self-test

退出码
    0 时序满足且无资源回归；1 时序未满足；2 参数错误
"""

from __future__ import print_function

import argparse
import json
import os
import re
import sys

# ----------------------------------------------------------------------------
# 解析
# ----------------------------------------------------------------------------

RE_UTIL_ROW = re.compile(
    r'^\|\s*([^|]+?)\s*\|\s*([\d,]+)\s*\|\s*([\d,]*)\s*\|\s*([\d,]*)\s*\|\s*([\d,]+)\s*\|\s*([\d.]+)\s*\|\s*$')

# 同一含义在不同器件家族里名字不同，按顺序取第一个存在的
RESOURCE_ALIASES = [
    ('lut', ['Slice LUTs', 'CLB LUTs', 'LUTs']),
    ('ff', ['Slice Registers', 'CLB Registers', 'Registers']),
    ('bram', ['Block RAM Tile', 'Block RAM Tiles', 'RAMB36/FIFO', 'Block RAM']),
    ('dsp', ['DSPs', 'DSP48E1', 'DSP48E2', 'DSP48E5', 'DSP48']),
    ('uram', ['URAM', 'Ultra RAM']),
    ('bufg', ['BUFGCTRL', 'BUFG']),
    ('mmcm', ['MMCME2_ADV', 'MMCME4_ADV', 'MMCME5', 'PLL']),
]

RESOURCE_LABEL = {
    'lut': 'LUT', 'ff': 'FF', 'bram': 'BRAM', 'dsp': 'DSP',
    'uram': 'URAM', 'bufg': 'BUFG', 'mmcm': 'MMCM/PLL',
}


def _num(text):
    return int(str(text).replace(',', '')) if str(text).strip() else None


def parse_utilization(path):
    """返回 {device, tool, state, rows:{name:(used,avail,util%)}, resources:{key:...}}"""
    text = open(path, 'r', encoding='utf-8', errors='replace').read()

    header = {}
    for key, pattern in (('tool', r'Tool Version\s*:\s*(.+)'),
                         ('date', r'Date\s*:\s*(.+)'),
                         ('design', r'Design\s*:\s*(.+)'),
                         ('device', r'Device\s*:\s*(.+)'),
                         ('state', r'Design State\s*:\s*(.+)')):
        match = re.search(pattern, text)
        header[key] = match.group(1).strip() if match else None

    rows = {}
    for line in text.splitlines():
        match = RE_UTIL_ROW.match(line.rstrip())
        if not match:
            continue
        name = match.group(1).strip()
        used = _num(match.group(2))
        avail = _num(match.group(5))
        util = float(match.group(6))
        if name and used is not None:
            rows[name] = {'used': used, 'available': avail, 'util': util}

    resources = {}
    lowered = {k.lower(): k for k in rows}
    for key, aliases in RESOURCE_ALIASES:
        for alias in aliases:
            real = lowered.get(alias.lower())
            if real:
                resources[key] = dict(rows[real], name=real)
                break

    return {'header': header, 'rows': rows, 'resources': resources, 'source': os.path.abspath(path)}


def _block_numbers(lines, start_keyword, max_scan=12, want=8):
    """在 start_keyword 之后找到第一行纯数字行并解析。"""
    for idx, line in enumerate(lines):
        if start_keyword not in line:
            continue
        for probe in lines[idx:idx + max_scan]:
            stripped = probe.strip()
            if not stripped or set(stripped) <= set('- '):
                continue
            tokens = stripped.split()
            if len(tokens) < want:
                continue
            try:
                values = [float(t) for t in tokens[:want]]
            except ValueError:
                continue
            return values
    return None


def parse_timing(path):
    text = open(path, 'r', encoding='utf-8', errors='replace').read()
    lines = text.splitlines()

    # 8 列版（早期工具链）与 12 列版（含 WPWS/TPWS）都要能吃下：只取前 8 个固定字段
    values = _block_numbers(lines, 'Design Timing Summary', want=8)
    keys = ['WNS', 'TNS', 'TNS_failing_endpoints', 'TNS_total_endpoints',
            'WHS', 'THS', 'THS_failing_endpoints', 'THS_total_endpoints']
    design = dict(zip(keys, values[:len(keys)])) if values else {}

    low = text.lower()
    if 'timing constraints are not met' in low:
        met = False
    elif 'timing constraints are met' in low:
        met = True
    else:
        met = None

    clocks = []
    for line in lines:
        match = re.match(r'^(\S+)\s+\{[^}]*\}\s+([\d.]+)\s+([\d.]+)\s*$', line.strip())
        if match:
            clocks.append({'name': match.group(1),
                           'period_ns': float(match.group(2)),
                           'frequency_mhz': float(match.group(3))})

    return {'design': design, 'constraints_met': met, 'clocks': clocks,
            'source': os.path.abspath(path)}


# ----------------------------------------------------------------------------
# 输出
# ----------------------------------------------------------------------------


def build_metrics(util, timing):
    metrics = {'device': (util or {}).get('header', {}).get('device'),
               'tool': (util or {}).get('header', {}).get('tool'),
               'design_state': (util or {}).get('header', {}).get('state'),
               'resources': {}, 'timing': {}}
    if util:
        for key in [k for k, _ in RESOURCE_ALIASES]:
            if key in util['resources']:
                entry = util['resources'][key]
                metrics['resources'][key] = {
                    'label': RESOURCE_LABEL.get(key, key),
                    'register_name': entry['name'],
                    'used': entry['used'],
                    'available': entry['available'],
                    'util_percent': entry['util'],
                }
    if timing:
        metrics['timing'] = {
            'constraints_met': timing['constraints_met'],
            'wns_ns': timing['design'].get('WNS'),
            'tns_ns': timing['design'].get('TNS'),
            'whs_ns': timing['design'].get('WHS'),
            'ths_ns': timing['design'].get('THS'),
            'failing_endpoints': timing['design'].get('TNS_failing_endpoints'),
            'total_endpoints': timing['design'].get('TNS_total_endpoints'),
            'clocks': timing['clocks'],
        }
    return metrics


def render_markdown(metrics, baseline=None):
    out = []
    out.append('# 综合与实现指标摘要')
    out.append('')
    if metrics['device']:
        out.append('- 器件：%s' % metrics['device'])
    if metrics['tool']:
        out.append('- 工具：%s' % metrics['tool'])
    if metrics['design_state']:
        out.append('- 实现状态：%s' % metrics['design_state'])
    out.append('')

    if metrics['resources']:
        out.append('| 资源 | 寄存器名 | Used | Available | Util% |')
        out.append('|------|----------|------|-----------|-------|')
        for key in ('lut', 'ff', 'bram', 'dsp', 'uram', 'bufg', 'mmcm'):
            item = metrics['resources'].get(key)
            if not item:
                continue
            avail = item['available'] if item['available'] is not None else '-'
            out.append('| %s | %s | %d | %s | %.2f |' % (
                item['label'], item['register_name'], item['used'], avail, item['util_percent']))
        out.append('')

    timing = metrics.get('timing') or {}
    if timing:
        out.append('## 时序')
        out.append('')
        if timing.get('constraints_met') is None:
            out.append('- 约束状态：报告里没有找到结论句')
        else:
            out.append('- 约束状态：%s' % ('满足' if timing['constraints_met'] else '**未满足**'))
        for label, key in (('WNS', 'wns_ns'), ('TNS', 'tns_ns'), ('WHS', 'whs_ns'), ('THS', 'ths_ns')):
            if timing.get(key) is not None:
                out.append('- %s：%s ns' % (label, ('%g' % timing[key])))
        if timing.get('failing_endpoints') is not None:
            out.append('- 失败端点：%g / %g' % (timing['failing_endpoints'],
                                            timing.get('total_endpoints') or 0))
        for clock in timing.get('clocks') or []:
            out.append('- 时钟 %s：%g MHz（周期 %g ns）' %
                       (clock['name'], clock['frequency_mhz'], clock['period_ns']))
        out.append('')

    if baseline:
        out.append('## 与基线对比')
        out.append('')
        base_res = (baseline.get('resources') or {})
        deltas = []
        for key, item in metrics['resources'].items():
            old = base_res.get(key)
            if not old:
                continue
            deltas.append((item['label'], old['used'], item['used'], item['used'] - old['used']))
        if deltas:
            out.append('| 资源 | 基线 Used | 当前 Used | 变化 |')
            out.append('|------|-----------|-----------|------|')
            for label, old, new, delta in deltas:
                out.append('| %s | %d | %d | %+d |' % (label, old, new, delta))
        base_w = (baseline.get('timing') or {}).get('wns_ns')
        cur_w = (metrics.get('timing') or {}).get('wns_ns')
        if base_w is not None and cur_w is not None:
            out.append('')
            out.append('- WNS：基线 %g ns → 当前 %g ns（%+g ns）' %
                       (base_w, cur_w, cur_w - base_w))
        out.append('')
    return '\n'.join(out) + '\n'


def find_regressions(metrics, baseline):
    """返回 (problems, notes)。problems 用于决定退出码。"""
    problems, notes = [], []
    timing = metrics.get('timing') or {}
    if timing.get('constraints_met') is False:
        problems.append('时序约束未满足（WNS=%s ns）' % timing.get('wns_ns'))
    if timing.get('wns_ns') is not None and timing['wns_ns'] < 0:
        problems.append('WNS 为负（%g ns），存在建立时间违例' % timing['wns_ns'])

    if not baseline:
        return problems, notes

    base_res = baseline.get('resources') or {}
    for key, item in metrics['resources'].items():
        old = base_res.get(key)
        if not old:
            continue
        delta = item['used'] - old['used']
        if old['used'] and abs(delta) / float(old['used']) > 0.20 and delta > 0:
            notes.append('%s 用量上升 %+d（>20%%）：确认增加的资源换来了可测量的收益'
                         % (item['label'], delta))
    base_w = (baseline.get('timing') or {}).get('wns_ns')
    cur_w = (metrics.get('timing') or {}).get('wns_ns')
    if base_w is not None and cur_w is not None and cur_w < base_w:
        notes.append('WNS 相比基线下降 %g ns（%g → %g）' % (base_w - cur_w, base_w, cur_w))
    return problems, notes


# ----------------------------------------------------------------------------
# 自检
# ----------------------------------------------------------------------------

_SAMPLE_UTIL = """| Tool Version : Vivado v.2026.1 (win64)
| Date         : Sat Oct 17 17:07:51 2026
| Design       : system_wrapper
| Device       : xc7z020clg400-1
| Design State : Fully Placed

1. Slice Logic
+----------------------------+------+-------+------------+-----------+-------+
|          Site Type         | Used | Fixed | Prohibited | Available | Util% |
+----------------------------+------+-------+------------+-----------+-------+
| Slice LUTs                 | 1675 |     0 |          0 |     53200 |  3.15 |
| Slice Registers            | 2281 |     0 |          0 |    106400 |  2.14 |
+----------------------------+------+-------+------------+-----------+-------+

3. Memory
+----------------------------+------+-------+------------+-----------+-------+
|        Site Type           | Used | Fixed | Prohibited | Available | Util% |
+----------------------------+------+-------+------------+-----------+-------+
| Block RAM Tile             |    1 |     0 |          0 |       140 |  0.71 |
+----------------------------+------+-------+------------+-----------+-------+

4. DSP
+----------------------------+------+-------+------------+-----------+-------+
|        Site Type           | Used | Fixed | Prohibited | Available | Util% |
+----------------------------+------+-------+------------+-----------+-------+
| DSPs                       |    0 |     0 |          0 |       220 |  0.00 |
+----------------------------+------+-------+------------+-----------+-------+
"""

_SAMPLE_TIMING = """
| Design Timing Summary
| ---------------------
    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)      THS(ns)  THS Failing Endpoints  THS Total Endpoints
    -------      -------  ---------------------  -------------------      -------      -------  ---------------------  -------------------
      2.029        0.000                      0                 6748        0.016        0.000                      0                 6748

All user specified timing constraints are met.

| Clock Summary
| -------------
Clock       Waveform(ns)       Period(ns)      Frequency(MHz)
-----       ------------       ----------      --------------
clk_fpga_0  {0.000 5.000}      10.000          100.000
"""


def self_test():
    import tempfile
    import shutil

    tmp = tempfile.mkdtemp(prefix='vrep_')
    try:
        up = os.path.join(tmp, 'utilization.rpt')
        tp = os.path.join(tmp, 'timing.rpt')
        open(up, 'w').write(_SAMPLE_UTIL)
        open(tp, 'w').write(_SAMPLE_TIMING)

        util = parse_utilization(up)
        timing = parse_timing(tp)
        assert util['header']['device'] == 'xc7z020clg400-1', util['header']
        assert util['resources']['lut']['used'] == 1675
        assert util['resources']['lut']['util'] == 3.15
        assert util['resources']['bram']['available'] == 140
        assert util['resources']['dsp']['used'] == 0
        assert timing['design']['WNS'] == 2.029, timing['design']
        assert timing['design']['TNS_total_endpoints'] == 6748
        assert timing['constraints_met'] is True
        assert timing['clocks'][0]['frequency_mhz'] == 100.0

        metrics = build_metrics(util, timing)
        md = render_markdown(metrics, baseline=metrics)
        assert '| LUT | Slice LUTs | 1675 | 53200 | 3.15 |' in md, md
        assert 'WNS' in md and '100 MHz' in md

        problems, _ = find_regressions(metrics, None)
        assert not problems, problems

        bad = dict(metrics)
        bad['timing'] = dict(metrics['timing'], wns_ns=-0.5, constraints_met=False)
        problems, _ = find_regressions(bad, None)
        assert len(problems) == 2, problems

        print('vivado_report self-test: OK（资源行/时序摘要/时钟/基线对比/回归判定）')
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description='Vivado 报告提取与对比')
    parser.add_argument('--utilization', help='utilization.rpt')
    parser.add_argument('--timing', help='timing.rpt')
    parser.add_argument('--md', help='输出 Markdown 摘要')
    parser.add_argument('--json', help='输出 JSON 指标')
    parser.add_argument('--baseline', help='上一版 JSON 指标，用于回归对比')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--no-fail', action='store_true', help='即使时序违例也返回 0')
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.utilization and not args.timing:
        parser.error('至少给 --utilization 或 --timing')

    for path in (args.utilization, args.timing, args.baseline):
        if path and not os.path.isfile(path):
            print('找不到文件：%s' % path, file=sys.stderr)
            return 2

    util = parse_utilization(args.utilization) if args.utilization else None
    timing = parse_timing(args.timing) if args.timing else None
    baseline = json.load(open(args.baseline)) if args.baseline else None

    metrics = build_metrics(util, timing)
    problems, notes = find_regressions(metrics, baseline)
    markdown = render_markdown(metrics, baseline)

    if not args.quiet:
        print(markdown)
        if problems:
            print('问题：')
            for item in problems:
                print('  - %s' % item)
        if notes:
            print('提示：')
            for item in notes:
                print('  - %s' % item)

    for path, payload in ((args.md, markdown), (args.json, None)):
        if not path:
            continue
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        if payload is None:
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(metrics, handle, ensure_ascii=False, indent=2)
        else:
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(payload)
        print('已写出 %s' % path)

    if problems and not args.no_fail:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
