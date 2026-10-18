import { expect, type APIRequestContext, type Browser, type BrowserContext, type Page } from "@playwright/test";

export const API = "http://127.0.0.1:8000";
export const PASSWORD = "Demo@12345";
let counter = 0;
export const uniq = (prefix: string) => `${prefix}${Date.now().toString(36)}${(counter++).toString(36)}`;

export interface Account { email: string; token: string; user: any }

export async function register(request: APIRequestContext, role: "patient" | "doctor" | "caregiver", name: string, lang = "en"): Promise<Account> {
  const email = `${uniq("e2e")}@example.com`;
  const r = await request.post(`${API}/auth/register`, { data: { email, password: PASSWORD, name, role, language: lang } });
  expect(r.status()).toBe(201);
  const body = await r.json();
  return { email, token: body.access_token, user: body.user };
}

export const authz = (a: Account) => ({ Authorization: `Bearer ${a.token}` });

export async function profile(request: APIRequestContext, a: Account, data: Record<string, unknown> = {}) {
  const r = await request.put(`${API}/me/profile`, { headers: authz(a), data: { birth_year: 1962, sex: "male", diabetes: true, hypertension: true, ...data } });
  expect(r.ok()).toBeTruthy();
}

export async function addLab(request: APIRequestContext, a: Account, data: Record<string, unknown> = {}) {
  const r = await request.post(`${API}/labs`, { headers: authz(a), data: { taken_on: "2026-06-01", scr: 2.0, acr: 300, sbp: 150, hba1c: 8.1, hgb: 12, potassium: 4.9, ...data } });
  expect(r.status()).toBe(201);
  return r.json();
}

export async function linkDoctor(request: APIRequestContext, patient: Account, doctor: Account) {
  const r = await request.post(`${API}/me/doctor`, { headers: authz(patient), data: { code: doctor.user.doctor_code } });
  expect(r.ok()).toBeTruthy();
}

/** A browser page that is already signed in as `a` (token in localStorage), language fixed to English. */
export async function signedIn(browser: Browser, a: Account, lang = "en"): Promise<{ ctx: BrowserContext; page: Page }> {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
  await ctx.addInitScript(([t, l]) => { localStorage.setItem("renalsight_token", t as string); localStorage.setItem("renalsight_lang", l as string); }, [a.token, lang]);
  const page = await ctx.newPage();
  return { ctx, page };
}

export async function anonymous(browser: Browser, lang = "en"): Promise<{ ctx: BrowserContext; page: Page }> {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
  await ctx.addInitScript((l) => { localStorage.setItem("renalsight_lang", l as string); }, lang);
  const page = await ctx.newPage();
  return { ctx, page };
}

export async function loginAs(request: APIRequestContext, email: string, password = PASSWORD): Promise<Account> {
  const r = await request.post(`${API}/auth/login`, { data: { email, password } });
  expect(r.status()).toBe(200);
  const b = await r.json();
  return { email, token: b.access_token, user: b.user };
}
