// `npm run mobile`: serves the app over a public HTTPS tunnel and prints a QR code,
// so a phone can open it. Press Ctrl+C to stop everything.
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import QRCode from 'qrcode';

// Not 4200, so this can run beside a normal `ng serve`.
const PORT = 4300;
const SERVE_TIMEOUT_MS = 180_000;
const TUNNEL_TIMEOUT_MS = 60_000;
const PUBLIC_TIMEOUT_MS = 60_000;

const frontendDir = dirname(dirname(fileURLToPath(import.meta.url)));
const children = [];
let stopping = false;

function findCloudflared() {
  const onPath = spawnSync(process.platform === 'win32' ? 'where' : 'which', ['cloudflared'], {
    encoding: 'utf8',
  });
  if (onPath.status === 0) {
    return onPath.stdout.split(/\r?\n/)[0].trim();
  }
  const windowsPaths = [
    'C:\\Program Files (x86)\\cloudflared\\cloudflared.exe',
    'C:\\Program Files\\cloudflared\\cloudflared.exe',
  ];
  return windowsPaths.find((path) => existsSync(path));
}

function stopAll(exitCode = 0) {
  if (stopping) {
    return;
  }
  stopping = true;
  console.log('\nStopped. The address no longer works. Run npm run mobile to start again.');
  for (const child of children) {
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    } else {
      child.kill();
    }
  }
  process.exit(exitCode);
}

function fail(message) {
  console.error(`\n${message}`);
  stopAll(1);
}

function start(command, args) {
  const child = spawn(command, args, { cwd: frontendDir, stdio: ['ignore', 'pipe', 'pipe'] });
  children.push(child);
  child.on('error', (error) => fail(`Could not start ${command}: ${error.message}`));
  child.on('exit', (code) => {
    if (!stopping) {
      fail(`${command} stopped unexpectedly (exit code ${code}).`);
    }
  });
  return child;
}

async function waitForApp() {
  const deadline = Date.now() + SERVE_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://localhost:${PORT}/`);
      if (response.ok) {
        return;
      }
    } catch {
      // The server isn't listening yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  fail('The app did not start in time.');
}

function waitForTunnel(tunnel) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => fail('cloudflared gave no address in time.'), TUNNEL_TIMEOUT_MS);
    const read = (chunk) => {
      const address = /https:\/\/(?!api\.)[a-z0-9-]+\.trycloudflare\.com/.exec(String(chunk));
      if (address) {
        clearTimeout(timer);
        resolve(address[0]);
      }
    };
    tunnel.stdout.on('data', read);
    tunnel.stderr.on('data', read);
  });
}

// A new address takes a moment to reach the internet, and a device that looks it up
// too early remembers the failure. So this asks a public DNS service, which keeps this
// computer from caching a miss, and it never stops the tunnel if the check is unsure.
async function waitForPublicAddress(address) {
  const { hostname } = new URL(address);
  const deadline = Date.now() + PUBLIC_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(
        `https://cloudflare-dns.com/dns-query?name=${hostname}&type=A`,
        { headers: { accept: 'application/dns-json' }, signal: AbortSignal.timeout(5000) },
      );
      if ((await response.json()).Answer?.length) {
        return;
      }
    } catch {
      // Not answered yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  console.log('Could not confirm the address yet. It may need another minute.');
}

async function showQrImage(address) {
  const file = join(tmpdir(), 'dealdirection-qr.png');
  await QRCode.toFile(file, address, { width: 640, margin: 4 });
  if (process.platform === 'win32') {
    spawn('explorer.exe', [file], { stdio: 'ignore', detached: true }).unref();
  }
  return file;
}

async function backendIsRunning() {
  try {
    return (await fetch('http://localhost:8000/api/health')).ok;
  } catch {
    return false;
  }
}

process.on('SIGINT', () => stopAll());
process.on('SIGTERM', () => stopAll());

const cloudflared = findCloudflared();
if (!cloudflared) {
  fail('cloudflared is not installed. On Windows run: winget install Cloudflare.cloudflared');
}

console.log('Starting the app...');
const app = start(process.execPath, [
  join('node_modules', '@angular', 'cli', 'bin', 'ng.js'),
  'serve',
  '--port',
  String(PORT),
  '--proxy-config',
  'proxy.conf.json',
]);
// Unread output would fill the pipe and freeze the server.
app.stdout.resume();
app.stderr.on('data', (chunk) => {
  if (/error/i.test(String(chunk))) {
    process.stderr.write(chunk);
  }
});
await waitForApp();

console.log('Opening the tunnel...');
const tunnel = start(cloudflared, [
  'tunnel',
  '--no-autoupdate',
  '--url',
  `http://localhost:${PORT}`,
]);
const address = await waitForTunnel(tunnel);
console.log('Waiting for the address to go live...');
await waitForPublicAddress(address);

const qrImage = await showQrImage(address);
console.log(`\n${await QRCode.toString(address, { type: 'terminal', small: true })}`);
console.log(`Scan the code with your phone, or open:\n${address}\n`);
console.log(`A larger code to scan: ${qrImage}`);
if (!(await backendIsRunning())) {
  console.log('Backend is off: login uses a demo account, and all data is fake.');
}
console.log('Anyone with this address can open the app while this runs.');
console.log('The address changes each time. Press Ctrl+C to stop.');
