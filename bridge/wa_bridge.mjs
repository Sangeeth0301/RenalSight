// RenalSight WhatsApp bridge (local only).
// Drives YOUR OWN WhatsApp Web in a normal, visible Google Chrome window (its own profile: bridge/chrome-profile) so the
// website's "Send now" button can message the people you selected, without WhatsApp asking who to send to.
//
//   node wa_bridge.mjs login              opens Chrome on WhatsApp Web; scan the QR code once with your phone
//   node wa_bridge.mjs status             is Chrome up and WhatsApp linked?
//   node wa_bridge.mjs send job.json      job = { id, text, recipients:[{name}], out:"result.json" }
//
// Keep that Chrome window open (you can minimise it). Only the named recipients in a job are ever messaged, and only by exact chat title.
// Unofficial automation of WhatsApp Web can be restricted by WhatsApp; keep volumes tiny, as this does.
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "..", "frontend", "web", "package.json"));
const { chromium } = require("playwright");
const CDP = "http://127.0.0.1:9222";
const PROFILE = path.join(here, "chrome-profile");
const STATE = path.join(here, "state.json");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const writeState = (o) => fs.writeFileSync(STATE, JSON.stringify({ ...o, at: new Date().toISOString() }));

async function cdpUp() {
  try { return (await fetch(CDP + "/json/version", { signal: AbortSignal.timeout(2000) })).ok; } catch { return false; }
}
function chromeExe() {
  const c = [process.env.CHROME_PATH, "C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    path.join(process.env.LOCALAPPDATA || "", "Google/Chrome/Application/chrome.exe"), "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"].filter(Boolean);
  const hit = c.find((p) => fs.existsSync(p));
  if (!hit) throw new Error("Google Chrome was not found. Install Chrome or set CHROME_PATH.");
  return hit;
}
async function ensureChrome() {
  if (await cdpUp()) return;
  spawn(chromeExe(), [`--remote-debugging-port=9222`, `--user-data-dir=${PROFILE}`, "--no-first-run", "--no-default-browser-check", "https://web.whatsapp.com/"], { detached: true, stdio: "ignore" }).unref();
  for (let i = 0; i < 60 && !(await cdpUp()); i++) await sleep(500);
  if (!(await cdpUp())) throw new Error("Could not start Chrome with the bridge profile.");
}
async function open({ front = false } = {}) {
  await ensureChrome();
  const browser = await chromium.connectOverCDP(CDP);
  const ctx = browser.contexts()[0];
  let page = ctx.pages().find((p) => p.url().includes("web.whatsapp.com"));
  if (!page) { page = await ctx.newPage(); await page.goto("https://web.whatsapp.com/", { waitUntil: "domcontentloaded" }); }
  if (front) await page.bringToFront().catch(() => {});
  return { browser, page };
}
const chatList = (page) => page.locator("#pane-side");
async function waitLinked(page, ms) {
  try { await chatList(page).waitFor({ timeout: ms }); return true; } catch { return false; }
}
async function takeOver(page) {                         // "WhatsApp is open in another window" -> use this one
  const btn = page.getByRole("button", { name: /use here/i });
  if (await btn.count()) await btn.first().click().catch(() => {});
}

async function typeMessage(page, text) {
  const box = page.locator('footer div[contenteditable="true"], div[role="textbox"][aria-label*="message" i]').last();
  await box.click();
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    if (lines[i]) await page.keyboard.insertText(lines[i]);
    if (i < lines.length - 1) await page.keyboard.press("Shift+Enter");
  }
}
async function headerTitle(page) {
  return ((await page.locator("#main header span[dir='auto'], #main header span[title]").first().textContent({ timeout: 8000 }).catch(() => "")) || "").trim();
}
async function sendCurrent(page, text) {
  await typeMessage(page, text);
  await page.keyboard.press("Enter");
  const first = text.split("\n")[0].slice(0, 25);
  await page.locator("#main").getByText(first, { exact: false }).last().waitFor({ timeout: 15000 });
  await sleep(1200);
}

// Exact chat title only. Never a phone number, never a "similar" name.
async function sendOne(page, r, text) {
  const self = /\(you\)\s*$/i.test(r.name);                       // "Sangeeth (You)" = the message-yourself chat
  const base = r.name.replace(/\s*\(you\)\s*$/i, "").trim();
  const search = page.locator('input[data-tab="3"], [contenteditable][data-tab="3"], input[role="textbox"]').first();
  await search.click();
  await page.keyboard.press("Control+A");
  await page.keyboard.press("Delete");
  await page.keyboard.insertText(r.search ?? base);
  await sleep(1500);
  const want = base.toLowerCase();
  const all = await chatList(page).locator("span[title]").evaluateAll((els) => els.map((e) => e.getAttribute("title") || ""));
  const hits = all.map((t, i) => [t.trim().toLowerCase(), i]).filter(([t]) => t === want);      // exact chat title only
  if (!hits.length) throw new Error(`no chat named "${r.name}" found`);
  const rows = chatList(page).locator("span[title]");
  for (const [, idx] of hits) {
    await rows.nth(idx).click();
    await sleep(1200);
    const head = ((await page.locator("#main header").first().innerText({ timeout: 8000 }).catch(() => "")) || "").toLowerCase();
    const isSelf = head.includes("message yourself");
    const lines = head.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);        // e.g. ["s", "sangeeth", "(you)", "message yourself"]: the first line is the avatar initial
    const nameOk = lines.includes(want) && (self ? lines.includes("(you)") : !lines.includes("(you)"));
    if (nameOk && isSelf === self) { await sendCurrent(page, text); await page.keyboard.press("Escape"); return; }
  }
  throw new Error(`could not confirm the chat "${r.name}" (the header did not match); nothing was sent`);
}

const cmd = process.argv[2];
if (cmd === "login") {
  const { browser, page } = await open({ front: true });
  await takeOver(page);
  // keep a picture of the QR for the website while we wait
  const snap = async () => { try { await page.screenshot({ path: path.join(here, "qr.png"), timeout: 5000 }); } catch { /* ignore */ } };
  const timer = setInterval(snap, 2500);
  const ok = await waitLinked(page, 300000);
  clearInterval(timer);
  try { fs.unlinkSync(path.join(here, "qr.png")); } catch { /* ignore */ }
  writeState({ linked: ok });
  await browser.close();
  process.exit(ok ? 0 : 2);
} else if (cmd === "status") {
  if (!(await cdpUp())) { console.log(JSON.stringify({ chrome: false, linked: false })); process.exit(0); }
  const { browser, page } = await open();
  await takeOver(page);
  const ok = await waitLinked(page, 20000);
  writeState({ linked: ok });
  await browser.close();
  console.log(JSON.stringify({ chrome: true, linked: ok }));
} else if (cmd === "send") {
  const job = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
  const results = [];
  const flush = (done) => fs.writeFileSync(job.out, JSON.stringify({ id: job.id, done, results }));
  flush(false);
  let browser;
  try {
    if (!(await cdpUp())) throw new Error("The WhatsApp Chrome window is closed. Click Link WhatsApp to open it again.");
    const o = await open();
    browser = o.browser;
    await takeOver(o.page);
    if (!(await waitLinked(o.page, 30000))) { writeState({ linked: false }); throw new Error("WhatsApp is not linked. Scan the QR code in the Chrome window."); }
    for (const r of job.recipients) {
      try { await sendOne(o.page, r, job.text); results.push({ name: r.name, ok: true }); }
      catch (e) { results.push({ name: r.name, ok: false, error: String(e.message || e).slice(0, 200) }); }
      flush(false);
      await sleep(2500);
    }
  } catch (e) {
    for (const r of job.recipients) if (!results.find((x) => x.name === r.name)) results.push({ name: r.name, ok: false, error: String(e.message || e).slice(0, 200) });
  }
  flush(true);
  if (browser) await browser.close();
} else {
  console.error("usage: node wa_bridge.mjs login|status|send job.json");
  process.exit(1);
}
