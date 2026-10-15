"""Search native draw.io AWS stencils, without embedded icon files."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def manifest():return json.loads((ROOT/'references/native-catalog.json').read_text())
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('query');p.add_argument('--role');a=p.parse_args();m=manifest()
    rows=[v for v in m['assets'].values() if a.query.casefold() in (v['id']+' '+v['name']).casefold() and (not a.role or v['role']==a.role)]
    print(json.dumps(rows,ensure_ascii=False,indent=2))
