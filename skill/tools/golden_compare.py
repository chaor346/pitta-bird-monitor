#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""golden_compare.py —— 通用黄金参考比对（CSV / NPY / 纯文本数值）

为什么需要它
    "功能正确"如果只靠肉眼看波形或听声音，就只是印象。硬件加速最容易被悄悄改坏的
    地方是数值：定点化、截位、饱和、符号扩展、通道顺序。本脚本把"当前输出 vs 参考输出"
    变成一条可重复、可写进报告的命令，容差、首个超差位置、最大误差都能落到文件里。

支持的输入
    .csv / .tsv  逐单元格比对；首行若是非数字则按列名对齐，数字列走容差，文本列走精确
    .npy / .npz  ndarray 逐元素比对（形状必须一致）
    其他          抽取全部数值（空白/逗号分隔皆可）按顺序比对

用法
    python3 golden_compare.py --golden ref.csv --actual hw.csv --atol 1e-6
    python3 golden_compare.py --golden ref.npy --actual hw.npy --rtol 1e-4 --json cmp.json
    python3 golden_compare.py --golden ref.txt --actual hw.txt --show 5
    python3 golden_compare.py --self-test

判定
    超差条件：|actual - golden| > atol + rtol * |golden|
    退出码：0 全部在容差内；1 有超差或形状不一致；2 参数错误
"""

from __future__ import print_function

import argparse
import csv
import json
import os
import re
import sys

FLOAT_RE = re.compile(r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?')


def _is_number(text):
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


def _fmt(value):
    if value is None:
        return '-'
    return '%.6g' % value


# ----------------------------------------------------------------------------
# 读取
# ----------------------------------------------------------------------------


def load_csv(path, delimiter=None):
    """返回 (header, rows)。header 为 None 表示没有表头。"""
    if delimiter is None:
        delimiter = '\t' if path.lower().endswith('.tsv') else ','
    with open(path, 'r', encoding='utf-8', errors='replace', newline='') as handle:
        rows = [row for row in csv.reader(handle, delimiter=delimiter) if any(c.strip() for c in row)]
    if not rows:
        raise SystemExit('空文件：%s' % path)
    first = rows[0]
    header = None if all(_is_number(c) or not c.strip() for c in first) else [c.strip() for c in first]
    body = rows[1:] if header else rows
    widths = {len(row) for row in body}
    if len(widths) > 1:
        raise SystemExit('%s 的列数不一致：%s' % (path, sorted(widths)))
    return header, body


def load_npy(path):
    try:
        import numpy as np
    except ImportError:
        raise SystemExit('需要 numpy 才能读 .npy')
    data = np.load(path)
    if hasattr(data, 'files'):
        key = sorted(data.files)[0]
        data = data[key]
    return np.asarray(data)


def load_text(path):
    text = open(path, 'r', encoding='utf-8', errors='replace').read()
    return [float(t) for t in FLOAT_RE.findall(text)]


def load_any(path):
    low = path.lower()
    if low.endswith(('.npy', '.npz')):
        return 'npy', load_npy(path)
    if low.endswith(('.csv', '.tsv')):
        return 'csv', load_csv(path)
    return 'text', load_text(path)


# ----------------------------------------------------------------------------
# 比对
# ----------------------------------------------------------------------------


def compare_numbers(golden, actual, atol, rtol):
    """逐元素比对两个序列，返回 (超差掩码列表, 最大绝对误差, 最大相对误差)。"""
    bad = []
    max_abs = 0.0
    max_rel = 0.0
    for idx, (ref, got) in enumerate(zip(golden, actual)):
        diff = abs(got - ref)
        limit = atol + rtol * abs(ref)
        if diff > max_abs:
            max_abs = diff
        if ref != 0:
            rel = diff / abs(ref)
            if rel > max_rel:
                max_rel = rel
        if diff > limit:
            bad.append(idx)
    return bad, max_abs, max_rel


def compare(path_golden, path_actual, atol, rtol, show):
    kind_g, golden = load_any(path_golden)
    kind_a, actual = load_any(path_actual)
    if kind_g != kind_a:
        raise SystemExit('两边格式不一致：%s / %s' % (kind_g, kind_a))

    result = {'golden': os.path.abspath(path_golden),
              'actual': os.path.abspath(path_actual),
              'kind': kind_g, 'atol': atol, 'rtol': rtol, 'columns': []}

    if kind_g == 'npy':
        import numpy as np
        if golden.shape != actual.shape:
            raise SystemExit('形状不一致：golden %s vs actual %s' % (golden.shape, actual.shape))
        g = golden.ravel().astype(np.float64)
        a = actual.ravel().astype(np.float64)
        bad, max_abs, max_rel = compare_numbers(g.tolist(), a.tolist(), atol, rtol)
        result['shape'] = list(golden.shape)
        result['total'] = int(g.size)
        result['mismatch'] = len(bad)
        result['max_abs_diff'] = max_abs
        result['max_rel_diff'] = max_rel
        result['first_bad'] = [{'index': int(i),
                                'golden': float(g[i]), 'actual': float(a[i])}
                               for i in bad[:show]]
        return result

    if kind_g == 'csv':
        header_g, rows_g = golden
        header_a, rows_a = actual
        width = len(rows_g[0])
        if len(rows_g) != len(rows_a):
            raise SystemExit('行数不一致：%d vs %d' % (len(rows_g), len(rows_a)))
        names = header_g or ['col%d' % i for i in range(width)]
        result['rows'] = len(rows_g)
        for col in range(width):
            numeric = all(_is_number(r[col]) for r in rows_g + rows_a if col < len(r))
            detail = {'name': names[col] if col < len(names) else 'col%d' % col,
                      'numeric': numeric}
            if numeric:
                g = [float(r[col]) for r in rows_g]
                a = [float(r[col]) for r in rows_a]
                bad, max_abs, max_rel = compare_numbers(g, a, atol, rtol)
                detail.update({'total': len(g), 'mismatch': len(bad),
                               'max_abs_diff': max_abs, 'max_rel_diff': max_rel})
                detail['first_bad'] = [{'row': int(i), 'golden': g[i], 'actual': a[i]}
                                       for i in bad[:show]]
            else:
                bad = [i for i, (rg, ra) in enumerate(zip(rows_g, rows_a))
                       if rg[col].strip() != ra[col].strip()]
                detail.update({'total': len(rows_g), 'mismatch': len(bad),
                               'first_bad': [{'row': int(i), 'golden': rows_g[i][col],
                                              'actual': rows_a[i][col]} for i in bad[:show]]})
            result['columns'].append(detail)
        result['mismatch'] = sum(c['mismatch'] for c in result['columns'])
        result['total'] = sum(c['total'] for c in result['columns'])
        return result

    # text
    if len(golden) != len(actual):
        raise SystemExit('数值个数不一致：%d vs %d' % (len(golden), len(actual)))
    bad, max_abs, max_rel = compare_numbers(golden, actual, atol, rtol)
    result['total'] = len(golden)
    result['mismatch'] = len(bad)
    result['max_abs_diff'] = max_abs
    result['max_rel_diff'] = max_rel
    result['first_bad'] = [{'index': int(i), 'golden': golden[i], 'actual': actual[i]}
                           for i in bad[:show]]
    return result


def print_result(result):
    print('比对 %s vs %s（%s 模式，atol=%g rtol=%g）'
          % (os.path.basename(result['golden']), os.path.basename(result['actual']),
             result['kind'], result['atol'], result['rtol']))
    if result['kind'] == 'npy':
        print('  形状：%s' % (result.get('shape'),))
    if result['kind'] == 'csv':
        print('  行数：%d  列数：%d' % (result['rows'], len(result['columns'])))
    print('  比对单元：%d  超差：%d' % (result['total'], result['mismatch']))
    if result['kind'] != 'csv':
        print('  最大绝对误差：%s  最大相对误差：%s'
              % (_fmt(result.get('max_abs_diff')), _fmt(result.get('max_rel_diff'))))
    for col in result.get('columns') or []:
        tag = '数值' if col['numeric'] else '文本'
        print('  列 %-12s [%s] 超差 %d/%d' % (col['name'], tag, col['mismatch'], col['total']))
        if col['numeric']:
            print('      最大绝对误差 %s  最大相对误差 %s'
                  % (_fmt(col.get('max_abs_diff')), _fmt(col.get('max_rel_diff'))))
    for item in (result.get('first_bad') or []):
        where = item.get('index', item.get('row'))
        print('  首个超差点 %s：golden=%s actual=%s'
              % (where, _fmt(item['golden']) if isinstance(item['golden'], float)
                 else item['golden'],
                 _fmt(item['actual']) if isinstance(item['actual'], float) else item['actual']))
    if result['mismatch'] == 0:
        print('  结论：在给定容差内一致')
    else:
        print('  结论：存在超差，功能/数值不等价')
    return 0 if result['mismatch'] == 0 else 1


# ----------------------------------------------------------------------------
# 自检
# ----------------------------------------------------------------------------

def self_test():
    import tempfile
    import shutil

    tmp = tempfile.mkdtemp(prefix='golden_')
    try:
        def write(name, text):
            path = os.path.join(tmp, name)
            with open(path, 'w', encoding='utf-8', newline='') as handle:
                handle.write(text)
            return path

        # CSV：一列数值在容差内，一列有明显偏差，一列文本
        ref = write('ref.csv', 'id,value,label\n0,1.000000,a\n1,2.000000,b\n2,3.000000,c\n')
        ok = write('ok.csv', 'id,value,label\n0,1.000000,a\n1,2.000000,b\n2,3.000001,c\n')
        bad = write('bad.csv', 'id,value,label\n0,1.000000,a\n1,2.000000,b\n2,3.100000,c\n')
        label_bad = write('label.csv', 'id,value,label\n0,1.000000,a\n1,2.000000,X\n2,3.000000,c\n')

        result = compare(ref, ok, atol=1e-5, rtol=0.0, show=3)
        assert result['mismatch'] == 0, result
        assert print_result(result) == 0

        result = compare(ref, bad, atol=1e-5, rtol=0.0, show=3)
        assert result['mismatch'] == 1, result
        assert print_result(result) == 1
        value_col = [c for c in result['columns'] if c['name'] == 'value'][0]
        assert value_col['mismatch'] == 1 and value_col['first_bad'][0]['row'] == 2, value_col

        result = compare(ref, label_bad, atol=1e-5, rtol=0.0, show=3)
        assert result['mismatch'] == 1, result

        # 文本：顺序数值比对
        t_ref = write('ref.txt', '1 2 3\n4 5\n')
        t_ok = write('ok.txt', '1,2,3,4,5.0000001')
        t_bad = write('bad.txt', '1,2,3,4,6')
        assert compare(t_ref, t_ok, 1e-5, 0.0, 1)['mismatch'] == 0
        assert compare(t_ref, t_bad, 1e-5, 0.0, 1)['mismatch'] == 1

        # npy：形状一致/不一致
        try:
            import numpy as np
            np.save(os.path.join(tmp, 'ref.npy'), np.array([[1.0, 2.0], [3.0, 4.0]]))
            np.save(os.path.join(tmp, 'ok.npy'), np.array([[1.0, 2.0], [3.0, 4.000001]]))
            np.save(os.path.join(tmp, 'shape.npy'), np.array([1.0, 2.0, 3.0, 4.0]))
            assert compare(os.path.join(tmp, 'ref.npy'), os.path.join(tmp, 'ok.npy'),
                           1e-5, 0.0, 3)['mismatch'] == 0
            try:
                compare(os.path.join(tmp, 'ref.npy'), os.path.join(tmp, 'shape.npy'), 1e-5, 0.0, 3)
                raise AssertionError('形状不一致应报错')
            except SystemExit:
                pass
            npy_checked = True
        except ImportError:
            npy_checked = False

        print('golden_compare self-test: OK（CSV 容差/文本列精确/NPY 形状%s）'
              % ('/数值' if npy_checked else '（未装 numpy，跳过）'))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description='黄金参考比对')
    parser.add_argument('--golden', help='参考输出')
    parser.add_argument('--actual', help='当前输出')
    parser.add_argument('--atol', type=float, default=0.0, help='绝对容差，默认 0')
    parser.add_argument('--rtol', type=float, default=0.0, help='相对容差，默认 0')
    parser.add_argument('--show', type=int, default=3, help='每列打印几个超差点')
    parser.add_argument('--json', help='比对结果写成 JSON')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.golden or not args.actual:
        parser.error('需要 --golden 与 --actual')
    for path in (args.golden, args.actual):
        if not os.path.isfile(path):
            print('找不到文件：%s' % path, file=sys.stderr)
            return 2

    result = compare(args.golden, args.actual, args.atol, args.rtol, args.show)
    code = print_result(result)
    if args.json:
        parent = os.path.dirname(os.path.abspath(args.json))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(args.json, 'w', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
        print('已写出 %s' % args.json)
    return code


if __name__ == '__main__':
    sys.exit(main())
