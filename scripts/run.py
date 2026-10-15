"""Build and freshly verify a diagram; persist success and failure reports."""
import argparse
import json
from pathlib import Path
from build_drawio import build
from verify_native import verify

def run(path,output,binary,profile,runtime):
    if output.exists():return {'status':'failed','errors':[{'code':'E_OUTPUT_EXISTS','message':'Output already exists'}]},2
    result,code=build(path,output,binary,profile,runtime)
    if code==0:
        result,code=verify(output,output/'qa',runtime,binary,profile,path)
    result=dict(result,exit_code=code)
    result.setdefault('production_eligible',False)
    result.setdefault('warnings',[])
    if not output.exists():output.mkdir(parents=True,exist_ok=False)
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result,code

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--drawio',type=Path,default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'))
    parser.add_argument('--profile',type=Path,required=True);parser.add_argument('--runtime',type=Path,required=True)
    args=parser.parse_args();result,code=run(args.input,args.output,args.drawio,args.profile,args.runtime)
    print(json.dumps({k:v for k,v in result.items() if k!='themes'},ensure_ascii=False));raise SystemExit(code)
