"""划分仙八色鸫完整录音。Python 3.8+，仅使用标准库。
1. python split_recordings.py --root . --make-groups metadata/source_groups.csv
2. 人工核对 source_groups.csv 中同源文件的 group_id。
3. python split_recordings.py --root . --groups metadata/source_groups.csv --out metadata/split_v1
不解码、不切片、不移动原文件；文件夹类别不是逐窗口标签。
"""
import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.aiff', '.aif', '.wma', '.opus'}
BUCKETS = ('raw_target', 'raw_negative')
SPLITS = ('train', 'val', 'test')


def scan(root):
    rows = []
    for bucket in BUCKETS:
        directory = root / bucket
        if not directory.is_dir():
            raise ValueError('缺少目录: ' + str(directory))
        files = sorted((p for p in directory.rglob('*')
                        if p.is_file() and p.suffix.lower() in EXTENSIONS),
                       key=lambda p: p.relative_to(root).as_posix())
        if not files:
            raise ValueError('目录中没有支持扩展名的音频: ' + str(directory))
        for p in files:
            if p.stat().st_size == 0:
                raise ValueError('空文件: ' + str(p))
            rows.append({'audio_path': p.relative_to(root).as_posix(), 'bucket': bucket})
    return rows


def write_csv(path, fields, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def suggested_group(relative_path):
    # Only explicit XC IDs are inferred. Crops/converted/re-recorded files must be reviewed.
    ids = re.findall(r'(?i)(?<![a-z0-9])XC[ _-]?(\d+)(?!\d)', Path(relative_path).stem)
    ids = sorted(set(ids))
    if len(ids) == 1:
        return 'xc_' + ids[0]
    return 'file_' + relative_path


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class UnionFind:
    def __init__(self, keys):
        self.parent = {k: k for k in keys}

    def find(self, key):
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        self.parent[max(a, b)] = min(a, b)


def allocate_counts(n, ratios):
    # Small datasets must retain at least one group in each split.
    counts = [max(1, int(math.floor(n * r))) for r in ratios]
    while sum(counts) < n:
        i = max(range(3), key=lambda j: n * ratios[j] - counts[j])
        counts[i] += 1
    while sum(counts) > n:
        choices = [i for i in range(3) if counts[i] > 1]
        if not choices:
            raise ValueError('至少需要3个独立来源组')
        i = max(choices, key=lambda j: counts[j] - n * ratios[j])
        counts[i] -= 1
    return counts


def assign_groups(groups, ratios, seed):
    """Search seeded group permutations; balance counts of independent groups, not clips."""
    keys = sorted(groups)
    totals = {b: sum(b in groups[g] for g in keys) for b in BUCKETS}
    for b, n in totals.items():
        if n < 3:
            raise ValueError(f'{b} 仅有 {n} 个独立来源组，不能同时覆盖 train/val/test。请补充独立录音。')
        if n < 10:
            print(f'提醒: {b} 仅有 {n} 个来源组，验证/测试结果可能波动很大。')
    counts = allocate_counts(len(keys), ratios)
    rng = random.Random(seed)
    best, best_score = None, float('inf')
    # Handles groups containing BOTH buckets, e.g. annotated excerpts from one source.
    for _ in range(3000):
        shuffled = keys.copy()
        rng.shuffle(shuffled)
        assignment = {}
        per_bucket = {b: [0, 0, 0] for b in BUCKETS}
        offset = 0
        for i, split in enumerate(SPLITS):
            for g in shuffled[offset:offset + counts[i]]:
                assignment[g] = split
                for b in groups[g]:
                    per_bucket[b][i] += 1
            offset += counts[i]
        if any(0 in per_bucket[b] for b in BUCKETS):
            continue
        score = sum((per_bucket[b][i] / totals[b] - ratios[i]) ** 2
                    for b in BUCKETS for i in range(3))
        if score < best_score:
            best, best_score = assignment, score
    if best is None:
        raise ValueError('未找到同时覆盖两类来源的划分。请检查来源分组，或补充独立来源；不要拆开同源组。')
    return best


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--root', default='.', help='包含 raw_target/raw_negative 的项目根目录')
    p.add_argument('--make-groups', help='生成待人工核对的来源表，然后退出')
    p.add_argument('--groups', help='人工核对后的来源表；路径相对于项目根目录')
    p.add_argument('--out', default='metadata/split_v1', help='新的输出目录，相对于项目根目录')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--ratios', nargs=3, type=float, default=[.70, .15, .15], metavar=('TRAIN', 'VAL', 'TEST'))
    a = p.parse_args()
    root = Path(a.root).expanduser().resolve()
    rows = scan(root)
    if a.make_groups:
        if a.groups:
            p.error('--make-groups 与 --groups 不可同时使用')
        destination = root / a.make_groups
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_csv(destination, ['audio_path', 'group_id'],
                  [{'audio_path': r['audio_path'], 'group_id': suggested_group(r['audio_path'])} for r in rows])
        print(f'已生成 {len(rows)} 行来源表: {destination}')
        print('请核对 group_id：同源裁剪、转码、增强、重录以及同一连续录音过程必须归为一组。')
        print('此时尚未划分 train/val/test。')
        return
    if not a.groups:
        p.error('先使用 --make-groups 生成来源表，再用 --groups 指定核对后的表')
    if any(not math.isfinite(r) or r <= 0 for r in a.ratios) or abs(sum(a.ratios) - 1) > 1e-6:
        p.error('--ratios 必须为3个正数，且总和为1')
    group_map = {}
    with (root / a.groups).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not {'audio_path', 'group_id'} <= set(reader.fieldnames or []):
            raise ValueError('来源表必须有 audio_path,group_id 两列')
        for r in reader:
            name = r['audio_path'].strip().replace('\\', '/')
            group = r['group_id'].strip()
            if not group or not name or name in group_map:
                raise ValueError('来源表路径重复或存在空值: ' + name)
            group_map[name] = group
    actual = {r['audio_path'] for r in rows}
    if actual != set(group_map):
        raise ValueError('来源表与目录不一致。缺少: ' + str(sorted(actual - set(group_map))[:10])
                         + '；多余: ' + str(sorted(set(group_map) - actual)[:10]))
    uf = UnionFind(group_map.values())
    seen, duplicates, inventory = {}, [], []
    for r in rows:
        name = r['audio_path']
        r.update(source_group_id=group_map[name], sha256=sha256(root / name), size_bytes=(root/name).stat().st_size)
        inventory.append(r.copy())
        if r['sha256'] in seen:
            first = seen[r['sha256']]
            if first['bucket'] != r['bucket']:
                raise ValueError('两类目录存在字节完全相同的文件，需先核实标签: '
                                 + first['audio_path'] + ' / ' + name)
            uf.union(first['source_group_id'], r['source_group_id'])
            duplicates.append({'excluded_path': name, 'kept_path': first['audio_path'], 'sha256': r['sha256']})
        else:
            seen[r['sha256']] = r
    kept = sorted(seen.values(), key=lambda r: r['audio_path'])
    groups = defaultdict(set)
    for r in kept:
        r['group_id'] = uf.find(r['source_group_id'])
        groups[r['group_id']].add(r['bucket'])
    assignment = assign_groups(groups, a.ratios, a.seed)
    manifest = []
    for r in kept:
        manifest.append({**r, 'split': assignment[r['group_id']]})
    summary = {'schema_version': 1, 'seed': a.seed, 'requested_ratios': a.ratios,
               'root_at_creation': str(root), 'input_files': len(rows), 'kept_files': len(kept),
               'excluded_byte_duplicates': len(duplicates), 'unique_source_groups': len(groups),
               'note': 'bucket是录音来源类别，不是每个时间窗口的标签。未检查解码音频、近似重复或时长。',
               'counts': {s: {b: {'files': sum(r['split']==s and r['bucket']==b for r in manifest),
                                   'groups': sum(assignment[g]==s and b in groups[g] for g in groups)}
                              for b in BUCKETS} for s in SPLITS}}
    output = root / a.out
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('输出目录不是空目录，拒绝覆盖已有划分: ' + str(output))
    output.mkdir(parents=True, exist_ok=True)
    marker = output / 'INCOMPLETE.txt'
    marker.write_text('输出未完成，禁止用于训练。', encoding='utf-8')
    fields = ['audio_path', 'bucket', 'source_group_id', 'group_id', 'split', 'sha256', 'size_bytes']
    write_csv(output/'splits.csv', fields, manifest)
    for s in SPLITS:
        write_csv(output/(s+'.csv'), fields, [r for r in manifest if r['split']==s])
    write_csv(output/'duplicates.csv', ['excluded_path','kept_path','sha256'], duplicates)
    write_csv(output/'inventory.csv', ['audio_path','bucket','source_group_id','sha256','size_bytes'], inventory)
    (output/'split_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    marker.unlink()
    print('\n划分完成（数量格式：文件数 / 来源组数）')
    for s in SPLITS:
        print(s, ' | '.join(f"{b}: {summary['counts'][s][b]['files']} / {summary['counts'][s][b]['groups']}" for b in BUCKETS))
    print('字节完全重复而排除的副本:', len(duplicates))
    print('输出目录:', output)
    print('原始录音未移动、未修改。后续只按 train.csv/val.csv/test.csv 读取并切片。')
    print('请冻结这次划分；新增录音不要直接重新运行后替换旧清单。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as exc:
        print('错误:', exc, file=sys.stderr)
        sys.exit(1)
