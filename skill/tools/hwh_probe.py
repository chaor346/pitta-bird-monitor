#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hwh_probe.py —— 通用 PYNQ .hwh 硬件描述解析与驱动骨架生成

适用范围
    任意 PYNQ Overlay 导出的 .hwh（EDKSYSTEM XML），Zynq-7000 / Zynq UltraScale+ /
    Kria 系列通用。不依赖本项目任何 IP 名称。

解决什么问题
    PYNQ 生态里最常见的翻车方式之一是"手抄寄存器偏移"：从 UG 或别人的博客里复制
    S2MM_CR=0x30 之类的数字，换一个 IP 版本或换一块板子就全部错位，表现为 DMA 不
    传输、状态位永远读到 0，而错误现场没有任何报错。本脚本把 .hwh 当作唯一事实来源，
    直接从硬件描述里导出实例、基址、寄存器表，并生成驱动骨架，让偏移不再靠记忆。

用法
    python3 hwh_probe.py <overlay.hwh>                    # 人类可读报告
    python3 hwh_probe.py <overlay.hwh> --json out.json    # 机器可读（含端口明细）
    python3 hwh_probe.py <overlay.hwh> --json out.json --compact  # 只写实例/地址/寄存器摘要
    python3 hwh_probe.py <overlay.hwh> --emit-driver drv/ # 生成 <instance>_regs.py
    python3 hwh_probe.py <overlay.hwh> --audit app.py     # 对账源码里的硬编码偏移
    python3 hwh_probe.py --self-test                      # 离线自检（无需板卡/文件）

退出码
    0 正常；1 参数或解析错误；2 --audit 发现未知偏移
"""

from __future__ import print_function

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

# ----------------------------------------------------------------------------
# 解析
# ----------------------------------------------------------------------------


def _props(node):
    """把一个节点下的 <PROPERTY NAME= VALUE=> 收成 dict。"""
    out = {}
    for p in node.findall('PROPERTY'):
        out[p.get('NAME')] = p.get('VALUE')
    return out


def _to_int(value, default=None):
    """'0x40400000' / '4096' / '32' -> int。解析不了返回 default。"""
    if value is None:
        return default
    value = str(value).strip()
    if not value:
        return default
    try:
        return int(value, 0)
    except ValueError:
        try:
            return int(value, 10)
        except ValueError:
            return default


def _norm_instance(mod):
    """返回块图里可寻址的实例名（层次设计用 a.b 形式）。"""
    full = (mod.get('FULLNAME') or '').strip('/')
    inst = mod.get('INSTANCE') or ''
    if full and full != inst:
        return full.replace('/', '.')
    return inst or full


def parse_hwh(path):
    """解析 .hwh，返回结构化 dict。"""
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise SystemExit('无法解析 %s：%s' % (path, exc))
    root = tree.getroot()

    system = dict(root.find('SYSTEMINFO').attrib) if root.find('SYSTEMINFO') is not None else {}
    system = {k.lower(): v for k, v in system.items()}

    # 地址映射：MEMRANGE 里 INSTANCE 是从设备，MASTERVALUE 等字段描述主设备
    memranges = []
    for mr in root.iter('MEMRANGE'):
        memranges.append({
            'instance': mr.get('INSTANCE'),
            'base': _to_int(mr.get('BASEVALUE')),
            'high': _to_int(mr.get('HIGHVALUE')),
            'slave_interface': mr.get('SLAVEBUSINTERFACE'),
            'master_interface': mr.get('MASTERBUSINTERFACE'),
            'memory_type': mr.get('MEMTYPE'),
        })

    ips = []
    for mod in root.iter('MODULE'):
        instance = _norm_instance(mod)
        params = {}
        pnode = mod.find('./PARAMETERS')
        if pnode is not None:
            for p in pnode.findall('PARAMETER'):
                params[p.get('NAME')] = p.get('VALUE')

        blocks = []
        for ab in mod.findall('./ADDRESSBLOCKS/ADDRESSBLOCK'):
            regs = []
            for reg in ab.findall('./REGISTERS/REGISTER'):
                props = _props(reg)
                regs.append({
                    'name': reg.get('NAME'),
                    'offset': _to_int(props.get('ADDRESS_OFFSET')),
                    'offset_raw': props.get('ADDRESS_OFFSET'),
                    'size': _to_int(props.get('SIZE')),
                    'access': props.get('ACCESS'),
                    'reset_value': props.get('RESET_VALUE'),
                    'enabled': (props.get('IS_ENABLED', 'true').lower() != 'false'),
                    'description': (props.get('DESCRIPTION') or '').split('\n')[0].strip(),
                })
            regs.sort(key=lambda r: (r['offset'] is None, r['offset']))
            blocks.append({
                'name': ab.get('NAME'),
                'interface': ab.get('INTERFACE'),
                'range': _to_int(ab.get('RANGE')),
                'usage': ab.get('USAGE'),
                'access': ab.get('ACCESS'),
                'registers': regs,
            })

        ports = []
        pnode = mod.find('./PORTS')
        if pnode is not None:
            for pt in pnode.findall('PORT'):
                conns = []
                cnode = pt.find('CONNECTIONS')
                if cnode is not None:
                    for c in cnode.findall('CONNECTION'):
                        conns.append((c.get('INSTANCE'), c.get('PORT')))
                ports.append({
                    'name': pt.get('NAME'),
                    'dir': pt.get('DIR'),
                    'sigis': pt.get('SIGIS'),
                    'sig_name': pt.get('SIGNAME'),
                    'connections': conns,
                    'width': (_to_int(pt.get('LEFT'), 0) - _to_int(pt.get('RIGHT'), 0) + 1)
                    if pt.get('LEFT') is not None else 1,
                    'clk_frequency': _to_int(pt.get('CLKFREQUENCY')),
                })

        mine = [m for m in memranges if m['instance'] == instance]
        base = min([m['base'] for m in mine if m['base'] is not None]) if mine else None
        high = max([m['high'] for m in mine if m['high'] is not None]) if mine else None

        ips.append({
            'instance': instance,
            'vlnv': mod.get('VLNV'),
            'iptype': mod.get('IPTYPE'),
            'modtype': mod.get('MODTYPE'),
            'hwversion': mod.get('HWVERSION'),
            'enabled': (mod.get('IS_ENABLE', '1') != '0'),
            'base': base,
            'high': high,
            'range': (high - base + 1) if (base is not None and high is not None) else None,
            'parameters': params,
            'address_blocks': blocks,
            'ports': ports,
        })

    # 顶层对外端口：其 CONNECTIONS 指回内部端口，用来区分"引出到引脚"和"真的悬空"
    external_ports = []
    extnode = root.find('EXTERNALPORTS')
    if extnode is not None:
        for pt in extnode.findall('PORT'):
            conns = []
            cnode = pt.find('CONNECTIONS')
            if cnode is not None:
                for c in cnode.findall('CONNECTION'):
                    conns.append((c.get('INSTANCE'), c.get('PORT')))
            external_ports.append({'name': pt.get('NAME'), 'dir': pt.get('DIR'),
                                   'connections': conns})

    ips.sort(key=lambda i: (i['base'] is None, i['base'] or 0, i['instance']))
    db = {'system': system, 'ips': ips, 'memranges': memranges,
          'external_ports': external_ports, 'source': os.path.abspath(path)}
    db['checks'] = consistency_checks(db)
    return db


# ----------------------------------------------------------------------------
# 一致性检查
# ----------------------------------------------------------------------------

# AXI DMA 一类带多通道的 IP：通道参数置 0 时，该通道的寄存器通常仍留在寄存器表里，
# 且 IS_ENABLED 有时仍写 true，但硬件并未生成。对着这些寄存器调试是纯粹的浪费时间。
_CHANNEL_PARAMS = {
    'axi_dma': {'MM2S': 'C_INCLUDE_MM2S', 'S2MM': 'C_INCLUDE_S2MM'},
}


def consistency_checks(db):
    """返回告警列表（dict：severity/message）。用于把"能读到寄存器"和"通道真的存在"分开。"""
    out = []
    for ip in db['ips']:
        modtype = (ip['modtype'] or '').lower()
        for prefix, param in _CHANNEL_PARAMS.get(modtype, {}).items():
            raw = str(ip['parameters'].get(param, '1'))
            if raw != '0':
                continue
            live = [r['name'] for b in ip['address_blocks']
                    for r in b['registers']
                    if r['name'].startswith(prefix) and r['enabled']]
            if live:
                out.append({
                    'severity': 'warn',
                    'instance': ip['instance'],
                    'message': (
                        '参数 %s=0，说明 %s 通道未实现，但寄存器表把 %s 标为启用。'
                        '读写这些寄存器不会有任何效果（读回复位值），不要据此判断通道是否工作。'
                        % (param, prefix, ', '.join(live[:4]) + (' 等' if len(live) > 4 else ''))),
                })
        # 复位值全 0 且未启用的寄存器，读出来永远是 0，容易误判成"总线挂死"
        dead = [r['name'] for b in ip['address_blocks']
                for r in b['registers'] if not r['enabled']]
        if dead and len(dead) == sum(len(b['registers']) for b in ip['address_blocks']):
            out.append({
                'severity': 'info',
                'instance': ip['instance'],
                'message': '该实例所有寄存器均为 IS_ENABLED=false，只能当作地址占位，不要当外设使用',
            })
    return out


# ----------------------------------------------------------------------------
# 报告
# ----------------------------------------------------------------------------


def _hex(value):
    return '0x%08X' % value if isinstance(value, int) else '-'


def _short(path):
    """尽量显示相对路径；跨盘符时退回绝对路径，不让显示逻辑打断工具。"""
    try:
        return os.path.relpath(path)
    except ValueError:
        return path


def _ensure_parent(path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)


def print_report(db, stream=sys.stdout):
    sysinfo = db['system']
    w = stream.write
    w('系统：%s %s%s%s  设计名=%s\n' % (
        sysinfo.get('arch', '?'), sysinfo.get('device', '?'),
        sysinfo.get('package', ''), sysinfo.get('speedgrade', ''),
        sysinfo.get('name', '?')))
    w('\n外设实例（按基址排序）\n')
    w('%-28s %-44s %-12s %-10s %s\n' % ('INSTANCE', 'VLNV', 'BASE', 'RANGE', 'EN'))
    for ip in db['ips']:
        w('%-28s %-44s %-12s %-10s %s\n' % (
            ip['instance'], ip['vlnv'] or '-', _hex(ip['base']),
            ip['range'] if ip['range'] is not None else '-',
            'Y' if ip['enabled'] else 'N'))

    for ip in db['ips']:
        blocks = [b for b in ip['address_blocks'] if b['registers']]
        if not blocks:
            continue
        w('\n寄存器表：%s  (%s @ %s)\n' % (ip['instance'], ip['vlnv'], _hex(ip['base'])))
        for b in blocks:
            w('  地址块 %s / 接口 %s / 范围 %s\n' % (b['name'], b['interface'], b['range']))
            w('    %-26s %-10s %-6s %-12s %-10s %s\n' %
              ('REGISTER', 'OFFSET', 'SIZE', 'ACCESS', 'RESET', 'EN'))
            for r in b['registers']:
                w('    %-26s %-10s %-6s %-12s %-10s %s\n' % (
                    r['name'], '0x%X' % r['offset'] if r['offset'] is not None else '-',
                    r['size'] if r['size'] is not None else '-', r['access'] or '-',
                    r['reset_value'] or '-', 'Y' if r['enabled'] else 'N'))
        # 直接点出被禁用的通道，避免对着不存在的寄存器调试
        disabled = [r['name'] for b in blocks for r in b['registers'] if not r['enabled']]
        if disabled:
            w('  提示：以下寄存器 IS_ENABLED=false，对应通道未生成，不要去读写：\n')
            w('        %s\n' % ', '.join(disabled))

    checks = db.get('checks') or []
    if checks:
        w('\n一致性检查（寄存器存在 != 硬件功能存在）\n')
        for item in checks:
            w('  [%s] %s: %s\n' % (item['severity'].upper(), item['instance'], item['message']))


# ----------------------------------------------------------------------------
# 驱动骨架生成
# ----------------------------------------------------------------------------


def _camel(name):
    parts = re.split(r'[^0-9A-Za-z]+', name)
    return ''.join(p[:1].upper() + p[1:] for p in parts if p) or 'Ip'


def emit_driver(db, outdir):
    """为每个带寄存器的实例生成 <instance>_regs.py。"""
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    written = []
    for ip in db['ips']:
        blocks = [b for b in ip['address_blocks'] if b['registers']]
        if not blocks:
            continue
        cls = _camel(ip['instance']) + 'Regs'
        lines = [
            '# -*- coding: utf-8 -*-',
            '"""自动生成，请勿手改。来源：%s' % os.path.basename(db['source']),
            '',
            '实例 %s (%s)  基址 %s' % (ip['instance'], ip['vlnv'], _hex(ip['base'])),
            '',
            '用法（板端）：',
            '    from pynq import Overlay',
            '    ol = Overlay("xxx.bit")',
            '    regs = %s(ol.%s.mmio)' % (cls, ip['instance']),
            '    regs.write("...", 0x1)',
            '"""',
            '',
            'BASE = %s' % (_hex(ip['base'])),
            'RANGE = %r' % (ip['range']),
            '',
            'REGISTERS = {',
        ]
        for b in blocks:
            lines.append('    # 地址块 %s / 接口 %s' % (b['name'], b['interface']))
            for r in b['registers']:
                if r['offset'] is None:
                    continue
                note = '' if r['enabled'] else '   # IS_ENABLED=false（通道未生成）'
                lines.append('    %-28r: %s,%s' % (r['name'], '0x%X' % r['offset'], note))
        lines += [
            '}',
            '',
            'DISABLED = %r' % ([r['name'] for b in blocks for r in b['registers'] if not r['enabled']]),
            '',
            '',
            'class %s(object):' % cls,
            '    """寄存器访问封装；偏移全部来自 .hwh，不手抄。"""',
            '',
            '    BASE = BASE',
            '    RANGE = RANGE',
            '    REGISTERS = REGISTERS',
            '',
            '    def __init__(self, mmio):',
            '        self.mmio = mmio',
            '',
            '    def offset(self, name):',
            '        try:',
            '            return self.REGISTERS[name]',
            '        except KeyError:',
            '            raise KeyError("未知寄存器 %s；可用：%s" % (name, sorted(self.REGISTERS)))',
            '',
            '    def read(self, name):',
            '        return self.mmio.read(self.offset(name))',
            '',
            '    def write(self, name, value):',
            '        self.mmio.write(self.offset(name), value)',
            '',
            '    def wait_until(self, name, mask, expect=None, timeout=1.0):',
            '        """轮询直到 (read(name) & mask) == expect（expect 缺省为 mask）。',
            '',
            '        返回最后一次读到的值；超时抛 RuntimeError，方便定位卡在哪个状态位。',
            '        """',
            '        import time',
            '        if expect is None:',
            '            expect = mask',
            '        deadline = time.time() + timeout',
            '        value = self.read(name)',
            '        while (value & mask) != expect:',
            '            if time.time() > deadline:',
            '                raise RuntimeError(',
            '                    "%s & 0x%X 期望 0x%X，实际 0x%X（超时 %.2fs）"',
            '                    % (name, mask, expect, value & mask, timeout))',
            '            time.sleep(0.001)',
            '            value = self.read(name)',
            '        return value',
            '',
        ]
        path = os.path.join(outdir, '%s_regs.py' % ip['instance'].replace('.', '_'))
        with open(path, 'w') as handle:
            handle.write('\n'.join(lines) + '\n')
        written.append(path)
    return written


# ----------------------------------------------------------------------------
# 硬编码偏移对账
# ----------------------------------------------------------------------------


_PAT_CALL = re.compile(r'\.(?:read|write)\(\s*([A-Za-z_][A-Za-z0-9_]*|0x[0-9A-Fa-f]+|\d+)')
_PAT_ASSIGN = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*=\s*(.+?)\s*$')


def _collect_constants(text):
    """收集模块级常量 NAME = 0x.. / A, B = 0x1, 0x2，用于解析符号化的寄存器偏移。"""
    consts = {}
    for line in text.splitlines():
        line = line.split('#', 1)[0]
        match = _PAT_ASSIGN.match(line)
        if not match:
            continue
        names = [n.strip() for n in match.group(1).split(',')]
        values = [v.strip() for v in match.group(2).split(',') if v.strip()]
        if len(names) != len(values):
            continue
        for name, value in zip(names, values):
            number = _to_int(value)
            if number is not None:
                consts[name] = number
    return consts


def _offset_index(db):
    """偏移 -> ["实例.寄存器", ...]，用于把对账结果翻译成人能看懂的名字。"""
    index = {}
    for ip in db['ips']:
        for block in ip['address_blocks']:
            for reg in block['registers']:
                if reg['offset'] is not None:
                    index.setdefault(reg['offset'], []).append(
                        '%s.%s' % (ip['instance'], reg['name']))
    return index


def audit_offsets(db, paths):
    """扫描源码里 read()/write() 的寄存器偏移（支持字面量与模块级常量），和 .hwh 对账。"""
    index = _offset_index(db)
    known = set(index)

    files = []
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.endswith('.py'):
                    files.append(os.path.join(p, name))
        elif os.path.isfile(p):
            files.append(p)
        else:
            print('跳过不存在的路径：%s' % p, file=sys.stderr)

    if not files:
        print('没有可扫描的 .py 文件')
        return 1

    unknown_total = 0
    scanned = 0
    for path in files:
        text = open(path, 'r', encoding='utf-8', errors='replace').read()
        consts = _collect_constants(text)
        hits = []
        unresolved = 0
        for lineno, line in enumerate(text.splitlines(), 1):
            code = line.split('#', 1)[0]
            for match in _PAT_CALL.finditer(code):
                token = match.group(1)
                number = _to_int(token)
                if number is None:
                    if token in consts:
                        number = consts[token]
                    else:
                        unresolved += 1
                        continue
                hits.append((lineno, number, line.strip()))
        if not hits and not unresolved:
            continue
        scanned += 1
        bad = [h for h in hits if h[1] not in known]
        print('%s：%d 处寄存器偏移引用，命中 %d 处，未能解析 %d 处' %
              (_short(path), len(hits), len(hits) - len(bad), unresolved))
        seen = set()
        for lineno, value, text_line in hits:
            if (lineno, value) in seen or value not in known:
                continue
            seen.add((lineno, value))
            name = ' / '.join(sorted(set(index.get(value, []))))
            print('  行 %-5d 0x%-5X → %s' % (lineno, value, name))
        for lineno, value, text_line in bad:
            unknown_total += 1
            print('  [ERROR] 行 %-5d 0x%-5X 无对应寄存器 | %s' %
                  (lineno, value, text_line[:90]))
    print('\n共扫描 %d 个文件，%d 处偏移与 .hwh 对不上' % (scanned, unknown_total))
    return 1 if unknown_total else 0


# ----------------------------------------------------------------------------
# 自检
# ----------------------------------------------------------------------------


_SAMPLE_HWH = """<?xml version="1.0" encoding="UTF-8"?>
<EDKSYSTEM>
  <SYSTEMINFO ARCH="zynq" DEVICE="7z020" PACKAGE="clg400" SPEEDGRADE="-1" NAME="demo"/>
  <MEMORYMAP>
    <MEMRANGE INSTANCE="demo_dma" BASEVALUE="0x40400000" HIGHVALUE="0x4040FFFF"
               MEMTYPE="REGISTER" SLAVEBUSINTERFACE="S_AXI_LITE"
               MASTERBUSINTERFACE="M_AXI_GP0"/>
  </MEMORYMAP>
  <MODULES>
    <MODULE INSTANCE="demo_dma" FULLNAME="/demo_dma" VLNV="xilinx.com:ip:axi_dma:7.1"
            IPTYPE="PERIPHERAL" MODTYPE="axi_dma" HWVERSION="7.1">
      <PARAMETERS>
        <PARAMETER NAME="C_INCLUDE_S2MM" VALUE="1"/>
        <PARAMETER NAME="C_INCLUDE_MM2S" VALUE="0"/>
      </PARAMETERS>
      <PORTS>
        <PORT DIR="I" NAME="s_axi_lite_aclk" SIGIS="clk" CLKFREQUENCY="100000000"/>
      </PORTS>
      <ADDRESSBLOCKS>
        <ADDRESSBLOCK NAME="Reg" INTERFACE="S_AXI_LITE" RANGE="4096" USAGE="register">
          <REGISTERS>
            <REGISTER NAME="S2MM_DMACR">
              <PROPERTY NAME="ADDRESS_OFFSET" VALUE="0x30"/>
              <PROPERTY NAME="SIZE" VALUE="32"/>
              <PROPERTY NAME="ACCESS" VALUE="read-write"/>
              <PROPERTY NAME="IS_ENABLED" VALUE="true"/>
            </REGISTER>
            <REGISTER NAME="S2MM_SR">
              <PROPERTY NAME="ADDRESS_OFFSET" VALUE="0x34"/>
              <PROPERTY NAME="SIZE" VALUE="32"/>
              <PROPERTY NAME="IS_ENABLED" VALUE="true"/>
            </REGISTER>
            <REGISTER NAME="MM2S_DMACR">
              <PROPERTY NAME="ADDRESS_OFFSET" VALUE="0x0"/>
              <PROPERTY NAME="SIZE" VALUE="32"/>
              <PROPERTY NAME="IS_ENABLED" VALUE="false"/>
            </REGISTER>
            <REGISTER NAME="MM2S_SA">
              <PROPERTY NAME="ADDRESS_OFFSET" VALUE="0x18"/>
              <PROPERTY NAME="SIZE" VALUE="32"/>
              <PROPERTY NAME="IS_ENABLED" VALUE="true"/>
            </REGISTER>
          </REGISTERS>
        </ADDRESSBLOCK>
      </ADDRESSBLOCKS>
    </MODULE>
  </MODULES>
</EDKSYSTEM>
"""


def self_test():
    import tempfile
    import shutil

    tmpdir = tempfile.mkdtemp(prefix='hwh_probe_')
    try:
        hwh = os.path.join(tmpdir, 'demo.hwh')
        with open(hwh, 'w') as handle:
            handle.write(_SAMPLE_HWH)
        db = parse_hwh(hwh)

        assert db['system']['device'] == '7z020', db['system']
        ip = db['ips'][0]
        assert ip['instance'] == 'demo_dma', ip['instance']
        assert ip['base'] == 0x40400000, ip['base']
        assert ip['range'] == 0x10000, ip['range']

        regs = {r['name']: r for r in ip['address_blocks'][0]['registers']}
        assert regs['S2MM_DMACR']['offset'] == 0x30
        assert regs['S2MM_SR']['offset'] == 0x34
        assert regs['MM2S_DMACR']['enabled'] is False
        assert any('C_INCLUDE_MM2S' in c['message'] for c in db['checks']), db['checks']

        drv = emit_driver(db, os.path.join(tmpdir, 'drv'))
        assert len(drv) == 1, drv
        text = open(drv[0]).read()
        assert 'S2MM_DMACR' in text and '0x30' in text
        assert 'IS_ENABLED=false' in text

        # 驱动骨架必须能 import 并正确映射偏移（用假的 mmio）
        sys.path.insert(0, os.path.dirname(drv[0]))
        mod = __import__(os.path.basename(drv[0])[:-3])
        assert mod.REGISTERS['S2MM_SR'] == 0x34

        class _FakeMmio(object):
            def __init__(self):
                self.mem = {}
            def read(self, off):
                return self.mem.get(off, 0)
            def write(self, off, val):
                self.mem[off] = val

        fake = _FakeMmio()
        regs_obj = mod.DemoDmaRegs(fake)
        regs_obj.write('S2MM_DMACR', 0x1)
        assert fake.mem[0x30] == 0x1
        assert regs_obj.read('S2MM_DMACR') == 0x1

        # 对账功能：故意写一个错偏移，应判为未知
        bad_py = os.path.join(tmpdir, 'bad_driver.py')
        with open(bad_py, 'w') as handle:
            handle.write('def f(m):\n    m.write(0x30, 1)\n    m.write(0x999, 1)\n')
        import io
        old = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = audit_offsets(db, [bad_py])
            captured = sys.stdout.getvalue()
        finally:
            sys.stdout = old
        assert code == 1, code
        assert '0x999' in captured, captured
        assert '[ERROR]' in captured, captured
        assert 'S2MM_DMACR' in captured, captured

        print('hwh_probe self-test: OK（解析/基址/寄存器/禁用通道/驱动骨架/偏移对账）')
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ----------------------------------------------------------------------------


def compact_db(db):
    """只保留实例、地址、寄存器与检查结论，去掉端口/连接明细与无关参数。

    随仓库存档的摘要不需要几千行端口连线或 PS7 的数百个 PCW_* 参数；
    需要明细时用不带 --compact 的完整导出。
    """
    keep = ('C_INCLUDE', 'C_NUM_', 'C_SG', 'C_MICRO_DMA', 'C_ENABLE_MULTI_CHANNEL',
            'C_M_AXI_S2MM_DATA_WIDTH', 'C_M_AXI_MM2S_DATA_WIDTH',
            'C_S_AXIS_S2MM_TDATA_WIDTH', 'C_M_AXIS_MM2S_TDATA_WIDTH',
            'C_PRMRY_IS_ACLK_ASYNC', 'C_BASEADDR', 'C_HIGHADDR',
            'SAMPLE_HZ', 'CLK_HZ')
    trimmed = {'system': db.get('system'), 'source': db.get('source'),
               'checks': db.get('checks'), 'ips': []}
    for ip in db.get('ips', []):
        blocks = []
        for block in ip.get('address_blocks', []):
            regs = [{'name': r.get('name'), 'offset': r.get('offset'),
                     'enabled': r.get('enabled')}
                    for r in block.get('registers', [])]
            blocks.append({'name': block.get('name'), 'range': block.get('range'),
                           'registers': regs})
        trimmed['ips'].append({
            'instance': ip.get('instance'),
            'vlnv': ip.get('vlnv'),
            'base': ip.get('base'),
            'range': ip.get('range'),
            'enabled': ip.get('enabled'),
            'parameters': {k: v for k, v in (ip.get('parameters') or {}).items()
                           if k.startswith(keep)},
            'address_blocks': blocks,
            'port_count': len(ip.get('ports', [])),
        })
    trimmed['external_port_count'] = len(db.get('external_ports', []))
    return trimmed


def main(argv=None):
    parser = argparse.ArgumentParser(description='PYNQ .hwh 解析与驱动骨架生成')
    parser.add_argument('hwh', nargs='?', help='Overlay 的 .hwh 文件')
    parser.add_argument('--json', metavar='PATH', help='导出结构化 JSON')
    parser.add_argument('--compact', action='store_true',
                        help='--json 只写摘要（实例/地址/寄存器），省略端口明细')
    parser.add_argument('--emit-driver', metavar='DIR', help='生成 <instance>_regs.py 到该目录')
    parser.add_argument('--audit', nargs='+', metavar='PATH', help='扫描源码中的硬编码寄存器偏移')
    parser.add_argument('--self-test', action='store_true', help='离线自检')
    parser.add_argument('--quiet', action='store_true', help='不打印报表')
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.hwh:
        parser.error('需要 .hwh 文件，或用 --self-test')
    if not os.path.isfile(args.hwh):
        print('找不到文件：%s' % args.hwh, file=sys.stderr)
        return 1

    db = parse_hwh(args.hwh)

    if not args.quiet:
        print_report(db)
    if args.json:
        _ensure_parent(args.json)
        payload = compact_db(db) if args.compact else db
        with open(args.json, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print('\n已写出 %s' % args.json)
    if args.emit_driver:
        written = emit_driver(db, args.emit_driver)
        print('\n生成驱动骨架 %d 个：' % len(written))
        for path in written:
            print('  %s' % path)

    code = 0
    if args.audit:
        print('\n硬编码偏移对账：')
        code = audit_offsets(db, args.audit)
    return code


if __name__ == '__main__':
    sys.exit(main())
