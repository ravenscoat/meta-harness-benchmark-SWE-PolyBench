// Private evaluator: launch an isolated headless browser and real local API.
const {spawn} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const [repo, domain, python, playwrightPath, logs, browserExecutable] = process.argv.slice(2);
const {chromium} = require(playwrightPath);
const payload = {
  'seat-booking': {key:'browser',show:'A',seats:1},
  'stock-transfer': {key:'browser',source:'A',target:'B',amount:2,source_version:1,target_version:1},
  'invoice-allocation': {key:'browser',total:2,weights:[{id:'a',weight:1},{id:'b',weight:1}]},
  'inbox-ack': {key:'browser',messages:[{id:'A',version:1}]}
}[domain];
const delay=ms=>new Promise(r=>setTimeout(r,ms));

(async()=>{
  fs.mkdirSync(logs,{recursive:true});
  // Bind a dynamic port before handing its socket to uvicorn via an inherited
  // descriptor is not portable on Windows. The API writes its selected port.
  const portFile=path.join(logs,'api-port.txt');
  const program="import socket,uvicorn;from pathlib import Path;s=socket.socket();s.bind(('127.0.0.1',0));s.listen(128);Path("+JSON.stringify(portFile)+").write_text(str(s.getsockname()[1]));uvicorn.Server(uvicorn.Config('backend.app:app',log_level='warning')).run(sockets=[s])";
  const api=spawn(python,['-c',program],{cwd:repo,env:{...process.env,PYTHONPATH:repo,HX_DB:path.join(logs,'browser.sqlite3')},stdio:['ignore','pipe','pipe'],windowsHide:true});
  const apiOutput=[];
  api.stderr.on('data',d=>apiOutput.push(String(d)));
  api.stdout.on('data',d=>apiOutput.push(String(d)));
  let server,browser;
  try {
    for(let n=0;n<100 && !fs.existsSync(portFile);n++) await delay(50);
    assert.ok(fs.existsSync(portFile),'API did not bind');
    const apiURL='http://127.0.0.1:'+fs.readFileSync(portFile,'utf8');
    let ready=false;
    for(let n=0;n<100;n++) {
      try {if((await fetch(apiURL+'/health')).ok){ready=true;break;}}catch{}
      await delay(50);
    }
    assert.ok(ready,'API did not become healthy');
    const {createServer}=await import(pathToFileURL(path.join(repo,'frontend/node_modules/vite/dist/node/index.js')));
    server=await createServer({root:path.join(repo,'frontend'),configFile:false,server:{host:'127.0.0.1',port:0,proxy:{'/operation':apiURL}},logLevel:'error'});
    await server.listen();
    const url='http://127.0.0.1:'+server.httpServer.address().port;
    browser=await chromium.launch({headless:true,executablePath:browserExecutable});
    const context=await browser.newContext();
    await context.tracing.start({screenshots:true,snapshots:true,sources:false});
    const page=await context.newPage();
    page.setDefaultTimeout(7000);
    // Permit only the local app/API network.
    await context.route('**/*',route=>{
      const u=new URL(route.request().url());
      return ['127.0.0.1','localhost'].includes(u.hostname)?route.continue():route.abort();
    });
    await page.goto(url);
    const input=page.getByRole('textbox',{name:'JSON operation'});
    const submit=page.getByRole('button',{name:'Submit operation'});
    const owner=page.getByRole('combobox',{name:'Owner'});
    const output=page.getByLabel('Operation result');
    let release,arrived,requests=0;
    const gate=new Promise(r=>release=r),started=new Promise(r=>arrived=r);
    await page.route('**/operation',async route=>{
      requests++;
      const response=await route.fetch();
      arrived();await gate;await route.fulfill({response});
    });
    await input.fill(JSON.stringify(payload));
    await submit.click();await started;
    await submit.click();
    const edited=JSON.stringify({...payload,key:'typed-during-await'});
    await input.fill(edited);release();
    await page.getByRole('status').filter({hasText:'Idle'}).waitFor();
    assert.equal(await input.inputValue(),edited,'completion erased newer typing');
    assert.equal(requests,1,'duplicate pending submission');
    assert.ok((await output.textContent()).includes('resources'),'real API result missing');
    await page.unroute('**/operation');

    // Reset by switching owner. Delay alpha request, cycle alpha->beta->alpha,
    // and complete a newer alpha request before releasing the obsolete one.
    await owner.selectOption('beta');await owner.selectOption('alpha');
    const old={...payload,key:'obsolete'};
    if(domain==='stock-transfer'){old.source_version=2;old.target_version=2;}
    if(domain==='inbox-ack') old.messages=[{id:'A',version:2}];
    let releaseOld,oldArrived;
    const oldGate=new Promise(r=>releaseOld=r),oldStarted=new Promise(r=>oldArrived=r);
    await page.route('**/operation',async route=>{
      const b=route.request().postDataJSON();
      if(b.key==='obsolete'){
        const response=await route.fetch();oldArrived();await oldGate;await route.fulfill({response});
      } else await route.continue();
    });
    await input.fill(JSON.stringify(old));await submit.click();await oldStarted;
    await owner.selectOption('beta');await owner.selectOption('alpha');
    const fresh={...payload,key:'fresh-after-switch'};
    if(domain==='stock-transfer'){fresh.source_version=3;fresh.target_version=3;}
    if(domain==='inbox-ack') fresh.messages=[{id:'A',version:3}];
    await input.fill(JSON.stringify(fresh));await submit.click();
    await page.getByRole('status').filter({hasText:'Idle'}).waitFor();
    const freshResult=await output.textContent();
    assert.ok(freshResult.includes('resources'),'new generation could not submit');
    releaseOld();await delay(250);
    assert.equal(await output.textContent(),freshResult,'obsolete result overwrote current generation');
    await page.screenshot({path:path.join(logs,'final.png'),fullPage:true});
    await context.tracing.stop({path:path.join(logs,'trace.zip')});
    console.log('real browser typing, coalescing, owner-generation and live API checks passed');
  } finally {
    fs.writeFileSync(path.join(logs,'api-output.txt'),apiOutput.join(''));
    if(browser) await browser.close();
    if(server) await server.close();
    api.kill();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
