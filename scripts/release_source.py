"""Bind acceptance to the exact code, tests, catalog and example inputs."""
import hashlib

def snapshot(root):
    files=[p for folder in ('scripts','tests','examples') for p in (root/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.cjs','.json') and '__pycache__' not in p.parts]
    files += [root/'SKILL.md']+[root/'references'/name for name in ('native-catalog.json','verified-assets.json','acceptance-contracts.json','service-names.json','version.json')]
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
