"""Write a local viewer with recorded review reasons and fit/100% controls. No server."""
import argparse,html,json,re
from pathlib import Path
from version import get_version
from review_status import project_presentation


def make(base):
    report=json.loads((base/'project-report.json').read_text())
    release_version=get_version()
    if report.get('version')!=release_version:raise ValueError('Project release version differs; use its matching skill release')
    presentation=project_presentation(report)
    options=''.join('<option value="'+html.escape(k,quote=True)+'">'+html.escape(v['title'])+'</option>' for k,v in report['views'].items())
    index={}
    for k in report['views']:
        source=base/k/'architecture.json'
        if source.exists():
            for edge in json.loads(source.read_text())['edges']:index.setdefault(edge['id'],[]).append(k)
    body=r'''<!doctype html><html lang="ja"><meta charset="utf-8"><title>AWS構成図 @@VERSION@@</title><style>
body{margin:0;font:16px system-ui;background:#eee;color:#222}header{padding:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}select,button,a{font:inherit}#frame{height:55vh;overflow:auto;background:white}#diagram{display:block}#frame.fit img{width:100%;height:100%;object-fit:contain}#frame.actual img{width:auto;height:auto}#info,#review{padding:10px;font-size:14px}#issues{margin:8px 0;padding-left:24px}details{padding:8px;max-height:80px;overflow:auto}body.dark{background:#202020;color:#eee}body.dark #frame{background:black}[hidden]{display:none!important}#overall{padding:10px;margin:0}#project-errors{white-space:pre-wrap}
</style><header><strong>AWS構成図 @@VERSION@@</strong><select id="view" aria-label="ビュー">@@OPTIONS@@</select><select id="theme" aria-label="テーマ" data-diagram-only><option value="light">ライト</option><option value="dark">ダーク</option></select><button id="fit" data-diagram-only>画面に合わせる</button><button id="actual" data-diagram-only>100%</button><a id="svg" data-diagram-only>SVG</a><a id="drawio" data-diagram-only>編集原本</a></header>
<p id="overall"></p><div id="project-errors"></div><section id="review" aria-live="polite"><strong id="view-status"></strong><ul id="issues"></ul></section>
<div id="frame" class="fit" data-diagram-only><img id="diagram" alt="選択したAWS構成図"></div><div id="info" data-diagram-only></div><details data-diagram-only><summary>この図で省略した接続（他の図を参照）</summary><div id="omitted"></div></details>
<script>
const records=@@MAPPING@@,presentation=@@PRESENTATION@@,edgeIndex=@@EDGEINDEX@@;
const view=document.querySelector('#view'),theme=document.querySelector('#theme'),frame=document.querySelector('#frame');
const issueText=i=>[i.kind,i.code,(i.element_ids||[]).join(', '),i.message].filter(Boolean).join(' ｜ ');
document.querySelector('#overall').textContent='プロジェクト: '+presentation.label;
document.querySelector('#project-errors').textContent=presentation.errors.map(issueText).join('\n');
function show(){
 const k=view.value,t=theme.value,r=records[k],p=presentation.views[k];
 document.body.className=t==='dark'?'dark':'';
 const available=!!p&&(p.state==='passed'||p.state==='review');
 for(const element of document.querySelectorAll('[data-diagram-only]'))element.hidden=!available;
 if(!r){document.querySelector('#view-status').textContent='表示できるビューがありません';return;}
 document.querySelector('#view-status').textContent=k+' ｜ '+p.title+' ｜ '+p.label;
 document.querySelector('#issues').replaceChildren(...p.issues.map(i=>{const li=document.createElement('li');li.textContent=issueText(i);return li}));
 const image=document.querySelector('#diagram');
 if(available)image.src=k+'/'+t+'.png';else image.removeAttribute('src');
 for(const [id,ext] of [['svg','svg'],['drawio','drawio']]){const link=document.querySelector('#'+id);if(available)link.href=k+'/'+t+'.'+ext;else link.removeAttribute('href');}
 document.querySelector('#info').textContent='PPTX部分適合（記号・矢じりは近似、日本語フォントは拡張） ｜ 必須経路: '+(r.flow_ids||[]).join(', ')+' ｜ 検証表示条件: '+r.display.width_px+'×'+r.display.height_px+'px・本文'+r.display.min_text_px+'px以上。小さい画面では100%またはSVGを使って確認。';
 const ids=[...(r.omitted_boundary_edges||[]),...(r.omitted_internal_edges||[])];
 document.querySelector('#omitted').replaceChildren(...ids.map(id=>{const d=document.createElement('div');d.append(document.createTextNode(id+' → '));for(const name of edgeIndex[id]||[]){const b=document.createElement('button');b.textContent=records[name].title;b.onclick=()=>{view.value=name;show()};d.append(b)}return d}));
}
view.onchange=theme.onchange=show;document.querySelector('#fit').onclick=()=>frame.className='fit';document.querySelector('#actual').onclick=()=>frame.className='actual';show();
</script></html>'''
    values={'VERSION':html.escape(release_version),'OPTIONS':options,
            'MAPPING':json.dumps(report['views'],ensure_ascii=False).replace('<','\\u003c'),
            'PRESENTATION':json.dumps(presentation,ensure_ascii=False).replace('<','\\u003c'),
            'EDGEINDEX':json.dumps(index).replace('<','\\u003c')}
    body=re.sub(r'@@(VERSION|OPTIONS|MAPPING|PRESENTATION|EDGEINDEX)@@',lambda m:values[m[1]],body)
    target=base/'image-review.html'
    if target.exists():raise ValueError('Existing viewer')
    target.write_text(body)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);a=p.parse_args();make(a.directory)
