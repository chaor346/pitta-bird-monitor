#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_pack.py —— 一条命令验证整个技能包与工程一致性

为什么需要它
    技能包最容易失效的方式是"写完当天能跑，换台机器就报错"。评审和下一个使用者也
    不会逐个脚本手动试。本脚本把工具自检、真实工程数据检查、构建可复现性、命名规范
    四类检查串起来，一次产出可存档的验证日志，失败项直接指明重跑命令。

用法
    python3 verify_pack.py --project ..                  # 在 skill/tools 目录下
    python3 verify_pack.py --project D:\\path\\to\\project --out verification
    python3 verify_pack.py --project .. --tools-only     # 只跑工具自检（无工程数据时）

产出
    <out>/selfcheck.log   完整输出（含每个子命令的 stdout/stderr）
    <out>/report.md       机器可读的结论表

退出码
    0 全部通过或有明确的 SKIP；1 存在 FAIL
"""

from __future__ import print_function

import argparse
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# 竞赛 3.3.5.4 要求：目录名与文件名只用英文、数字、下划线、连字符、点，
# 且除约定俗成的大写文件名（README.md / SKILL.md）外应为小写。
_BAD_NAME_RE = re.compile(r'[^0-9a-zA-Z_\-\.]')
_ALLOW_UPPER = ('README.md', 'SKILL.md', 'LICENSE', 'LICENSE.md')


def _find(project, relative_candidates):
    for rel in relative_candidates:
        path = os.path.join(project, rel)
        if os.path.exists(path):
            return path
    return None


def _glob(project, pattern, subdirs=('', 'build', 'src/fpga')):
    for sub in subdirs:
        folder = os.path.join(project, sub) if sub else project
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(pattern):
                return os.path.join(folder, name)
    # 兜底：别队工程的目录习惯各不相同（overlays/、<board>/、src/…），
    # 在限定深度内递归找一次，避免因为放错目录被误判成 SKIP。
    for root, dirs, files in os.walk(project):
        depth = os.path.relpath(root, project).count(os.sep)
        if depth >= 3:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs
                   if d not in ('.git', '.idea', 'venv', '__pycache__', 'node_modules')]
        for name in sorted(files):
            if name.lower().endswith(pattern):
                return os.path.join(root, name)
    return None


class Checker(object):
    def __init__(self, project, outdir, verbose):
        self.project = os.path.abspath(project)
        self.outdir = os.path.abspath(outdir)
        self.verbose = verbose
        self.rows = []
        self.log = []
        if not os.path.isdir(self.outdir):
            os.makedirs(self.outdir)

    # --- 记录 -------------------------------------------------------------
    def record(self, name, status, detail, command=None, output=''):
        self.rows.append({'name': name, 'status': status, 'detail': detail,
                          'command': command or ''})
        print('[%-4s] %-32s %s' % (status, name, detail))
        self.log.append('===== %s [%s] =====' % (name, status))
        if command:
            self.log.append('$ ' + command)
        self.log.append(detail)
        if output:
            self.log.append(output.rstrip())
        self.log.append('')

    # --- 执行 -------------------------------------------------------------
    def run(self, name, args, required=True):
        command = ' '.join([os.path.basename(sys.executable)] + args)
        started = time.time()
        try:
            proc = subprocess.run([sys.executable] + args, cwd=HERE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = proc.stdout.decode('utf-8', 'replace')
            code = proc.returncode
        except Exception as exc:                      # noqa: BLE001
            self.record(name, 'FAIL', '无法执行：%s' % exc, command)
            return 1
        elapsed = time.time() - started
        status = 'PASS' if code == 0 else ('FAIL' if required else 'WARN')
        detail = '退出码 %d，耗时 %.2fs' % (code, elapsed)
        self.record(name, status, detail, command, output)
        if self.verbose and output:
            print(output)
        return code

    def skip(self, name, detail):
        self.record(name, 'SKIP', detail)

    # --- 具体检查 ---------------------------------------------------------
    def check_tool_selftests(self):
        for tool in ('hwh_probe.py', 'bd_lint.py', 'vivado_report.py', 'golden_compare.py'):
            self.run('%s --self-test' % tool, [os.path.join(HERE, tool), '--self-test'])

    def check_artifacts(self, tools_only):
        hwh = _glob(self.project, '.hwh')
        xdc = _glob(self.project, '.xdc', subdirs=('src/fpga', 'src', ''))
        util = _find(self.project, ['build/utilization.rpt'])
        timing = _find(self.project, ['build/timing.rpt'])
        tcl = _find(self.project, ['build/build.tcl'])

        if tools_only or not hwh:
            self.skip('hwh 解析', '未找到 .hwh' if not tools_only else '--tools-only')
        else:
            self.run('hwh 解析', [os.path.join(HERE, 'hwh_probe.py'), hwh, '--quiet',
                                 '--compact',
                                 '--json', os.path.join(self.outdir, 'hwh_summary.json')])

        if tools_only or not (hwh or tcl):
            self.skip('块图检查', '未找到 .hwh / build.tcl')
        else:
            args = [os.path.join(HERE, 'bd_lint.py')]
            if tcl:
                args += ['--tcl', tcl]
            if hwh:
                args += ['--hwh', hwh]
            if xdc:
                args += ['--xdc', xdc]
            args += ['--json', os.path.join(self.outdir, 'bd_lint.json')]
            self.run('块图检查', args)

        if tools_only or not hwh:
            self.skip('DMA 测试计划', '未找到 .hwh')
        else:
            self.run('DMA 测试计划', [os.path.join(HERE, 'dma_selftest.py'),
                                     '--hwh', hwh, '--dry-run'])

        if tools_only or not (util or timing):
            self.skip('综合/实现指标', '未找到 utilization.rpt / timing.rpt')
        else:
            args = [os.path.join(HERE, 'vivado_report.py')]
            if util:
                args += ['--utilization', util]
            if timing:
                args += ['--timing', timing]
            args += ['--quiet', '--no-fail',
                     '--md', os.path.join(self.outdir, 'vivado_summary.md'),
                     '--json', os.path.join(self.outdir, 'vivado_summary.json')]
            self.run('综合/实现指标', args)

    def check_reproducible(self):
        """构建脚本引用的源文件是否都在，路径是否还成立。"""
        tcl = _find(self.project, ['build/build.tcl'])
        if not tcl:
            self.skip('构建脚本可复现', '未找到 build/build.tcl')
            return
        text = open(tcl, 'r', encoding='utf-8', errors='replace').read()
        base = os.path.dirname(tcl)
        raw = re.findall(r'add_files(?:\s+-fileset\s+\S+)?(?:\s+-norecurse)?\s+\{?([^\s\]\}]+)',
                         text)
        # 带 tcl 变量的路径是构建产物（$output_dir 等），不能按静态文件核对
        skipped = [r for r in raw if '$' in r]
        referenced = [r for r in raw if '$' not in r]
        missing = []
        for rel in referenced:
            path = os.path.normpath(os.path.join(base, rel))
            if not os.path.exists(path):
                missing.append(rel)
        if missing:
            self.record('构建脚本可复现', 'FAIL',
                        '%d 个被引用的源文件不存在：%s' % (len(missing), ', '.join(missing[:5])))
        else:
            self.record('构建脚本可复现', 'PASS',
                        '%d 个 add_files 引用全部存在（另有 %d 个含 tcl 变量的路径未静态核对）'
                        % (len(referenced), len(skipped)))

    def check_naming(self):
        """竞赛要求：仓库内目录名与文件名必须为纯英文（小写字母/数字/下划线/连字符）。"""
        bad = []
        upper = []
        hls_dir = os.path.normpath(os.path.join('src', 'fpga', 'gemm'))
        for root, dirs, files in os.walk(self.project):
            dirs[:] = [d for d in dirs if d not in ('.git', '.idea', '__pycache__')]
            rel_root = os.path.relpath(root, self.project)
            # HLS 自动生成的 IP 文件名含大写且由 Vivado 打包固定，重命名会导致工程找不到，
            # 该目录 README 已说明，故豁免大写检查（仍检查非英文字符）
            in_hls = (rel_root == hls_dir or rel_root.startswith(hls_dir + os.sep))
            for name in list(dirs) + files:
                if name.startswith('.') and name not in ('.gitignore',):
                    continue
                rel = os.path.normpath(os.path.join(rel_root, name))
                if _BAD_NAME_RE.search(name):
                    bad.append(rel)
                elif not in_hls and name not in _ALLOW_UPPER and name != name.lower():
                    upper.append(rel)
        if bad:
            detail = '%d 个名称含非英文/空格/特殊字符，例如：%s' % (len(bad), '; '.join(bad[:5]))
            self.record('命名规范（纯英文）', 'FAIL', detail)
        elif upper:
            detail = '%d 个名称含大写字母（建议改小写），例如：%s' % (
                len(upper), '; '.join(upper[:5]))
            self.record('命名规范（纯英文）', 'WARN', detail)
        else:
            self.record('命名规范（纯英文）', 'PASS', '所有目录与文件名均符合英文命名要求')

    # --- 汇总 -------------------------------------------------------------
    def finish(self):
        log_path = os.path.join(self.outdir, 'selfcheck.log')
        with open(log_path, 'w', encoding='utf-8') as handle:
            handle.write('# 技能包自检日志\n')
            handle.write('# 生成时间：%s\n\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
            handle.write('\n'.join(self.log))

        counts = {'PASS': 0, 'FAIL': 0, 'SKIP': 0, 'WARN': 0}
        for row in self.rows:
            counts[row['status']] = counts.get(row['status'], 0) + 1

        md_path = os.path.join(self.outdir, 'report.md')
        with open(md_path, 'w', encoding='utf-8') as handle:
            handle.write('# 技能包验证报告\n\n')
            handle.write('生成时间：%s　项目根目录：`%s`\n\n'
                         % (time.strftime('%Y-%m-%d %H:%M:%S'), self.project))
            handle.write('| 检查项 | 结果 | 说明 |\n|---|---|---|\n')
            for row in self.rows:
                handle.write('| %s | %s | %s |\n'
                             % (row['name'], row['status'], row['detail'].replace('|', '/')))
            handle.write('\n合计：PASS=%d FAIL=%d SKIP=%d WARN=%d\n'
                         % (counts['PASS'], counts['FAIL'], counts['SKIP'], counts['WARN']))
            handle.write('\n完整输出见同目录 `selfcheck.log`。\n')

        print('\n合计：PASS=%d FAIL=%d SKIP=%d WARN=%d'
              % (counts['PASS'], counts['FAIL'], counts['SKIP'], counts['WARN']))
        print('日志：%s' % log_path)
        print('结论表：%s' % md_path)
        return 1 if counts['FAIL'] else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='技能包整体自检')
    parser.add_argument('--project', default='..', help='工程根目录，默认 skill/..')
    parser.add_argument('--out', default=None, help='输出目录，默认 <project>/skill/verification')
    parser.add_argument('--tools-only', action='store_true', help='只跑工具自检')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args(argv)

    project = os.path.abspath(args.project)
    outdir = args.out or os.path.join(project, 'skill', 'verification')
    if not os.path.isdir(project):
        print('项目目录不存在：%s' % project, file=sys.stderr)
        return 2

    checker = Checker(project, outdir, args.verbose)
    checker.check_tool_selftests()
    checker.check_artifacts(args.tools_only)
    if not args.tools_only:
        checker.check_reproducible()
        checker.check_naming()
    return checker.finish()


if __name__ == '__main__':
    sys.exit(main())
