"""Rehearse local release update/rollback in a NEW isolated directory only.
Does not install a personal skill, modify app settings, register runners or delete versions.
"""
import argparse,hashlib,json,os,subprocess,zipfile
from pathlib import Path
from check_bundle import audit

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def unpack(archive,checksum,dest,allow_legacy=False):
    r,code=audit(archive,checksum,allow_legacy=allow_legacy)
    if code:raise ValueError('Bundle rejected: '+str(r))
    if dest.exists():raise ValueError('Refuse existing stage')
    dest.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            p=dest/info.filename
            if info.is_dir():p.mkdir(parents=True,exist_ok=True)
            else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(info))
    return dest/'aws-architecture-drawio',r

def rehearsal(old,new,output,runtime,profile,binary,python):
    if output.exists():raise ValueError('Refuse existing output')
    output.mkdir(parents=True)
    report={'status':'running','scope':'Isolated executable release selection; personal installation and app discovery not tested','settings_changed':False,'steps':[]}
    def save():(output/'lifecycle-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    oldroot,oldaudit=unpack(old,old.with_suffix('.zip.sha256'),output/'versions/old',allow_legacy=True)
    newroot,newaudit=unpack(new,new.with_suffix('.zip.sha256'),output/'versions/new')
    oldhash={str(p.relative_to(oldroot)):sha(p) for p in oldroot.rglob('*') if p.is_file()}
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');pointer=output/'active-release.json'
    def select(root,version):pointer.write_text(json.dumps({'path':str(root.resolve()),'version':version},indent=2))
    def invoke(root,input_path,label):
        selected=Path(json.loads(pointer.read_text())['path'])
        if selected!=root.resolve():raise ValueError('Active pointer mismatch')
        dest=output/'renders'/label
        cmd=[str(python),str(selected/'scripts/run.py'),'--input',str(input_path.resolve()),'--output',str(dest.resolve()),'--runtime',str(runtime.resolve()),'--profile',str(profile.resolve()),'--drawio',str(binary.resolve())]
        result=subprocess.run(cmd,cwd=output,env=env,text=True,capture_output=True,timeout=180)
        (output/(label+'.log')).write_text(result.stdout+result.stderr)
        if result.returncode:raise ValueError('Selected release render failed: '+label)
        data=json.loads((dest/'result.json').read_text())
        if not data['production_eligible'] or data['status']!='passed':raise ValueError('Render failed')
        report['steps'].append({'step':label,'version':json.loads(pointer.read_text())['version'],'status':'passed','input_sha256':sha(input_path),'source':str(selected),'themes':['light','dark']});save()
        return dest
    select(oldroot,oldaudit['version']);invoke(oldroot,oldroot/'examples/real-world/web-three-tier.json','baseline-old')
    select(newroot,newaudit['version']);invoke(newroot,oldroot/'examples/real-world/web-three-tier.json','update-compatible-input')
    # Exercise a new-version feature through the staged source, not the working copy.
    cmd=[str(python),str(newroot/'scripts/project.py'),'--input',str((newroot/'examples/projects/modern-web-iot.json').resolve()),'--output',str((output/'renders/new-project').resolve()),'--runtime',str(runtime.resolve()),'--profile',str(profile.resolve()),'--drawio',str(binary.resolve())]
    r=subprocess.run(cmd,cwd=output,env=env,text=True,capture_output=True,timeout=1200);(output/'new-project.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise ValueError('Staged new project failed')
    report['steps'].append({'step':'new-feature-from-bundle','status':'passed','views':len(json.loads((output/'renders/new-project/project-report.json').read_text())['views'])});save()
    # A corrupted download is rejected before replacing the currently selected release.
    corrupt=output/'corrupted.zip';corrupt.write_bytes(new.read_bytes()+b'corruption')
    checksum=output/'corrupted.zip.sha256';checksum.write_text(newaudit['sha256']+'  corrupted.zip\n')
    before=pointer.read_bytes();rejected,code=audit(corrupt,checksum)
    if code==0 or pointer.read_bytes()!=before:raise ValueError('Corrupted update changed selection')
    report['steps'].append({'step':'corrupted-update-rejected','status':'passed','code':rejected['code'],'selection_preserved':True})
    select(oldroot,oldaudit['version']);recovered=invoke(oldroot,oldroot/'examples/real-world/web-three-tier.json','rollback-old')
    base=output/'renders/baseline-old'
    stable={name:sha(base/name)==sha(recovered/name) for name in ('architecture.json','layout.json','light.drawio','dark.drawio','light.svg','dark.svg','light.png','dark.png')}
    if not all(stable.values()):raise ValueError('Rollback output differs')
    if oldhash!={str(p.relative_to(oldroot)):sha(p) for p in oldroot.rglob('*') if p.is_file()}:raise ValueError('Old source changed')
    report.update(status='passed',old_source_preserved=True,rollback_artifacts_identical=stable,bundle_audits={'old':oldaudit,'new':newaudit},active_version=oldaudit['version']);save();return report

if __name__=='__main__':
    import sys
    p=argparse.ArgumentParser();p.add_argument('--old',type=Path,required=True);p.add_argument('--new',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--drawio',type=Path,default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'));a=p.parse_args()
    try:r=rehearsal(a.old.resolve(),a.new.resolve(),a.output.resolve(),a.runtime,a.profile,a.drawio,Path(sys.executable));print(json.dumps(r,ensure_ascii=False));raise SystemExit(0)
    except (OSError,ValueError,subprocess.TimeoutExpired) as e:
        failure={'status':'failed','error':str(e)}
        if a.output.is_dir():(a.output/'lifecycle-report.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2))
        print(json.dumps(failure));raise SystemExit(2)
