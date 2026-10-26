#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bd_lint.py —— 通用 Vivado 块图静态检查（不绑定任何具体工程/IP 名称）

为什么需要它
    Vivado 的 `validate_bd_design` 只保证"图在语法和规则上成立"，不保证"图符合你的
    意图"：AXI 主口忘了连、时钟域混了、AXI-Stream 方向接反、DMA 流位宽与内存位宽不等
    且没开 DRE——这些都能通过 Validate Design，然后在板子上表现成"数据全 0 / DMA 不动 /
    读到固定值"，排查成本极高。本脚本把这些意图检查固化成规则，可在综合前跑。

两种模式
    --tcl   ：直接读 build.tcl / 导出的 bd tcl，检查结构与配置（综合前可用）
    --hwh   ：读综合后的 .hwh，检查真实连通性（哪些输入口真的没人驱动）
    两者可同时给，互相补充；.hwh 的连通性是事实，tcl 是意图。

用法
    python3 bd_lint.py --tcl build/build.tcl
    python3 bd_lint.py --hwh build/inmp441.hwh --xdc src/fpga/inmp441_pmodb.xdc
    python3 bd_lint.py --tcl build/build.tcl --hwh build/inmp441.hwh --json out.json
    python3 bd_lint.py --self-test

退出码
    0 无 ERROR；1 有 ERROR；2 参数错误
"""

from __future__ import print_function

import argparse
import json
import os
import re
import sys

RE_PINS = re.compile(r'\[get_bd_pins\s+([^\]]+?)\s*\]')
RE_INTF = re.compile(r'\[get_bd_intf_pins\s+([^\]]+?)\s*\]')
RE_CELLS = re.compile(r'\[get_bd_cells\s+([^\]]+?)\s*\]')
RE_PORTS = re.compile(r'\[get_bd_ports\s+([^\]]+?)\s*\]')


# ----------------------------------------------------------------------------
# tcl 解析
# ----------------------------------------------------------------------------


def _clean(token):
    return token.strip().strip('{}').strip()


def _strip_comment(line):
    """去掉行内注释：只在 '#' 前面是空白（不在 token 内）时截断。"""
    for idx, char in enumerate(line):
        if char == '#' and (idx == 0 or line[idx - 1] in ' \t'):
            return line[:idx]
    return line


def load_commands(path):
    """读 tcl，合并行尾 '\\' 续行，返回逐条命令。"""
    text = open(path, 'r', encoding='utf-8', errors='replace').read()
    commands = []
    buffer = ''
    for raw in text.splitlines():
        line = _strip_comment(raw).rstrip()
        if not buffer and not line.strip():
            continue
        if line.endswith('\\'):
            buffer += line[:-1] + ' '
            continue
        commands.append((buffer + line).strip())
        buffer = ''
    if buffer.strip():
        commands.append(buffer.strip())
    return commands


def parse_bd_tcl(path):
    """把 bd tcl 解析成结构化信息。"""
    cells = []
    nets = []
    intf_nets = []
    automations = []
    externals = []
    addresses = []

    for cmd in load_commands(path):
        if not cmd:
            continue
        verb = cmd.split(None, 1)[0]

        if verb == 'create_bd_cell':
            kind = re.search(r'-type\s+(\S+)', cmd)
            vlnv = re.search(r'-vlnv\s+(\S+)', cmd)
            ref = re.search(r'-reference\s+(\S+)', cmd)
            cells.append({
                'name': _clean(cmd.split()[-1]),
                'type': kind.group(1) if kind else '',
                'vlnv': vlnv.group(1) if vlnv else (ref.group(1) if ref else ''),
                'reference': ref.group(1) if ref else '',
                'config': {},
            })
        elif verb == 'connect_bd_net':
            pins = [p for p in (_clean(x) for x in RE_PINS.findall(cmd)) if p]
            if pins:
                nets.append({'pins': pins, 'command': cmd})
        elif verb == 'connect_bd_intf_net':
            pins = [p for p in (_clean(x) for x in RE_INTF.findall(cmd)) if p]
            if pins:
                intf_nets.append({'pins': pins, 'command': cmd})
        elif verb in ('make_bd_pins_external', 'make_bd_intf_pins_external'):
            found = RE_PINS.findall(cmd) or RE_INTF.findall(cmd)
            for item in found:
                externals.append(_clean(item))
        elif verb == 'apply_bd_automation':
            rule = re.search(r'-rule\s+(\S+)', cmd)
            pair = []
            for key in ('Master', 'Slave'):
                match = re.search(key + r'\s*\{([^}]*)\}', cmd)
                if match:
                    pair.append(_clean(match.group(1)))
            target = RE_INTF.findall(cmd)
            if target:
                pair.append(_clean(target[-1]))
            automations.append({'rule': rule.group(1) if rule else '', 'pins': pair})
        elif verb == 'set_property':
            pairs = re.findall(r'(CONFIG\.[A-Za-z0-9_]+)\s+\{?([^{}\s]+)\}?', cmd)
            targets = [_clean(t) for t in RE_CELLS.findall(cmd)]
            if pairs and targets:
                for name in targets:
                    for cell in cells:
                        if cell['name'] == name:
                            for key, value in pairs:
                                cell['config'][key] = value
        elif verb == 'assign_bd_address':
            offset = re.search(r'-offset\s+(\S+)', cmd)
            rng = re.search(r'-range\s+(\S+)', cmd)
            segs = re.findall(r'\[get_bd_addr_segs\s+([^\]]+?)\s*\]', cmd)
            if segs:
                addresses.append({
                    'seg': _clean(segs[0]),
                    'offset': offset.group(1) if offset else None,
                    'range': rng.group(1) if rng else None,
                })

    return {'cells': cells, 'nets': nets, 'intf_nets': intf_nets,
            'automations': automations, 'externals': externals,
            'addresses': addresses, 'source': os.path.abspath(path)}


# ----------------------------------------------------------------------------
# tcl 结构检查
# ----------------------------------------------------------------------------


def _to_int(value):
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        return None


def _strip_index(pin):
    """'axi_dma_0/S_AXIS_S2MM' 保留原样；去掉可能的 [0] 位索引。"""
    return re.sub(r'\[\d+\]$', '', pin)


def lint_tcl(bd, xdc_path=None):
    problems = []

    def add(severity, rule, message):
        problems.append({'severity': severity, 'rule': rule, 'message': message})

    # T001 悬空网络：一条 connect_bd_net 只连了一个 pin
    for net in bd['nets']:
        if len(net['pins']) < 2:
            add('error', 'T001', '网络只连了 1 个引脚，属于悬空连接：%s' % net['pins'][0])

    # T002 AXI-Stream 方向冲突
    for net in bd['intf_nets']:
        if len(net['pins']) != 2:
            continue
        low = [p.lower() for p in net['pins']]
        if all(p.endswith('m_axis') or '/m_axis_' in p for p in low):
            add('error', 'T002', 'AXI-Stream 两端都是 m_axis（源对源）：%s' % ' <-> '.join(net['pins']))
        if all(p.endswith('s_axis') or '/s_axis_' in p for p in low):
            add('error', 'T002', 'AXI-Stream 两端都是 s_axis（汇对汇）：%s' % ' <-> '.join(net['pins']))

    # T003 同一网络里混用高有效 reset 与低有效 aresetn
    for net in bd['nets']:
        low = [p.lower() for p in net['pins']]
        has_n = any('aresetn' in p or 'resetn' in p for p in low)
        has_pos = any(('reset' in p or 'rst' in p) and 'resetn' not in p and 'aresetn' not in p
                      for p in low)
        if has_n and has_pos:
            add('error', 'T003',
                '同一网络同时接了低有效复位和高有效复位，极性冲突：%s' % ' <-> '.join(net['pins']))

    # T005 AXI DMA 流位宽 vs 内存位宽（未开 DRE 时必须相等）
    for cell in bd['cells']:
        if 'axi_dma' not in (cell['vlnv'] or ''):
            continue
        cfg = cell['config']
        for ch in ('MM2S', 'S2MM'):
            if str(cfg.get('CONFIG.c_include_%s' % ch.lower(), '1')) != '1':
                continue
            stream = _to_int(cfg.get('CONFIG.c_%s_axis_%s_tdata_width'
                                     % ('m' if ch == 'MM2S' else 's', ch.lower())))
            mm = _to_int(cfg.get('CONFIG.c_m_axi_%s_data_width' % ch.lower()))
            dre = str(cfg.get('CONFIG.c_include_%s_dre' % ch.lower(), '0'))
            if stream is None or mm is None:
                continue
            if stream != mm and dre == '0':
                add('error', 'T005',
                    '%s：流位宽 %d bit 与内存位宽 %d bit 不等且未开 DRE。'
                    '这种配置会通过 Validate Design，但上板会丢数据或直接挂死；'
                    '要么让两个位宽相等，要么打开 Enable DRE。'
                    % (cell['name'], stream, mm))
            if stream > mm and dre == '1':
                add('warn', 'T005',
                    '%s：%s 流位宽 %d > 内存位宽 %d，开了 DRE 可以工作，但带宽会被内存侧限制'
                    % (cell['name'], ch, stream, mm))

    # T006 创建了却从未参与任何连接（漏连的 IP）
    touched = set()
    for net in bd['nets'] + bd['intf_nets']:
        for pin in net['pins']:
            touched.add(pin.split('/')[0])
    for auto in bd['automations']:
        for pin in auto['pins']:
            touched.add(pin.split('/')[0])
    for item in bd['externals']:
        touched.add(item.split('/')[0])
    for cell in bd['cells']:
        ref = cell['reference'] or ''
        if cell['name'] not in touched and ref not in touched:
            add('warn', 'T006', 'IP %s (%s) 创建后没有参与任何连接'
                % (cell['name'], cell['vlnv'] or cell['type']))

    # T007 外部端口未在 XDC 中约束
    if xdc_path:
        if not os.path.isfile(xdc_path):
            add('warn', 'T007', 'XDC 文件不存在：%s' % xdc_path)
        else:
            xdc_text = open(xdc_path, 'r', encoding='utf-8', errors='replace').read()
            constrained = set()
            for block in re.findall(r'get_ports\s*\{([^}]*)\}', xdc_text):
                constrained.update(n.strip() for n in block.split() if n.strip())
            for name in re.findall(r'get_ports\s+([A-Za-z_][\w\[\]\.]*)', xdc_text):
                constrained.add(name.strip())
            for item in bd['externals']:
                port = item.split('/')[-1]
                if port not in constrained:
                    add('warn', 'T007',
                        '块图对外端口 %s 在 %s 中没有 find 到 PACKAGE_PIN 约束；'
                        'Make External 后的端口名必须与 XDC 里的 get_ports 名一致'
                        % (port, os.path.basename(xdc_path)))

    # T008 自定义模块（module_ref）提示
    modules = [c['name'] for c in bd['cells'] if c['reference']]
    if modules:
        add('info', 'T008', '自定义模块引用：%s（需确认综合时能找到源码，且端口名与 XDC/顶层一致）'
            % ', '.join(modules))

    # T009 多个时钟源
    sources = set()
    for net in bd['nets']:
        for pin in net['pins']:
            low = _strip_index(pin).lower()
            if 'fclk_clk' in low or 'clk_out' in low:
                sources.add(pin)
    if len(sources) > 1:
        add('warn', 'T009', '块图里有 %d 个时钟源（%s），确认跨时钟域信号已做同步，'
                             'AXI 接口没有跨域' % (len(sources), ', '.join(sorted(sources))))

    # T010 地址重叠
    ranges = []
    for item in bd['addresses']:
        base, rng = _to_int(item['offset']), _to_int(item['range'])
        if base is not None and rng:
            ranges.append((base, base + rng - 1, item['seg']))
    ranges.sort()
    for prev, cur in zip(ranges, ranges[1:]):
        if cur[0] <= prev[1]:
            add('error', 'T010', '地址重叠：%s [0x%X-0x%X] 与 %s [0x%X-0x%X]'
                % (prev[2], prev[0], prev[1], cur[2], cur[0], cur[1]))

    return problems


# ----------------------------------------------------------------------------
# .hwh 连通性检查
# ----------------------------------------------------------------------------


# 各 IP 家族里"本来就可以不接"的选通/调试/能力位端口。它们悬空是常态，
# 一律按 ERROR 报会让工具在真实工程上满屏噪音，反而没人看。
_OPTIONAL_PORT_RE = re.compile(
    r'(aux_reset_in|mb_debug_sys_rst|dcm_locked|issuecap\d*_en|tie_off|_trig)$', re.I)

# AXI-Stream 的必需握手信号：输入端缺其中任何一个，数据通路就是断的
_STREAM_ESSENTIAL = ('tdata', 'tvalid', 'tready', 'tlast', 'tkeep', 'tstrb')


def _is_optional_port(name):
    return bool(_OPTIONAL_PORT_RE.search(name or ''))


def lint_hwh(db):
    problems = []

    def add(severity, rule, message):
        problems.append({'severity': severity, 'rule': rule, 'message': message})

    external = set()
    for port in db.get('external_ports', []):
        for inst, pin in port.get('connections') or []:
            external.add((inst, pin))

    for ip in db['ips']:
        for port in ip['ports']:
            if port['dir'] != 'I':
                continue
            if port['connections']:
                continue
            if (ip['instance'], port['name']) in external:
                continue
            name = port['name'] or ''
            low = name.lower()
            sigis = port.get('sigis')

            if _is_optional_port(name):
                add('info', 'H005', '%s.%s 未接（该 IP 的可选/调试口，通常可以不接）'
                    % (ip['instance'], name))
            elif sigis == 'clk':
                add('error', 'H001', '%s.%s 是时钟输入但没有驱动' % (ip['instance'], name))
            elif sigis == 'rst':
                add('error', 'H001', '%s.%s 是复位输入但没有驱动' % (ip['instance'], name))
            elif 'axis' in low and any(token in low for token in _STREAM_ESSENTIAL):
                add('error', 'H002', '%s.%s 是 AXI-Stream 必需信号但没连，数据通路断了'
                    % (ip['instance'], name))
            else:
                add('warn', 'H001', '%s.%s 是输入口但没有驱动' % (ip['instance'], name))

    # H003 中断没接
    for ip in db['ips']:
        for port in ip['ports']:
            if port.get('sigis') != 'intr':
                continue
            if not port['connections'] and (ip['instance'], port['name']) not in external:
                add('info', 'H003', '%s.%s 中断未接（用轮询则正常，用中断则需要接 IRQ）'
                    % (ip['instance'], port['name']))

    # H004 寄存器表里 IS_ENABLED=false 的寄存器被当成可用功能
    for item in db.get('checks') or []:
        add(item['severity'], 'H004', '%s：%s' % (item['instance'], item['message']))

    return problems


# ----------------------------------------------------------------------------
# 输出
# ----------------------------------------------------------------------------


def _print(problems, sources):
    order = {'error': 0, 'warn': 1, 'info': 2}
    problems = sorted(problems, key=lambda p: (order.get(p['severity'], 3), p['rule']))
    counts = {'error': 0, 'warn': 0, 'info': 0}
    for item in problems:
        counts[item['severity']] = counts.get(item['severity'], 0) + 1
        print('[%-5s] %-5s %s' % (item['severity'].upper(), item['rule'], item['message']))
    if not problems:
        print('未发现问题。')
    print('\n检查输入：%s' % '；'.join(sources))
    print('汇总：ERROR=%d  WARN=%d  INFO=%d' %
          (counts['error'], counts['warn'], counts['info']))
    if counts['error'] == 0:
        print('结论：未发现阻断性问题。注意本工具只覆盖已固化的规则，'
              '仍应在 Vivado 里跑 validate_bd_design 并做上板验证。')
    else:
        print('结论：存在 ERROR，先修掉再综合。')
    return counts['error']


# ----------------------------------------------------------------------------
# 自检
# ----------------------------------------------------------------------------


_BAD_TCL = """
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_0
set_property -dict [list \\
    CONFIG.c_include_sg {0} \\
    CONFIG.c_include_mm2s {0} \\
    CONFIG.c_include_s2mm {1} \\
    CONFIG.c_s_axis_s2mm_tdata_width {64} \\
    CONFIG.c_m_axi_s2mm_data_width {32} \\
    CONFIG.c_include_s2mm_dre {0} \\
] [get_bd_cells axi_dma_0]
create_bd_cell -type module -reference my_core my_core_0
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_0
connect_bd_net [get_bd_pins my_core_0/aclk]
connect_bd_net [get_bd_pins rst_0/peripheral_aresetn] [get_bd_pins my_core_0/reset]
connect_bd_intf_net [get_bd_intf_pins my_core_0/m_axis] [get_bd_intf_pins axi_dma_0/m_axis]
"""

_GOOD_TCL = """
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_0
set_property -dict [list \\
    CONFIG.c_include_mm2s {0} \\
    CONFIG.c_include_s2mm {1} \\
    CONFIG.c_s_axis_s2mm_tdata_width {32} \\
    CONFIG.c_m_axi_s2mm_data_width {32} \\
    CONFIG.c_include_s2mm_dre {0} \\
] [get_bd_cells axi_dma_0]
create_bd_cell -type module -reference my_core my_core_0
make_bd_pins_external [get_bd_pins my_core_0/sd]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins my_core_0/aclk]
connect_bd_net [get_bd_pins rst_0/peripheral_aresetn] [get_bd_pins my_core_0/aresetn]
connect_bd_intf_net [get_bd_intf_pins my_core_0/m_axis] [get_bd_intf_pins axi_dma_0/S_AXIS_S2MM]
"""


def _ensure_parent(path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)


def _write_tmp(name, text):
    import tempfile
    path = os.path.join(tempfile.mkdtemp(prefix='bd_lint_'), name)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    return path


def self_test():
    import io
    import shutil

    tmpdir = None
    try:
        bad = _write_tmp('bad.tcl', _BAD_TCL)
        tmpdir = os.path.dirname(bad)
        good = _write_tmp('good.tcl', _GOOD_TCL)
        xdc = _write_tmp('pins.xdc',
                         'set_property PACKAGE_PIN T11 [get_ports {sd}]\n')

        bad_bd = parse_bd_tcl(bad)
        good_bd = parse_bd_tcl(good)

        # 续行合并：set_property 的 CONFIG 必须被解析进 cell
        dma = [c for c in good_bd['cells'] if 'axi_dma' in c['vlnv']][0]
        assert dma['config'].get('CONFIG.c_s_axis_s2mm_tdata_width') == '32', dma['config']

        # 旧版脚本的正则只能抓到第一个 pin，这里必须两个都抓到
        stream = [n for n in good_bd['intf_nets'] if 'S_AXIS_S2MM' in ' '.join(n['pins'])]
        assert stream and len(stream[0]['pins']) == 2, stream

        bad_rules = {p['rule'] for p in lint_tcl(bad_bd)}
        for rule in ('T001', 'T002', 'T003', 'T005'):
            assert rule in bad_rules, (rule, bad_rules)

        good_rules = {p['rule'] for p in lint_tcl(good_bd, xdc)}
        for rule in ('T001', 'T002', 'T003', 'T005', 'T007', 'T010'):
            assert rule not in good_rules, (rule, good_rules)

        # 外部端口没约束时应报 T007
        no_xdc = {p['rule'] for p in lint_tcl(good_bd, _write_tmp('empty.xdc', ''))}
        assert 'T007' in no_xdc, no_xdc

        # hwh 模式：用一个输入悬空的假 hwh
        hwh = _write_tmp('conn.hwh', """<?xml version="1.0" encoding="UTF-8"?>
<EDKSYSTEM>
  <SYSTEMINFO ARCH="zynq" DEVICE="7z020" PACKAGE="clg400" SPEEDGRADE="-1" NAME="t"/>
  <EXTERNALPORTS>
    <PORT DIR="IO" NAME="sd" SIGNAME="sd">
      <CONNECTIONS><CONNECTION INSTANCE="core_0" PORT="sd"/></CONNECTIONS>
    </PORT>
  </EXTERNALPORTS>
  <MODULES>
    <MODULE INSTANCE="core_0" FULLNAME="/core_0" VLNV="xilinx.com:module_ref:core:1.0"
            IPTYPE="PERIPHERAL" MODTYPE="core">
      <PORTS>
        <PORT DIR="I" NAME="sd" SIGIS="undef" SIGNAME="sd"/>
        <PORT DIR="I" NAME="aclk" SIGIS="clk" SIGNAME="aclk"/>
        <PORT DIR="I" NAME="s_axis_tdata" SIGIS="undef" SIGNAME="s_axis_tdata"/>
      </PORTS>
    </MODULE>
  </MODULES>
</EDKSYSTEM>
""")
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import hwh_probe
        problems = lint_hwh(hwh_probe.parse_hwh(hwh))
        rules = {(p['rule'], p['severity']) for p in problems}
        assert ('H001', 'error') in rules, rules          # aclk 悬空
        assert ('H002', 'error') in rules, rules          # s_axis 悬空
        assert not any(p['rule'] == 'H001' and 'sd' in p['message'] for p in problems), problems
        print('bd_lint self-test: OK（续行解析/多 pin 捕获/5 类结构规则/XDC 约束/hwh 连通性）')
        return 0
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ----------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description='Vivado 块图静态检查')
    parser.add_argument('--tcl', metavar='FILE', help='build.tcl 或导出的 bd tcl')
    parser.add_argument('--hwh', metavar='FILE', help='综合后的 .hwh（真实连通性）')
    parser.add_argument('--xdc', metavar='FILE', help='引脚约束文件，用于检查外部端口是否被约束')
    parser.add_argument('--json', metavar='PATH', help='把结果写成 JSON')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.tcl and not args.hwh:
        parser.error('至少要给 --tcl 或 --hwh')

    problems = []
    sources = []
    if args.tcl:
        if not os.path.isfile(args.tcl):
            print('找不到 tcl：%s' % args.tcl, file=sys.stderr)
            return 2
        problems += lint_tcl(parse_bd_tcl(args.tcl), args.xdc)
        sources.append(args.tcl)
    if args.hwh:
        if not os.path.isfile(args.hwh):
            print('找不到 hwh：%s' % args.hwh, file=sys.stderr)
            return 2
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import hwh_probe
        problems += lint_hwh(hwh_probe.parse_hwh(args.hwh))
        sources.append(args.hwh)
    if args.xdc:
        sources.append(args.xdc)

    # 同一问题在两种模式可能重复（如 H004 与 hwh_probe 的一致性检查），去重
    seen = set()
    unique = []
    for item in problems:
        key = (item['rule'], item['message'])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    errors = 0
    if not args.quiet:
        errors = _print(unique, sources)
    else:
        errors = sum(1 for p in unique if p['severity'] == 'error')

    if args.json:
        _ensure_parent(args.json)
        with open(args.json, 'w', encoding='utf-8') as handle:
            json.dump({'sources': sources, 'problems': unique}, handle,
                      ensure_ascii=False, indent=2)
        print('已写出 %s' % args.json)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
