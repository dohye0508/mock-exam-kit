#!/usr/bin/env node
'use strict';
/* Detect disposable magenta markers, replace their white label zones, and add
   editable SVG text over a self-contained generated raster illustration. */
const fs = require('node:fs');
const path = require('node:path');
function getSharp() {
  const candidates = [process.env.SCIENCE_SHARP_PATH, 'sharp',
    path.join(process.env.HOME || '', '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp')].filter(Boolean);
  for (const candidate of candidates) { try { return require(candidate); } catch (e) { if (e.code !== 'MODULE_NOT_FOUND') throw e; } }
  throw new Error('sharp is required. Set SCIENCE_SHARP_PATH to its absolute package directory or install sharp in the Node environment.');
}
const sharp = getSharp();
function fail(message) { throw new Error(message); }
function finite(value, label, min, max) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) fail(`${label}: expected a number between ${min} and ${max}`);
  return value;
}
function escapeXML(value) { return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&apos;'); }
function core(r,g,b,a) { return a > 200 && r >= 160 && b >= 160 && g <= 160 && r-g >= 65 && b-g >= 65; }
function loose(r,g,b,a) {
  // Image-generation antialiasing may leave a very pale magenta fringe, e.g.
  // [252,234,255]. Admit only bright magenta-tinted fringe, never gray/black.
  const brightFringe = r >= 235 && b >= 235 && g >= 210 && r-g >= 8 && b-g >= 8;
  return a > 0 && ((r >= 130 && b >= 130 && r-g >= 20 && b-g >= 20) || brightFringe);
}
function white(r,g,b,a) { return a === 0 || (r >= 235 && g >= 235 && b >= 235); }
function gray(r,g,b,a) {
  // Generated grayscale art can contain faint chromatic ringing around markers.
  // Keep the tolerance small; brightness and smooth-background checks also apply.
  return a >= 240 && Math.min(r,g,b) >= 160 && Math.max(r,g,b)-Math.min(r,g,b) <= 20;
}
function grayMarker(r,g,b,a) {
  // A magenta edge blended against gray may be less saturated than its core.
  return a > 0 && r >= 130 && b >= 130 && Math.abs(r-b) <= 35 && r-g >= 8 && b-g >= 8;
}
function parseLabels(doc) {
  if (!doc || doc.version !== 1 || !Array.isArray(doc.labels) || !doc.labels.length || doc.labels.length > 50) fail('labels JSON requires version:1 and 1–50 labels');
  if (Object.hasOwn(doc, 'overlays')) fail('overlays are not allowed: request an image-generation marker for every text label first');
  finite(doc.width, 'width', 100, 20000);
  finite(doc.height, 'height', 100, 20000);
  const ids = new Set();
  return doc.labels.map((item, i) => {
    if (!item || typeof item !== 'object') fail(`labels[${i}]: expected an object`);
    const id = item.id;
    if (typeof id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(id) || ids.has(id)) fail(`labels[${i}].id: expected a unique ASCII identifier`);
    ids.add(id);
    if (typeof item.text !== 'string' || !item.text.trim() || item.text.length > 120 || /[\u0000-\u001f\ud800-\udfff\ufffe\uffff]/.test(item.text)) fail(`${id}.text: expected nonempty single-line text without control characters (max 120 chars)`);
    const anchor=item.anchor ?? 'middle', cleanup=item.cleanup ?? 'white';
    if (!['start','middle','end'].includes(anchor)) fail(`${id}.anchor: expected start, middle or end`);
    if (!['white','local_gray'].includes(cleanup)) fail(`${id}.cleanup: expected white or local_gray`);
    return {id, x: finite(item.x, `${id}.x`, 0, 1), y: finite(item.y, `${id}.y`, 0, 1), text:item.text,
      font_size: finite(item.font_size, `${id}.font_size`, 4, 512), search_radius: finite(item.search_radius ?? 0.08, `${id}.search_radius`, 0.001, 0.3),
      anchor, cleanup, halo:finite(item.halo ?? 0,`${id}.halo`,0,4)};
  });
}
function localGrayBackground(data,w,box,id) {
  const at=(x,y)=>{const k=(y*w+x)*4;return [data[k],data[k+1],data[k+2],data[k+3]];};
  const corner=(x,y,dx,dy)=>{
    let total=0,n=0;
    for(const [xx,yy] of [[x,y],[x+dx,y],[x,y+dy]]) {
      const pixel=at(xx,yy);
      if(!gray(...pixel)) fail(`${id}: local_gray border is not bright neutral background; review marker placement`);
      total+=(pixel[0]+pixel[1]+pixel[2])/3;n++;
    }
    return total/n;
  };
  const corners=[corner(box.x,box.y,1,1),corner(box.right,box.y,-1,1),corner(box.x,box.bottom,1,-1),corner(box.right,box.bottom,-1,-1)];
  if(Math.max(...corners)-Math.min(...corners)>45) fail(`${id}: local_gray background changes too much; review marker placement`);
  const predict=(x,y)=>{
    const tx=(x-box.x)/(box.right-box.x),ty=(y-box.y)/(box.bottom-box.y);
    return Math.round((corners[0]*(1-tx)+corners[1]*tx)*(1-ty)+(corners[2]*(1-tx)+corners[3]*tx)*ty);
  };
  for(let y=box.y;y<=box.bottom;y++)for(let x=box.x;x<=box.right;x++) {
    const pixel=at(x,y), edge=x===box.x||x===box.right||y===box.y||y===box.bottom;
    if(!edge && grayMarker(...pixel)) continue;
    const mean=(pixel[0]+pixel[1]+pixel[2])/3;
    if(!gray(...pixel)||Math.abs(mean-predict(x,y))>16) fail(`${id}: local_gray cleanup touches a drawing line or non-smooth background at (${x},${y}); request a safer marker position`);
  }
  return {predict,corners:corners.map(x=>+x.toFixed(2))};
}
function checkTextBounds(item, center, size, w, h, anchor='middle') {
  // Font-independent conservative estimate; final font/layout still needs visual review.
  const estimatedWidth = [...item.text].reduce((sum, c) => sum + (c.codePointAt(0) > 0x2ff ? 1.1 : 0.75), 0) * size;
  const left = center[0] - (anchor === 'end' ? estimatedWidth : anchor === 'middle' ? estimatedWidth/2 : 0);
  if (left < 0 || left + estimatedWidth > w) fail(`${item.id}: text may clip at left/right edge; reduce font size or move its anchor`);
  if (center[1] < size*0.65 || center[1] + size*0.65 > h) fail(`${item.id}: text is too close to top/bottom edge`);
}
function detect(data, w, h) {
  const n = w*h, seen = new Uint8Array(n), candidates = [];
  // 8-connectivity preserves antialiased diagonal marker edges.
  for (let p=0; p<n; p++) {
    if (seen[p]) continue;
    const k=p*4;
    if (!core(data[k],data[k+1],data[k+2],data[k+3])) continue;
    const queue=[p]; seen[p]=1;
    let area=0, minX=w, minY=h, maxX=0, maxY=0;
    for(let head=0;head<queue.length;head++) {
      const q=queue[head], x=q%w, y=Math.floor(q/w); area++;
      minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
      for(let dy=-1;dy<=1;dy++) for(let dx=-1;dx<=1;dx++) {
        const xx=x+dx, yy=y+dy;
        if(xx<0||xx>=w||yy<0||yy>=h) continue;
        const t=yy*w+xx,j=t*4;
        if(!seen[t]&&core(data[j],data[j+1],data[j+2],data[j+3])) {seen[t]=1;queue.push(t);}
      }
    }
    if(area>=4) candidates.push({area,minX,minY,maxX,maxY,x:(minX+maxX)/2,y:(minY+maxY)/2});
  }
  return candidates;
}
async function compose(input, labelPath, prefix) {
  const doc=JSON.parse(fs.readFileSync(labelPath,'utf8')), labels=parseLabels(doc);
  const outputs={clean:prefix+'.clean.png',svg:prefix+'.final.svg',png:prefix+'.final.png',report:prefix+'.detected.json'};
  for(const file of Object.values(outputs)) if(fs.existsSync(file)) fail(`Refusing to overwrite ${file}; use a new output prefix`);
  const result=await sharp(input,{limitInputPixels:80e6}).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  const {width:w,height:h}=result.info;
  if(w<100||h<100) fail('Input image is too small');
  if(Math.abs(w/h-doc.width/doc.height)/(doc.width/doc.height)>0.03) fail('Generated image aspect ratio differs from sketch by more than 3%; review before composing');
  const data=result.data, candidates=detect(data,w,h), matches=[], used=new Set();
  for(const label of labels) {
    const nearby=candidates.map((c,i)=>({c,i,d:Math.hypot(c.x/w-label.x,c.y/h-label.y)})).filter(x=>x.d<=label.search_radius);
    if(nearby.length!==1) fail(`${label.id}: expected exactly one marker within search_radius, found ${nearby.length}`);
    const {c,i}=nearby[0];
    if(used.has(i)) fail(`${label.id}: marker already assigned to another label`);
    const cw=c.maxX-c.minX+1,ch=c.maxY-c.minY+1;
    if(cw/ch<0.4||cw/ch>2.5||cw>0.07*w||ch>0.07*h) fail(`${label.id}: candidate is not a small compact marker`);
    used.add(i);
    const pad=Math.max(3,Math.ceil(w/doc.width*3));
    const box={x:Math.max(0,c.minX-pad),y:Math.max(0,c.minY-pad),right:Math.min(w-1,c.maxX+pad),bottom:Math.min(h-1,c.maxY+pad)};
    let background;
    if(label.cleanup==='local_gray') background=localGrayBackground(data,w,box,label.id);
    else for(let y=box.y;y<=box.bottom;y++) for(let x=box.x;x<=box.right;x++) {
        const k=(y*w+x)*4;
        if(!white(data[k],data[k+1],data[k+2],data[k+3])&&!loose(data[k],data[k+1],data[k+2],data[k+3])) fail(`${label.id}: marker cleanup region touches nonwhite drawing pixels at (${x},${y}); review the generated image`);
      }
    matches.push({...label,center_px:[c.x,c.y],marker_bbox_px:[c.minX,c.minY,c.maxX+1,c.maxY+1],cleanup_bbox_px:[box.x,box.y,box.right+1,box.bottom+1],area:c.area,background});
  }
  if(used.size!==candidates.length) fail(`Found ${candidates.length-used.size} unexpected magenta marker(s); review the generated image`);
  // Only verified marker neighborhoods may change; other illustration pixels stay intact.
  const cleaned=Buffer.from(data);
  for(const m of matches) {
    const [x0,y0,x1,y1]=m.cleanup_bbox_px;
    for(let y=y0;y<y1;y++) for(let x=x0;x<x1;x++) {
      const k=(y*w+x)*4;
      if(m.cleanup==='white') cleaned.fill(255,k,k+4);
      else {
        const value=m.background.predict(x,y);cleaned[k]=cleaned[k+1]=cleaned[k+2]=value;cleaned[k+3]=255;
      }
    }
  }
  for(let k=0;k<cleaned.length;k+=4) if(core(cleaned[k],cleaned[k+1],cleaned[k+2],cleaned[k+3])) fail('Residual magenta found outside verified marker regions; review before exporting');
  const cleanPNG=await sharp(cleaned,{raw:{width:w,height:h,channels:4}}).png().toBuffer();
  const font="'Noto Sans CJK KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif";
  const texts=matches.map(m=>`  <text data-label-id="${escapeXML(m.id)}" x="${m.center_px[0]}" y="${m.center_px[1]}" font-size="${+(m.font_size*w/doc.width).toFixed(3)}" text-anchor="${m.anchor}" dominant-baseline="central"${m.halo > 0 ? ` stroke="white" stroke-width="${+(m.halo*w/doc.width).toFixed(3)}" stroke-linejoin="round" paint-order="stroke fill"` : ''}>${escapeXML(m.text)}</text>`).join('\n');
  for(const m of matches) checkTextBounds(m,m.center_px,m.font_size*w/doc.width,w,h,m.anchor);
  const svg=`<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img">\n  <title>실험 장치 모식도</title>\n  <image x="0" y="0" width="${w}" height="${h}" href="data:image/png;base64,${cleanPNG.toString('base64')}"/>\n  <g id="labels" font-family="${escapeXML(font)}" fill="black">\n${texts}\n  </g>\n</svg>\n`;
  const finalPNG=await sharp(Buffer.from(svg),{limitInputPixels:80e6}).png().toBuffer();
  fs.mkdirSync(path.dirname(prefix),{recursive:true});
  fs.writeFileSync(outputs.clean,cleanPNG);fs.writeFileSync(outputs.svg,svg);fs.writeFileSync(outputs.png,finalPNG);
  fs.writeFileSync(outputs.report,JSON.stringify({version:1,input_image:path.basename(input),width:w,height:h,labels:matches.map(({search_radius,background,...m})=>({...m,...(background ? {background_corners_gray:background.corners}: {})}))},null,2)+'\n');
  return outputs;
}
if(require.main===module) {
  const args=process.argv.slice(2);
  if(args.length!==3) {console.error('Usage: node compose_labels.js generated.png labels.json output/prefix');process.exitCode=2;}
  else compose(...args).then(outputs=>console.log(JSON.stringify(outputs,null,2))).catch(e=>{console.error('Error: '+e.message);process.exitCode=1;});
}
module.exports={compose,detect,parseLabels};