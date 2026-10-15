"""Read-only diagnostics; never starts an app, installs packages or changes settings."""
import argparse
import json
import plistlib
import sys
from pathlib import Path
from catalog import manifest

def diagnose(binary,runtime):
    issues=[];environment={'python':sys.version.split()[0],'drawio_executable':str(binary),'drawio_version':None}
    if not binary.is_file():issues.append({'code':'E_RUNTIME_UNAVAILABLE','component':'drawio'})
    plist=binary.parent.parent/'Info.plist'
    if plist.is_file():
        try:environment['drawio_version']=plistlib.loads(plist.read_bytes()).get('CFBundleShortVersionString')
        except (OSError,ValueError,plistlib.InvalidFileException):issues.append({'code':'E_DRAWIO_METADATA'})
    if environment['drawio_version']!=manifest()['tested_drawio_version']:issues.append({'code':'E_DRAWIO_UNTESTED','expected':manifest()['tested_drawio_version']})
    if runtime is None:issues.append({'code':'E_RUNTIME_REQUIRED','component':'browser'})
    else:
        try:
            cfg=json.loads(runtime.read_text())
            if not isinstance(cfg,dict) or not isinstance(cfg.get('fonts'),dict):raise ValueError('Invalid object types')
            files=[cfg['node'],cfg['browser_executable'],*cfg['fonts'].values()]
            if set(cfg)!=set(('node','playwright_module','browser_executable','fonts')) or set(cfg['fonts'])!=set(('latin','japanese')):raise ValueError('Invalid keys')
            if not all(isinstance(x,str) and Path(x).is_absolute() and Path(x).is_file() for x in files):raise ValueError('Missing files')
            pkg=Path(cfg['playwright_module'])/'package.json'
            if not pkg.is_file() or not Path(cfg['playwright_module']).is_absolute():raise ValueError('Missing Playwright')
            environment['playwright']=json.loads(pkg.read_text()).get('version')
        except (OSError,ValueError,KeyError,TypeError):issues.append({'code':'E_BROWSER_CONFIG'})
    return {'status':'ready' if not issues else 'unavailable','scope':'Read-only file/version checks; actual rendering still required','environment':environment,'errors':issues,'settings_changed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--drawio',type=Path,default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'));p.add_argument('--runtime',type=Path);a=p.parse_args()
    result=diagnose(a.drawio,a.runtime);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['status']=='ready' else 3)
