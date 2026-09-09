import {spawn} from 'node:child_process';
import {mkdtemp, readFile, writeFile, rm} from 'node:fs/promises';
import {join} from 'node:path';

const profile = await mkdtemp('/private/tmp/makera-browser-');
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'
], {stdio: 'ignore'});
let socket;
try {
  let port;
  for (let i = 0; i < 100; i++) {
    try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break; }
    catch { await new Promise(resolve => setTimeout(resolve, 100)); }
  }
  if (!port) throw new Error('Chrome did not start');
  const tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let next = 0;
  const pending = new Map();
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (pending.has(message.id)) {
      const {resolve, reject, timer} = pending.get(message.id); pending.delete(message.id); clearTimeout(timer);
      message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result);
    }
  };
  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++next;
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Timeout: ${method}`)); }, 15000);
      pending.set(id, {resolve, reject, timer}); socket.send(JSON.stringify({id, method, params}));
    });
  }
  async function evaluate(expression) {
    const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', {width: 1440, height: 1080, deviceScaleFactor: 1, mobile: false});
  await send('Page.navigate', {url: 'http://127.0.0.1:8768/'});
  for (let i = 0; i < 80; i++) {
    if (await evaluate('Boolean(window.MAKERA_PAGES && document.querySelector("#search"))')) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  const count = await evaluate('window.MAKERA_PAGES.length');
  if (count !== 91) throw new Error(`Unexpected page count: ${count}`);
  const found = await evaluate(`(() => { const input=document.querySelector('#search'); input.value='palpage'; input.dispatchEvent(new Event('input')); return {visible: !document.querySelector('#search-results').hidden, count:document.querySelectorAll('.search-result').length}; })()`);
  if (!found.visible || found.count < 1) throw new Error(`Search failed: ${JSON.stringify(found)}`);
  await evaluate("document.querySelector('#search-close').click()");
  const desktop = await send('Page.captureScreenshot', {format: 'png'});
  await writeFile('/private/tmp/makera-desktop.png', Buffer.from(desktop.data, 'base64'));
  await send('Emulation.setDeviceMetricsOverride', {width: 390, height: 844, deviceScaleFactor: 1, mobile: true});
  await new Promise(resolve => setTimeout(resolve, 150));
  const mobile = await evaluate(`(() => { document.querySelector('#menu-toggle').click(); return {open:document.body.classList.contains('menu-open'), expanded:document.querySelector('#menu-toggle').getAttribute('aria-expanded'), overflow:document.documentElement.scrollWidth>innerWidth}; })()`);
  if (!mobile.open || mobile.expanded !== 'true' || mobile.overflow) throw new Error(`Mobile failed: ${JSON.stringify(mobile)}`);
  await evaluate("document.querySelector('#menu-toggle').click()");
  await new Promise(resolve => setTimeout(resolve, 250));
  const screenshot = await send('Page.captureScreenshot', {format: 'png'});
  await writeFile('/private/tmp/makera-mobile.png', Buffer.from(screenshot.data, 'base64'));
  console.log(JSON.stringify({pages: count, searchResults: found.count, mobileMenu: 'OK', horizontalOverflow: false}));
} finally {
  if (socket) socket.close();
  chrome.kill('SIGTERM');
  await new Promise(resolve => { chrome.once('exit', resolve); setTimeout(resolve, 2000); });
  await rm(profile, {recursive: true, force: true});
}
