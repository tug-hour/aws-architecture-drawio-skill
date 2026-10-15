// Native draw.io SVG measurement/inspection. No network, installation or image assets.
const fs=require('node:fs');
async function main(){
  const a=JSON.parse(fs.readFileSync(0,'utf8')),cfg=a.runtime,{chromium}=require(cfg.playwright_module);
  const browser=await chromium.launch({executablePath:cfg.browser_executable,headless:true,chromiumSandbox:true});
  try{
    const ctx=await browser.newContext({serviceWorkers:'block',deviceScaleFactor:1});await ctx.route('**/*',r=>r.abort());
    const fonts=`@font-face{font-family:Arial;src:url(data:font/ttf;base64,${fs.readFileSync(cfg.fonts.latin).toString('base64')})}@font-face{font-family:"Arial Unicode MS";src:url(data:font/ttf;base64,${fs.readFileSync(cfg.fonts.japanese).toString('base64')})}`;
    const environment={node:process.version,playwright:require(cfg.playwright_module+'/package.json').version,browser:browser.version(),network:'blocked',sandbox:true};
    if(a.operation==='measure'){
      const p=await ctx.newPage(),escape=t=>t.replaceAll('&','&amp;').replaceAll('<','&lt;');
      await p.setContent(`<style>${fonts}</style><svg xmlns="http://www.w3.org/2000/svg">${a.texts.map((t,i)=>`<text id="m${i}" font-family="Arial,Arial Unicode MS" font-size="12">${escape(t)}</text>`).join('')}</svg>`);
      await p.evaluate(async()=>{await document.fonts.load('12px Arial');await document.fonts.load('12px "Arial Unicode MS"');await document.fonts.ready;});
      const metrics=await p.evaluate(ts=>Object.fromEntries(ts.map((t,i)=>{const b=document.getElementById('m'+i).getBBox();return[t,{width:b.width,height:b.height}]})),a.texts);return{metrics,environment};
    }
    if(a.operation!=='inspect-native')throw Error('Unsupported operation');
    const themes={};
    for(const [theme,svg] of Object.entries(a.images)){
      const p=await ctx.newPage();await p.setContent(`<style>body{margin:0}${fonts}</style>${svg}`);
      const dimensions=await p.evaluate(()=>{const s=document.querySelector('svg');return{width:Math.ceil(s.width.baseVal.value),height:Math.ceil(s.height.baseVal.value)}});
      if(dimensions.width>16384||dimensions.height>16384)throw Error('Canvas too large');await p.setViewportSize(dimensions);
      await p.evaluate(async()=>{await document.fonts.load('16px Arial');await document.fonts.load('16px "Arial Unicode MS"');await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));});
      const geometry=await p.evaluate(()=>{
        const cells=[...document.querySelectorAll('g[data-cell-id]')],bbox=e=>{const b=e.getBoundingClientRect();return{x:b.x,y:b.y,w:b.width,h:b.height}},labels=[],icons=[],glyphs=[],headers=[],frames=[],edges=[];
        const textbox=c=>{const boxes=[...c.querySelectorAll('text')].map(bbox);if(!boxes.length)return{x:0,y:0,w:0,h:0};const x=Math.min(...boxes.map(b=>b.x)),y=Math.min(...boxes.map(b=>b.y));return{x,y,w:Math.max(...boxes.map(b=>b.x+b.w))-x,h:Math.max(...boxes.map(b=>b.y+b.h))-y}};
        for(const c of cells){
          const id=c.dataset.cellId;
          if(id.startsWith('label.')||id.startsWith('header.label.')||id.startsWith('glossary.')||id.startsWith('connection.label.'))labels.push({id,text:[...c.querySelectorAll('text')].map(e=>e.textContent).join(''),font_sizes:[...c.querySelectorAll('text')].map(e=>parseFloat(getComputedStyle(e).fontSize)),colors:[...c.querySelectorAll('text')].map(e=>getComputedStyle(e).fill),cell_box:bbox(c),...textbox(c)});
          if(id.startsWith('icon.base.')){const r=c.querySelector('rect');icons.push({id,...bbox(c),fill:r?.getAttribute('fill')})}
          if(id.startsWith('icon.glyph.'))glyphs.push({id,...bbox(c),primitives:c.querySelectorAll('path,rect,circle,ellipse,polygon,polyline').length,fills:[...c.querySelectorAll('[fill]')].map(e=>e.getAttribute('fill'))});
          if(id.startsWith('header.icon.'))headers.push({id,...bbox(c),fills:[...c.querySelectorAll('[fill]')].map(e=>e.getAttribute('fill'))});
          if(id.startsWith('frame.')){const e=c.querySelector('[stroke]:not([stroke="none"])');frames.push({id,...bbox(c),fill:e?.getAttribute('fill'),stroke:e?.getAttribute('stroke'),width:Number(e?.getAttribute('stroke-width')||1),dash:e?.getAttribute('stroke-dasharray')||null})}
          if(id.startsWith('edge.'))edges.push({id,paths:[...c.querySelectorAll('path')].map(e=>({d:e.getAttribute('d'),fill:e.getAttribute('fill'),stroke:e.getAttribute('stroke'),width:Number(e.getAttribute('stroke-width')||1)}))});
        }
        return{labels,icons,glyphs,headers,frames,edges,images:document.querySelectorAll('image').length};
      });
      const cdp=await ctx.newCDPSession(p);await cdp.send('DOM.enable');await cdp.send('CSS.enable');const {root}=await cdp.send('DOM.getDocument');
      const {nodeIds}=await cdp.send('DOM.querySelectorAll',{nodeId:root.nodeId,selector:'g[data-cell-id^="label."] text,g[data-cell-id^="header.label."] text,g[data-cell-id^="glossary."] text,g[data-cell-id^="connection.label."] text'});const actual=[];
      for(const nodeId of nodeIds){const{fonts}=await cdp.send('CSS.getPlatformFontsForNode',{nodeId});actual.push(...fonts)}await cdp.detach();
      if(!actual.length||actual.some(f=>!['Arial','Arial Unicode MS'].includes(f.familyName)))throw Error('Unverified font substitution '+JSON.stringify(actual));
      themes[theme]={...geometry,dimensions,fonts:actual,png_base64:(await p.screenshot({type:'png',animations:'disabled'})).toString('base64')};await p.close();
    }
    return{themes,environment};
  }finally{await browser.close()}
}
main().then(r=>process.stdout.write(JSON.stringify(r))).catch(e=>{process.stderr.write(String(e));process.exitCode=1});
