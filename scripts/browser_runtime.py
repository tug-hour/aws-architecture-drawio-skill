"""Explicit, pre-installed browser runtime. Never installs or downloads anything."""
import hashlib, json, math, struct, subprocess
from pathlib import Path

class RuntimeFailure(Exception):pass

def font_covers(path, chars):
    """Check TrueType cmap formats 4/12 for required code points, not .notdef."""
    data=Path(path).read_bytes()
    def u16(p):return struct.unpack_from('>H',data,p)[0]
    def u32(p):return struct.unpack_from('>I',data,p)[0]
    if data[:4] not in (b'\x00\x01\x00\x00',b'OTTO'):raise RuntimeFailure('Only individual TTF/OTF fonts are supported')
    table=None
    for i in range(u16(4)):
        p=12+16*i
        if data[p:p+4]==b'cmap':table=u32(p+8)
    if table is None:raise RuntimeFailure('Font has no cmap')
    offsets={table+u32(table+4+8*i+4) for i in range(u16(table+2)) if u16(table+4+8*i) in (0,3)}
    def glyph(code):
        for off in offsets:
            fmt=u16(off)
            if fmt==12:
                for i in range(u32(off+12)):
                    p=off+16+12*i;start,end,first=u32(p),u32(p+4),u32(p+8)
                    if start<=code<=end and first+code-start:return True
            elif fmt==4 and code<65536:
                count=u16(off+6)//2;ends=off+14;starts=ends+2*count+2;deltas=starts+2*count;ranges=deltas+2*count
                for i in range(count):
                    if u16(starts+2*i)<=code<=u16(ends+2*i):
                        delta=u16(deltas+2*i);rng=u16(ranges+2*i)
                        value=u16(ranges+2*i+rng+2*(code-u16(starts+2*i))) if rng else code
                        if value and (value+delta)%65536:return True
        return False
    return {c for c in chars if glyph(ord(c))}

def invoke(config_path, request):
    try:
        cfg=json.loads(Path(config_path).read_text())
        if set(cfg)!=set(('node','playwright_module','browser_executable','fonts')) or set(cfg['fonts'])!=set(('latin','japanese')):raise RuntimeFailure('Invalid runtime configuration')
        paths=[cfg['node'],cfg['browser_executable'],*cfg['fonts'].values()]
        if not all(isinstance(p,str) and Path(p).is_absolute() and Path(p).is_file() for p in paths):raise RuntimeFailure('Runtime files are missing or paths are not absolute')
        if not Path(cfg['playwright_module']).is_absolute() or not (Path(cfg['playwright_module'])/'package.json').is_file():raise RuntimeFailure('Playwright module is missing')
        texts=request.get('texts',[]);chars=set(''.join(texts))-{'\n'}
        covered=set()
        for p in cfg['fonts'].values():covered.update(font_covers(p,chars))
        if chars-covered:raise RuntimeFailure('Missing font glyphs: '+','.join('U+%04X'%ord(c) for c in sorted(chars-covered)))
        result=subprocess.run([cfg['node'],str(Path(__file__).with_name('browser_worker.cjs'))],input=json.dumps({'runtime':cfg,**request},ensure_ascii=False),text=True,capture_output=True,timeout=60)
        if result.returncode:raise RuntimeFailure('Browser execution failed: '+result.stderr[-1200:])
        value=json.loads(result.stdout)
        if value.get('error'):raise RuntimeFailure(value['error'])
        if request['operation']=='measure':
            if set(value['metrics'])!=set(texts):raise RuntimeFailure('Incomplete browser measurements')
            for item in value['metrics'].values():
                if not isinstance(item['width'],(int,float)) or not math.isfinite(item['width']) or item['width']<0:raise RuntimeFailure('Invalid browser measurement')
        value['environment']['font_sha256']={k:hashlib.sha256(Path(p).read_bytes()).hexdigest() for k,p in cfg['fonts'].items()}
        value['environment']['browser_sha256']=hashlib.sha256(Path(cfg['browser_executable']).read_bytes()).hexdigest()
        return value
    except RuntimeFailure:raise
    except (OSError,ValueError,KeyError,TypeError,struct.error,subprocess.TimeoutExpired) as e:raise RuntimeFailure(str(e))
