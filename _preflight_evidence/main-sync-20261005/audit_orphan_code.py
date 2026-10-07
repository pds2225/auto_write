import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(r'D:\auto_write')
OUT = ROOT / '_preflight_evidence' / 'main-sync-20261005'
BASES = {
    'dapper-launching-hamming': 'worktree-dapper-launching-hamming',
    'feat+harden-fill-accuracy': '53f66bcfbde6aeda66ba7f4d0943c1d3a94cc860',
    'feat+hwpx-layout-guards': 'worktree-feat+hwpx-layout-guards',
    'marketgate-hscity-fix': 'worktree-marketgate-hscity-fix',
    'typed-herding-marble': 'worktree-typed-herding-marble',
}

def tree(ref):
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '-z', ref])
    result = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        result[name.decode('utf-8')] = metadata.split()[2].decode('ascii')
    return result

def blob_hash(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

main = tree('origin/main')
audit = []
for name, base in BASES.items():
    folder = ROOT / '.claude' / 'worktrees' / name
    baseline = tree(base)
    changes = []
    unchanged = 0
    for file in folder.rglob('*'):
        if not file.is_file() or file.suffix.lower() not in {'.py', '.js', '.ts', '.tsx', '.html', '.css', '.bat', '.ps1'}:
            continue
        rel = file.relative_to(folder).as_posix()
        if any(p in {'.git', '__pycache__', '.venv', 'node_modules', 'data', 'results'} for p in file.relative_to(folder).parts):
            continue
        data = file.read_bytes()
        hashes = {blob_hash(data), blob_hash(data.replace(b'\r\n', b'\n'))}
        if baseline.get(rel) in hashes:
            unchanged += 1
        elif main.get(rel) not in hashes:
            changes.append({'path': rel, 'baseline_blob': baseline.get(rel), 'main_blob': main.get(rel), 'sha256': hashlib.sha256(data).hexdigest()})
    record = {'folder': str(folder), 'base': base, 'unchanged_code_files': unchanged, 'candidate_changes': changes}
    audit.append(record)
    print(json.dumps({'folder': name, 'unchanged': unchanged, 'candidates': [c['path'] for c in changes]}, ensure_ascii=False))
(OUT / 'orphan-code-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
