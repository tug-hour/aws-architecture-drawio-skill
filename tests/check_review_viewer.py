"""Browser-only display check using copies of existing images; no draw.io export."""
import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from test_review_status import fixture_report, make


def check(runtime, source, output):
    if output.exists():
        raise ValueError('Existing output')
    cfg=json.loads(runtime.read_text())
    output.mkdir(parents=True)
    report=fixture_report()
    report['views']['unknown']=dict(report['views']['ok'],title='判定情報が不足した図')
    report['views']['unknown'].pop('operational_quality')
    report['views']['review']['warnings'][0]['message']+=' </script><script>window.injected=true</script>'
    (output/'project-report.json').write_text(json.dumps(report,ensure_ascii=False))
    for view in ('ok','review'):
        target=output/view; target.mkdir()
        for theme in ('light','dark'):
            for ext in ('png','svg','drawio'):
                shutil.copyfile(source/(theme+'.'+ext),target/(theme+'.'+ext))
        shutil.copyfile(source/'architecture.json',target/'architecture.json')
    make(output)
    script=r'''
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const cfg=JSON.parse(fs.readFileSync(process.argv[1])),out=process.argv[2];
const {chromium}=require(cfg.playwright_module);
(async()=>{
 const browser=await chromium.launch({executablePath:cfg.browser_executable,headless:true,chromiumSandbox:true});
 try {
  const page=await browser.newPage({viewport:{width:1200,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*',route=>route.request().url().startsWith('file:')?route.continue():route.abort());
  await page.goto(pathToFileURL(path.join(out,'image-review.html')).href);
  const assert=(ok,msg)=>{if(!ok)throw new Error(msg)};
  const diagramUI=async visible=>{
   for(const selector of ['#theme','#fit','#actual','#svg','#drawio','#frame','#info','details'])
    assert(await page.locator(selector).isVisible()===visible,selector+' visibility');
   assert(await page.locator('#view').isVisible()&&await page.locator('#view-status').isVisible(),'keep view selection and status');
  };
  assert((await page.locator('#overall').innerText()).includes('生成・検証失敗'),'project failure');
  assert((await page.locator('#view-status').innerText()).includes('機械検査合格'),'passed view');
  await page.selectOption('#view','review');
  assert((await page.locator('#view-status').innerText()).includes('要確認'),'review state');
  const issue=await page.locator('#issues').innerText();
  assert(issue.includes('W_EDGE_FRAME_TRANSIT')&&issue.includes('edge.a, frame.b'),'reason and IDs');
  assert(await page.evaluate(()=>!window.injected),'escaped report content');
  for(const theme of ['light','dark']){
   await page.selectOption('#theme',theme);
   await page.waitForFunction(()=>{const i=document.querySelector('#diagram');return i.complete&&i.naturalWidth>0});
   await page.screenshot({path:path.join(out,theme+'.viewer.png'),fullPage:true});
  }
  for(const [unavailable,label] of [['failed','生成・検証失敗'],['unknown','結果未確認']]){
   for(const restored of ['ok','review']){
    await page.selectOption('#view',unavailable);
    assert((await page.locator('#view-status').innerText()).includes(label),unavailable+' state');
    if(unavailable==='failed')assert((await page.locator('#issues').innerText()).includes('E_RUNTIME_REQUIRED'),'failure reason');
    await diagramUI(false);
    assert(await page.locator('#diagram').getAttribute('src')===null,'clear invalid image');
    for(const id of ['svg','drawio'])assert(await page.locator('#'+id).getAttribute('href')===null,'clear invalid link');
    if(restored==='ok')await page.screenshot({path:path.join(out,unavailable+'.viewer.png'),fullPage:true});
    await page.selectOption('#view',restored);
    await diagramUI(true);
    await page.waitForFunction(()=>{const i=document.querySelector('#diagram');return i.complete&&i.naturalWidth>0});
    for(const ext of ['png','svg','drawio']){
     const value=await page.locator(ext==='png'?'#diagram':'#'+ext).getAttribute(ext==='png'?'src':'href');
     assert(value===restored+'/dark.'+ext,'restore selected artifact');
    }
    await page.click('#actual');assert(await page.locator('#frame').getAttribute('class')==='actual','restore 100% control');
    await page.click('#fit');assert(await page.locator('#frame').getAttribute('class')==='fit','restore fit control');
   }
  }
  assert(errors.length===0,errors.join('\n'));
  console.log(JSON.stringify({status:'passed',screenshots:['light.viewer.png','dark.viewer.png','failed.viewer.png','unknown.viewer.png'],page_errors:errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
'''
    start=time.monotonic()
    result=subprocess.run([cfg['node'],'-e',script,str(runtime.resolve()),str(output.resolve())],capture_output=True,text=True)
    record={'status':'passed' if result.returncode==0 else 'failed','exit_code':result.returncode,
            'seconds':round(time.monotonic()-start,6),'source':str(source.resolve()),'output':str(output.resolve()),
            'scope':'Synthetic display report with copied images; no new diagram validation',
            'stdout':result.stdout,'stderr':result.stderr}
    (output/'browser-check.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(record,ensure_ascii=False))
    return result.returncode


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(check(a.runtime,a.source,a.output))
