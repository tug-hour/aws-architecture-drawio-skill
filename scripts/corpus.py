"""Deterministic adversarial DAG corpus, independent of hand-positioned examples."""
import argparse,json
from pathlib import Path
from run import run
from schema import load
from quality import operational_quality

def fixtures():
    cases={}
    for count in (4,8,16):
        # Layered branch + shared sink exercises fan-in ports and wire separation.
        nodes=[{'id':'entry','asset_id':'aws4.api_gateway','label':'Amazon API Gateway','description':'処理開始'}]+[{'id':'branch%02d'%i,'asset_id':'aws4.lambda','label':'AWS Lambda','description':'日本語の処理分岐%02d'%i} for i in range(count)]+[{'id':'state','asset_id':'aws4.dynamodb','label':'Amazon DynamoDB','description':'結果保存'}]
        edges=[{'id':'in%02d'%i,'source':'entry','target':'branch%02d'%i} for i in range(count)]+[{'id':'out%02d'%i,'source':'branch%02d'%i,'target':'state'} for i in range(count)]
        cases['fan-'+str(count)]={'architecture':{'schema_version':'1.0','theme':'both','nodes':nodes,'edges':edges},'expected':'passed' if count==4 else 'needs-review-or-split','allowed_rejections':[] if count==4 else ['E_EDGE_TERMINAL']}
    for count in (2,3):
        groups=[{'id':'aws','type':'group.aws-cloud','role':'containment','label':'AWS Cloud'},{'id':'region','type':'group.region','role':'containment','label':'日本語リージョン','parent_id':'aws'},{'id':'vpc','type':'group.vpc','role':'containment','label':'アプリケーション VPC','parent_id':'region'}]
        nodes=[{'id':'entry','asset_id':'aws4.application_load_balancer','label':'Application Load Balancer\n複数AZの入口','group_id':'vpc'}];edges=[]
        for i in range(count):
            az='az'+str(i);sub='sub'+str(i);n='api'+str(i)
            groups.extend([{'id':az,'type':'group.availability-zone','role':'containment','label':'AZ '+str(i),'parent_id':'vpc'},{'id':sub,'type':'group.private-subnet','role':'containment','label':'プライベートサブネット','parent_id':az}])
            nodes.append({'id':n,'asset_id':'aws4.fargate','label':'AWS Fargate','description':'APIサービス'+str(i),'group_id':sub});edges.append({'id':'route'+str(i),'source':'entry','target':n})
        cases['nested-'+str(count)]={'architecture':{'schema_version':'1.0','theme':'both','nodes':nodes,'edges':edges,'groups':groups,'layout':{'mode':'auto','frame_padding_pt':24}},'expected':'passed' if count==2 else 'needs-review-or-split'}
    cases['long-japanese']={'architecture':{'schema_version':'1.0','theme':'both','direction':'left-to-right','nodes':[{'id':'a','asset_id':'aws4.lambda','label':'AWS Lambda','description':'日本語ラベルの幅を確認するための長い処理名称'},{'id':'b','asset_id':'aws4.dynamodb','label':'Amazon DynamoDB','description':'特性別の状態データと処理結果の保存領域'}],'edges':[{'id':'e','source':'a','target':'b','label':'処理結果を保存する'}]},'expected':'passed'}
    cases['dense-dag']={'architecture':{'schema_version':'1.0','theme':'both','nodes':[{'id':'n'+str(i),'asset_id':'aws4.lambda','label':'AWS Lambda','description':'処理'+str(i)} for i in range(8)],'edges':[{'id':'e%d_%d'%(i,j),'source':'n'+str(i),'target':'n'+str(j)} for i in range(8) for j in range(i+1,8)]},'expected':'needs-review-or-split','allowed_rejections':['E_EDGE_TERMINAL']}
    return cases

def outcome_matches(case,gate,code):
    if gate['status']!=case['expected']:return False
    if code==0:return True
    errors={e['code'] for e in gate.get('errors',[])}
    return bool(errors) and errors<=set(case.get('allowed_rejections',[]))

def corpus(output,binary,profile,runtime):
    if output.exists():raise ValueError('Existing corpus output')
    output.mkdir(parents=True);report={'status':'running','cases':{},'viewport':{'width_px':1920,'height_px':1080,'min_text_px':12}}
    for name,c in fixtures().items():
        path=output/(name+'.json');path.write_text(json.dumps(c['architecture'],ensure_ascii=False,indent=2));r,code=run(path,output/name,binary,profile,runtime)
        gate=operational_quality(r,load(output/name/'layout.json'),report['viewport']) if code==0 else {'status':'needs-review-or-split','errors':r.get('errors',[])}
        report['cases'][name]={'expected':c['expected'],'observed':gate,'status':'passed' if outcome_matches(c,gate,code) else 'failed','nodes':len(c['architecture']['nodes']),'edges':len(c['architecture']['edges'])}
        (output/'corpus-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({name:report['cases'][name]},ensure_ascii=False),flush=True)
    report['status']='passed' if all(c['status']=='passed' for c in report['cases'].values()) else 'failed';(output/'corpus-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--drawio',type=Path,default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'));a=p.parse_args();r=corpus(a.output,a.drawio,a.profile,a.runtime);raise SystemExit(0 if r['status']=='passed' else 2)
