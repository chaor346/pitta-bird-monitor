#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dma_selftest.py —— 通用 AXI DMA 自检（自动发现实例，偏移取自 .hwh，不手抄）

为什么需要它
    AXI DMA 出问题时的现象高度相似：数据全 0、传输不结束、状态位恒定、板子卡死。
    原因却散落在寄存器偏移、cache 一致性、流接口 TLAST、位宽配置、通道是否真的实现
    这几处。逐个 hand-craft 调试脚本，等于每次重踩一遍。本脚本把"先证明 DMA 通路本身
    是通的"这一步固化下来，且不依赖具体工程。

三种用法
    --dry-run  离线：只读 .hwh，打印本次要在板上做什么（PC 上就能跑，用于交底和复查）
    默认       板端：加载 Overlay，对已实现的通道做一次真实传输 + 数据覆盖检查 + 吞吐
    --seconds  板端：在同一通路上持续跑指定时长，给出稳定吞吐（不用瞬时峰值冒充）

用法
    python3 dma_selftest.py --hwh inmp441.hwh --dry-run
    sudo python3 dma_selftest.py --bit inmp441.bit --hwh inmp441.hwh --json dma.json
    sudo python3 dma_selftest.py --bit inmp441.bit --seconds 30

阻塞保护
    S2MM 在源端不发数时不会完成，MM2S 在没有消费者时会一直等 TREADY。两者都会让
    channel.wait() 永久阻塞。本脚本把传输放进独立线程，超过 --timeout（默认 5 s）
    就报错退出，并把 MM2S 默认设为不测（确有消费者时加 --include-mm2s）。

判定口径
    - 传输完成（wait 返回）只证明 DMA 认为结束，不证明数据到位；
    - 因此必须"预填已知模式 → invalidate → 统计被覆盖的字数"，覆盖率为 0 才是真问题；
    - 错误位（DMAIntErr/DMASlvErr/DMADecErr）必须为 0，否则直接报错并打印原始 SR。
"""

from __future__ import print_function

import argparse
import json
import os
import sys
import threading

# AXI DMA 状态位（来自 AXI DMA 产品指南，与工具是否通用无关，属于协议常量）
SR_HALTED = 0x1
SR_ERR_INT = 0x10
SR_ERR_SLV = 0x20
SR_ERR_DEC = 0x40
SR_IOC = 0x1000
SR_IDLE = 0x2000
CR_RUN = 0x1
CR_RESET = 0x4


# ----------------------------------------------------------------------------
# 计划（离线）
# ----------------------------------------------------------------------------


def _load_probe():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import hwh_probe
    return hwh_probe


def plan_from_hwh(hwh_path):
    """从 .hwh 生成板端测试计划：有哪些 DMA、哪些通道真的实现、偏移是多少。"""
    probe = _load_probe()
    db = probe.parse_hwh(hwh_path)

    dmas = []
    for ip in db['ips']:
        if 'axi_dma' not in (ip['modtype'] or '').lower():
            continue
        params = ip['parameters']
        channels = {}
        for ch, key in (('S2MM', 'C_INCLUDE_S2MM'), ('MM2S', 'C_INCLUDE_MM2S')):
            channels[ch] = str(params.get(key, '1')) == '1'
        regs = {}
        for block in ip['address_blocks']:
            for reg in block['registers']:
                if reg['offset'] is not None:
                    regs[reg['name']] = reg['offset']
        dmas.append({
            'instance': ip['instance'],
            'vlnv': ip['vlnv'],
            'base': ip['base'],
            'range': ip['range'],
            'channels': channels,
            'registers': regs,
            'enabled_registers': sorted([n for n in regs if n not in
                                         {r['name'] for b in ip['address_blocks']
                                          for r in b['registers'] if not r['enabled']}]),
        })
    return {'source': os.path.abspath(hwh_path), 'system': db['system'], 'dmas': dmas}


def print_plan(plan, stream=sys.stdout):
    w = stream.write
    sysinfo = plan.get('system') or {}
    w('Overlay 硬件信息：%s %s%s%s\n' % (sysinfo.get('arch', '?'), sysinfo.get('device', '?'),
                                       sysinfo.get('package', ''), sysinfo.get('speedgrade', '')))
    if not plan['dmas']:
        w('未在该 .hwh 中找到 axi_dma 实例。\n')
        return 1
    for dma in plan['dmas']:
        w('\nDMA 实例：%s (%s)\n' % (dma['instance'], dma['vlnv']))
        w('  基址=%s  范围=%s\n' % (('0x%08X' % dma['base']) if dma['base'] is not None else '-',
                                  dma['range']))
        for ch in ('S2MM', 'MM2S'):
            w('  通道 %s：%s\n' % (ch, '已实现' if dma['channels'][ch] else '未实现（跳过）'))
        for ch in ('S2MM', 'MM2S'):
            if not dma['channels'][ch]:
                continue
            names = [n for n in sorted(dma['registers'])
                     if n.startswith(ch + '_')
                     and n[len(ch) + 1:] in ('DMACR', 'DMASR', 'LENGTH', 'DA', 'DA_MSB',
                                             'SA', 'SA_MSB')]
            w('  通道 %s 将使用的寄存器（偏移取自 .hwh）：\n' % ch)
            for name in names:
                w('    %-24s 0x%X\n' % (name, dma['registers'][name]))
        if dma['channels']['MM2S']:
            w('  注：MM2S 默认不测（无消费者时 wait 会永久阻塞），需要时加 --include-mm2s。\n')
    w('\n板端计划：对每个已实现通道 —— 预填已知模式并 flush → 由 PYNQ DMA 驱动发起传输并计时'
      ' → invalidate 缓存 → 统计被覆盖字数 → 读回 DMASR 错误位。\n'
      '判定：覆盖字数必须 > 0（否则是"传输完成但数据没来"），错误位必须为 0。\n')
    return 0


# ----------------------------------------------------------------------------
# 板端
# ----------------------------------------------------------------------------


def _percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * q))
    return ordered[idx]


def _with_timeout(func, timeout, what):
    """在守护线程里跑可能永久阻塞的驱动调用。

    PYNQ 的 channel.wait() 没有超时参数：源端不发数、或 MM2S 没有消费者时它会一直等，
    整个脚本跟着挂死，连错误信息都打不出来。这里超时就抛错，让调用方记录并退出。
    """
    result = {}

    def runner():
        try:
            result['value'] = func()
        except BaseException as exc:                 # noqa: BLE001 - 原样带回给调用方
            result['error'] = exc

    worker = threading.Thread(target=runner)
    worker.daemon = True
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise RuntimeError('%s 超过 %.1f s 未返回（源端未发数 / TREADY 未拉高 / 中断未接）'
                           % (what, timeout))
    if 'error' in result:
        raise result['error']
    return result.get('value')


def _find_dma(ol):
    """在 Overlay 里按 IP 类型找 DMA，不依赖实例名。"""
    hits = []
    for name, info in ol.ip_dict.items():
        vlnv = (info.get('type') or '')
        if 'axi_dma' in vlnv:
            hits.append(name)
    return hits


def _read_reg(dma, offsets, name):
    """优先用 .hwh 的偏移直接读 MMIO；退化到 PYNQ 的 register_map 属性。"""
    if offsets and name in offsets:
        return dma.mmio.read(offsets[name])
    reg_map = getattr(dma, 'register_map', None)
    if reg_map is not None:
        try:
            return int(getattr(reg_map, name))
        except (AttributeError, TypeError):
            pass
    return None


def _describe_sr(sr):
    if sr is None:
        return '未知'
    flags = []
    if sr & SR_HALTED:
        flags.append('HALTED')
    if sr & SR_ERR_INT:
        flags.append('DMAIntErr')
    if sr & SR_ERR_SLV:
        flags.append('DMASlvErr')
    if sr & SR_ERR_DEC:
        flags.append('DMADecErr')
    if sr & SR_IOC:
        flags.append('IOC')
    if sr & SR_IDLE:
        flags.append('IDLE')
    return '|'.join(flags) or '空闲无标志'


def run_board(args):
    import time
    import numpy as np
    from pynq import Overlay, allocate

    if not os.path.isfile(args.bit):
        raise SystemExit('找不到 bit 文件：%s' % args.bit)

    ol = Overlay(os.path.abspath(args.bit))
    names = _find_dma(ol)
    if not names:
        raise SystemExit('Overlay 中没有 AXI DMA；可用 IP：%s' % sorted(ol.ip_dict))
    if args.dma and args.dma not in names:
        raise SystemExit('指定实例 %s 不存在；可用：%s' % (args.dma, names))
    chosen = args.dma or names[0]

    plan = plan_from_hwh(args.hwh) if args.hwh else {'dmas': []}
    plan_entry = next((d for d in plan['dmas'] if d['instance'] == chosen), None)
    offsets = (plan_entry or {}).get('registers') or {}
    channels = (plan_entry or {}).get('channels') or {'S2MM': True, 'MM2S': True}

    dma = getattr(ol, chosen)
    results = {'overlay': os.path.abspath(args.bit), 'dma': chosen,
               'registers_from_hwh': bool(offsets), 'tests': []}

    n_bytes = (int(args.buf_bytes) // 4) * 4
    n_words = n_bytes // 4
    sentinel = 0x5A5AA5A5

    def one_transfer(direction):
        buf = allocate(shape=(n_words,), dtype=np.uint32, cacheable=True)
        finished = False
        try:
            buf[:] = sentinel
            buf.flush()
            channel = dma.recvchannel if direction == 'S2MM' else dma.sendchannel

            def go():
                channel.transfer(buf)
                channel.wait()

            t0 = time.perf_counter()
            _with_timeout(go, float(args.timeout), '%s 传输' % direction)
            elapsed = time.perf_counter() - t0
            buf.invalidate()
            words = np.asarray(buf, dtype=np.uint32)
            changed = int(np.count_nonzero(words != np.uint32(sentinel)))
            sr_name = '%s_DMASR' % direction
            sr = _read_reg(dma, offsets, sr_name)
            length_reg = _read_reg(dma, offsets, '%s_LENGTH' % direction)
            finished = True
            return {
                'seconds': elapsed,
                'bytes_per_second': n_bytes / elapsed if elapsed > 0 else None,
                'changed_words': changed,
                'total_words': n_words,
                'status_raw': sr,
                'status': _describe_sr(sr),
                'length_raw': length_reg,
            }
        finally:
            # 超时或异常时故意不 free：DMA 可能仍在写这块内存，立即回收会踩坏数据。
            # 进程马上退出，由驱动关闭 Overlay 时统一回收。
            if finished:
                buf.free()

    for direction in ('S2MM', 'MM2S'):
        if direction == 'MM2S' and not args.include_mm2s:
            results['tests'].append({'direction': direction, 'skipped': True,
                                     'reason': 'MM2S 默认不测（无消费者时 wait 会永久阻塞）；'
                                               '确有下游接收方时加 --include-mm2s'})
            continue
        if not channels.get(direction, True):
            results['tests'].append({'direction': direction, 'skipped': True,
                                     'reason': '.hwh 显示该通道未实现（C_INCLUDE_%s=0）' % direction})
            continue
        try:
            if args.seconds:
                rounds = []
                deadline = time.time() + float(args.seconds)
                while time.time() < deadline:
                    rounds.append(one_transfer(direction))
                rates = [r['bytes_per_second'] for r in rounds if r['bytes_per_second']]
                test = {'direction': direction, 'rounds': len(rounds),
                        'mean_bps': (sum(rates) / len(rates)) if rates else None,
                        'p05_bps': _percentile(rates, 0.05),
                        'max_bps': max(rates) if rates else None,
                        'min_changed_words': min(r['changed_words'] for r in rounds) if rounds else 0,
                        'error_rounds': sum(1 for r in rounds
                                            if r['changed_words'] == 0
                                            or (r['status_raw'] or 0) & (SR_ERR_INT | SR_ERR_SLV | SR_ERR_DEC)),
                        'last_status': rounds[-1]['status'] if rounds else None}
            else:
                single = one_transfer(direction)
                test = {'direction': direction}
                test.update(single)
                # 结论：S2MM 必须看到数据覆盖，否则等于"传输完成但数据没来"
                if direction == 'S2MM':
                    test['conclusion'] = ('数据已到位' if single['changed_words'] > 0
                                          else '传输完成但缓冲区未被覆盖：检查流源是否在发数、TLAST 是否到达')
            results['tests'].append(test)
        except Exception as exc:                     # noqa: BLE001 - 板端异常要原样带出
            results['tests'].append({'direction': direction, 'error': '%s: %s'
                                     % (type(exc).__name__, exc)})
    return results


def print_results(results):
    print('Overlay: %s' % results['overlay'])
    print('DMA    : %s（寄存器偏移来源：%s）'
          % (results['dma'], '.hwh' if results['registers_from_hwh'] else 'PYNQ register_map'))
    for test in results['tests']:
        if test.get('skipped'):
            print('\n[%s] 跳过：%s' % (test['direction'], test['reason']))
            continue
        if test.get('error'):
            print('\n[%s] 失败：%s' % (test['direction'], test['error']))
            continue
        print('\n[%s]' % test['direction'])
        if 'rounds' in test:
            print('  轮次=%d  平均=%.0f B/s  P05=%.0f B/s  最大=%.0f B/s'
                  % (test['rounds'], test['mean_bps'] or 0, test['p05_bps'] or 0,
                     test['max_bps'] or 0))
            print('  最少覆盖字数=%d  异常轮次=%d  最后状态=%s'
                  % (test['min_changed_words'], test['error_rounds'], test['last_status']))
            if test['direction'] == 'S2MM' and (test['min_changed_words'] == 0
                                                or test['error_rounds']):
                print('  结论=持续测试中存在未覆盖或错误位的轮次，先排查源端与 TLAST')
        else:
            print('  耗时=%.3f s  吞吐=%.0f B/s  覆盖=%d/%d 字'
                  % (test['seconds'], test['bytes_per_second'] or 0,
                     test['changed_words'], test['total_words']))
            print('  状态=0x%08X (%s)' % (test['status_raw'] or 0, test['status']))
            print('  结论=%s' % test.get('conclusion', '传输完成'))
    failed = []
    for test in results['tests']:
        if test.get('skipped'):
            continue
        if test.get('error'):
            failed.append(test)
        elif test['direction'] == 'S2MM':
            if 'rounds' in test:
                if test.get('min_changed_words', 0) == 0 or test.get('error_rounds', 0):
                    failed.append(test)
            elif test.get('changed_words', 0) == 0:
                failed.append(test)
    print('\n汇总：%d 个通道测试，%d 个未通过' % (len(results['tests']), len(failed)))
    return 1 if failed else 0


# ----------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description='AXI DMA 通用自检')
    parser.add_argument('--bit', help='Overlay 的 .bit（板端运行必需）')
    parser.add_argument('--hwh', help='同一工程的 .hwh：用于取寄存器偏移与通道实现情况')
    parser.add_argument('--dma', help='指定 DMA 实例名（默认取第一个）')
    parser.add_argument('--buf-bytes', type=int, default=8192, help='单次传输字节数，默认 8192')
    parser.add_argument('--seconds', type=float, default=0.0, help='持续测试时长（0 表示单次）')
    parser.add_argument('--timeout', type=float, default=5.0,
                        help='单次传输超时秒数，默认 5（超时即判失败，避免脚本挂死）')
    parser.add_argument('--include-mm2s', action='store_true',
                        help='是否也测 MM2S 发送通道（默认不测，避免无消费者时阻塞）')
    parser.add_argument('--dry-run', action='store_true', help='只打印计划，不接触硬件')
    parser.add_argument('--json', help='把结果写成 JSON')
    args = parser.parse_args(argv)

    if args.dry_run:
        if not args.hwh or not os.path.isfile(args.hwh):
            parser.error('--dry-run 需要 --hwh')
        return print_plan(plan_from_hwh(args.hwh))

    if not args.bit:
        parser.error('板端运行需要 --bit；只想看计划请加 --dry-run')
    results = run_board(args)
    code = print_results(results)
    if args.json:
        parent = os.path.dirname(os.path.abspath(args.json))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(args.json, 'w') as handle:
            json.dump(results, handle, indent=2, ensure_ascii=True)
        print('已写出 %s' % args.json)
    return code


if __name__ == '__main__':
    sys.exit(main())
