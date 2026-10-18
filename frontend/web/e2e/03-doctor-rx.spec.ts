import { expect, test } from "@playwright/test";
import { addLab, API, authz, linkDoctor, profile, register, signedIn } from "./helpers";

test("prescription flow: patient request -> doctor safety block -> override sign -> patient sees doses and PDF", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Flow");
  const pat = await register(request, "patient", "Pat Flow");
  await profile(request, pat);
  await addLab(request, pat);
  await linkDoctor(request, pat, doc);
  const { ctx: pctx, page: p } = await signedIn(browser, pat);
  const { ctx: dctx, page: d } = await signedIn(browser, doc);

  // patient asks for a plan: lifestyle advice and medicine labels, but never doses
  await p.goto("/rx");
  await p.getByTestId("rx-request").click();
  await expect(p.getByTestId("rx-detail")).toBeVisible();
  await expect(p.getByTestId("do-not-take")).toBeVisible();
  await expect(p.getByTestId("rx-detail")).not.toContainText(/\d+ mg/);
  await expect(p.getByText("Waiting for your doctor").first()).toBeVisible();
  await p.getByTestId("rx-submit").click();
  await expect(p.getByText("With your doctor").first()).toBeVisible();

  // doctor: queue -> editor
  await d.goto("/doctor/queue");
  await expect(d.getByTestId("queue-item")).toHaveCount(1);
  await d.getByTestId("queue-item").click();
  await expect(d.getByTestId("safety-ok")).toBeVisible();
  await expect(d.getByTestId("dose-0")).toBeVisible();                           // doctor sees doses

  // add an NSAID: blocking warning, signing asks for a written override
  await d.getByTestId("add-drug").selectOption("ibuprofen");
  await d.getByTestId("save-items").click();
  await expect(d.getByTestId("safety-blocked")).toBeVisible();
  await expect(d.getByTestId("warn-nsaid_ckd")).toBeVisible();
  await d.getByTestId("sign").click();
  await expect(d.getByTestId("override-reason")).toBeVisible();
  await expect(d.getByTestId("sign-anyway")).toBeDisabled();                     // needs 10+ characters
  await d.getByTestId("override-reason").fill("Short course agreed with the patient and monitored closely");
  await d.getByTestId("sign-anyway").click();
  await expect(d.getByText("Signed by doctor").first()).toBeVisible();
  await expect(d.getByText(/Override:/)).toBeVisible();

  // patient: bell shows the notification, signed prescription has doses, PDF opens
  await p.goto("/rx");
  await p.getByTestId("rx-item").first().click();
  await expect(p.getByTestId("signed-items")).toContainText("mg");
  await expect(p.getByTestId("do-not-take")).toHaveCount(0);
  const [resp] = await Promise.all([p.waitForResponse((r) => /\/rx\/\d+\/pdf/.test(r.url())), p.getByTestId("rx-pdf").click()]);
  expect(resp.status()).toBe(200);                                                // sent with the Authorization header
  expect(resp.headers()["content-type"]).toContain("application/pdf");
  const list = await (await request.get(`${API}/rx`, { headers: authz(pat) })).json();
  const pdf = await request.get(`${API}/rx/${list[0].id}/pdf`, { headers: authz(pat) });
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  await p.goto("/notifications");
  await expect(p.getByTestId("notification").first()).toContainText("Your prescription is ready");

  // signed prescriptions are read-only; the doctor can create a revision
  await d.reload();
  await expect(d.getByTestId("revise")).toBeVisible();
  await expect(d.getByTestId("sign")).toHaveCount(0);
  await d.getByTestId("revise").click();
  await expect(d.getByText("Draft").first()).toBeVisible();
  await pctx.close();
  await dctx.close();
});

test("doctor panel ranks patients by severity and a patient without labs cannot request a plan", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Rank");
  const bad = await register(request, "patient", "Critical Pat");
  const good = await register(request, "patient", "Healthy Pat");
  const none = await register(request, "patient", "NoLabs Pat");
  for (const p of [bad, good, none]) { await profile(request, p); await linkDoctor(request, p, doc); }
  await addLab(request, bad, { scr: 4.6, acr: 900, sbp: 172, potassium: 6.1 });
  await addLab(request, good, { scr: 0.8, acr: 8, sbp: 116, potassium: 4.2 });
  const { ctx, page } = await signedIn(browser, doc);
  await page.goto("/doctor");
  const cards = page.getByTestId("patient-card");
  await expect(cards).toHaveCount(3);
  await expect(cards.first()).toContainText("Critical Pat");
  await expect(cards.first()).toContainText("Urgent");
  await page.getByTestId("patient-search").fill("Healthy");
  await expect(cards).toHaveCount(1);
  await cards.first().click();                                                       // touching a patient opens the quick-view drawer
  await expect(page.getByTestId("drawer")).toContainText("Healthy Pat");
  await page.getByTestId("open-record").click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Healthy Pat");
  await expect(page.getByText("Forecast")).toBeVisible();
  await ctx.close();

  const { ctx: c2, page: p2 } = await signedIn(browser, none);
  await p2.goto("/rx");
  await p2.getByTestId("rx-request").click();
  await expect(p2.getByText(/lab report with creatinine/i).first()).toBeVisible();
  await c2.close();
});

test("role guards: a patient cannot open the doctor portal and a doctor cannot open patient pages", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Guard");
  const pat = await register(request, "patient", "Pat Guard");
  const { ctx, page } = await signedIn(browser, pat);
  await page.goto("/doctor");
  await expect(page).toHaveURL(/home/);
  await ctx.close();
  const { ctx: c2, page: p2 } = await signedIn(browser, doc);
  await p2.goto("/reports");
  await expect(p2).toHaveURL(/doctor/);
  await c2.close();
});
