import { expect, test } from "@playwright/test";
import { addLab, linkDoctor, profile, register, signedIn, anonymous } from "./helpers";

test("type a hospital, patient and blood group: message is written and WhatsApp opens in one click; public page takes an offer", async ({ browser, request }) => {
  const p = await register(request, "patient", "Anita Rao");
  const { ctx, page } = await signedIn(browser, p);
  await page.goto("/hub/request/new");
  await page.getByTestId("hospital-input").fill("KMCH");
  await page.getByRole("listbox").getByRole("option").first().click();
  await expect(page.getByTestId("hospital-input")).toHaveValue(/Kovai Medical/);
  await page.getByTestId("patient-name").fill("Ravi Kumar");
  await page.getByTestId("blood-group").selectOption("B+");
  await page.getByTestId("contact-phone").fill("98765 43210");

  const text = page.getByTestId("share-text");
  await expect(text).toHaveValue(/Ravi Kumar/, { timeout: 15000 });
  await expect(text).toHaveValue(/Kovai Medical/);
  await expect(text).toHaveValue(/B\+/);
  await expect(text).toHaveValue(/never paid/);
  const wa = await page.getByTestId("wa-send").getAttribute("href");
  expect(wa).toMatch(/^https:\/\/wa\.me\/\?text=/);
  expect(decodeURIComponent(wa!)).toContain("Ravi Kumar");

  await page.getByRole("tab", { name: "தமிழ்" }).click();                                   // same request in Tamil
  await expect(text).toHaveValue(/இரத்த வகை/, { timeout: 15000 });
  await page.getByRole("tab", { name: "English" }).click();

  // saved contacts get one-click WhatsApp links with their own number
  await page.getByTestId("contacts-raw").fill("Meena, 9123456789");
  await page.getByTestId("contacts-add").click();
  await expect(page.locator('a[href*="wa.me/919123456789"]')).toBeVisible();

  await page.getByTestId("save-request").click();
  await expect(page).toHaveURL(/\/hub\/request\/\d+/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Ravi Kumar");
  const url = await page.locator("p.break-all").first().textContent();
  expect(url).toMatch(/\/r\/[\w-]+$/);

  // anyone can open the public page (masked phone) and offer to be tested
  const pub = await anonymous(browser);
  await pub.page.goto(new URL(url!).pathname);
  await expect(pub.page.getByTestId("pub-patient")).toHaveText("Ravi Kumar");
  await expect(pub.page.locator("body")).not.toContainText("98765 43210");
  await pub.page.getByTestId("offer-name").fill("Kind Stranger");
  await pub.page.getByTestId("offer-phone").fill("9000012345");
  await expect(pub.page.getByTestId("offer-send")).toBeDisabled();                         // consent required first
  await pub.page.getByTestId("offer-consent").check();
  await pub.page.getByTestId("offer-send").click();
  await expect(pub.page.getByTestId("offer-done")).toBeVisible();
  await pub.ctx.close();

  await page.reload();
  await expect(page.getByTestId("offers")).toContainText("Kind Stranger");
  await ctx.close();
});

test("donor pledge enforces: hearts only after death; hospitals directory and seat board; compat checker", async ({ browser, request }) => {
  const p = await register(request, "patient", "Donor Dev");
  const { ctx, page } = await signedIn(browser, p);
  await page.goto("/hub");
  await page.getByTestId("bg-O+").click();
  await expect(page.getByTestId("compat-result")).toContainText("O");
  await page.getByTestId("bg-AB+").click();
  await expect(page.getByTestId("compat-result")).toContainText("AB, A, B, O");

  await page.goto("/hub/donate");
  await page.getByTestId("pledge-bg").selectOption("O+");
  await page.getByTestId("pledge-consent").check();
  await expect(page.getByTestId("organs")).toContainText("heart");
  await page.getByRole("tab", { name: "While alive" }).click();
  await expect(page.getByTestId("organs")).not.toContainText("heart");                    // hearts are not offered for living donation
  await page.getByRole("tab", { name: "After death" }).click();
  await page.getByTestId("pledge-save").click();
  await expect(page.getByTestId("donor-card")).toContainText("O+");
  await expect(page.getByTestId("donor-card")).toContainText("heart");

  await page.goto("/hub/hospitals");
  await page.getByTestId("hospital-search").fill("kolkata");
  await expect(page.getByTestId("hospital-list")).toContainText("AMRI");
  await page.getByRole("tab", { name: "Dialysis seats" }).click();
  await expect(page.getByTestId("seat-list")).toBeVisible();
  await ctx.close();
});

test("journey checklist, dialysis log warning, emergency ID with exports", async ({ browser, request }) => {
  const p = await register(request, "patient", "Journey Joe");
  const { ctx, page } = await signedIn(browser, p);
  await page.goto("/hub/journey");
  await expect(page.getByTestId("journey-progress")).toHaveText("0%");
  await page.getByTestId("step-nephrologist").click();
  await expect(page.getByTestId("journey-progress")).toHaveText("10%");

  await page.goto("/hub/dialysis");
  for (const [d, pre, post] of [["2026-10-01", "70", "67.5"], ["2026-10-03", "71", "68"]]) {
    await page.locator('input[type="date"]').fill(d);
    await page.getByTestId("pre-weight").fill(pre);
    await page.getByTestId("post-weight").fill(post);
    await page.getByTestId("add-session").click();
    await expect(page.getByTestId("session-rows")).toContainText(d);
  }
  await expect(page.getByTestId("dialysis-warning")).toContainText("3 kg");

  await page.goto("/hub/id");
  await page.locator("select").first().selectOption("A+");
  await page.getByTestId("save-card").click();
  await expect(page.getByTestId("id-card")).toContainText("A+");
  const dl = page.waitForEvent("download");
  await page.getByTestId("export-fhir").click();
  expect((await dl).suggestedFilename()).toBe("renalsight-fhir.json");
  await ctx.close();
});

test("coordinator desk: a doctor verifies a request and the patient sees the badge", async ({ browser, request }) => {
  const patient = await register(request, "patient", "Needs Help");
  const doctor = await register(request, "doctor", "Dr Verify");
  const created = await request.post("http://127.0.0.1:8000/requests", { headers: { Authorization: `Bearer ${patient.token}` },
    data: { hospital_name: "AIIMS", patient_name: "Desk Patient", blood_group: "O-", contact_phone: "9000000042" } });
  expect(created.ok()).toBeTruthy();
  const d = await signedIn(browser, doctor);
  await d.page.goto("/hub/desk");
  const row = d.page.getByTestId("desk-list").locator("div", { hasText: "Desk Patient" }).first();
  await row.getByRole("button", { name: "Verify" }).click();
  await expect(d.page.getByTestId("desk-list")).toContainText("Verified");
  await d.ctx.close();
  const { page, ctx } = await signedIn(browser, patient);
  await page.goto("/hub");
  await expect(page.getByTestId("request-row").first()).toContainText("Verified");
  await ctx.close();
});

test("lab form can be filled from real dataset samples (no typing)", async ({ browser, request }) => {
  const p = await register(request, "patient", "Sample Sam");
  const { ctx, page } = await signedIn(browser, p);
  await page.goto("/reports");
  await page.getByTestId("sample-failure").click();
  await expect(page.getByTestId("sample-info")).toContainText("NHANES");
  const scr = Number(await page.getByTestId("lab-scr").inputValue());
  expect(scr).toBeGreaterThan(2.5);                                  // kidney failure band has high creatinine
  await page.getByTestId("sample-normal").click();
  await expect.poll(async () => Number(await page.getByTestId("lab-scr").inputValue())).toBeLessThan(1.3);
  await ctx.close();
});

test("WhatsApp messages page: doctor and patient can message a group or each person with their name filled in", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Wa");
  const pat = await register(request, "patient", "Wa Pat");
  await profile(request, pat);
  await linkDoctor(request, pat, doc);

  const d = await signedIn(browser, doc);
  await d.page.goto("/hub/broadcast");
  await d.page.getByTestId("tpl-lab").click();
  await expect(d.page.getByTestId("bc-text")).toHaveValue(/kidney blood and urine tests/);
  await d.page.getByTestId("bc-raw").fill("Meena Devi, 98765 43210");
  await d.page.getByTestId("bc-add").click();
  await d.page.getByTestId("import-patients").click();
  await expect(d.page.getByTestId("bc-list")).toContainText("Wa Pat");
  const send = d.page.locator('a[href*="wa.me/919876543210"]');
  await expect(send).toBeVisible();
  expect(decodeURIComponent((await send.getAttribute("href"))!)).toContain("Hello Meena,");        // personalised with the first name
  await d.page.getByRole("tab", { name: /WhatsApp group/ }).click();
  const g = await d.page.getByTestId("bc-group-send").getAttribute("href");
  expect(g).toMatch(/^https:\/\/wa\.me\/\?text=/);
  expect(decodeURIComponent(g!)).toContain("Hello everyone,");
  await d.ctx.close();

  const p = await signedIn(browser, pat);
  await p.page.goto("/hub/broadcast");
  await expect(p.page.getByTestId("tpl-update")).toBeVisible();
  await expect(p.page.getByTestId("import-patients")).toHaveCount(0);                          // patients do not get the patient-import button
  await p.ctx.close();
});

test("Send on WhatsApp button: only the four allowed people are offered; doctor needs consent first", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Qs");
  const pat = await register(request, "patient", "Qs Pat");
  await profile(request, pat);
  await addLab(request, pat, { scr: 2.4, acr: 300 });
  await linkDoctor(request, pat, doc);

  const p = await signedIn(browser, pat);
  await p.page.goto("/home");
  await p.page.getByTestId("quick-whatsapp").click();
  await expect(p.page.getByTestId("qs-preview")).toContainText("Qs Pat");
  await expect(p.page.getByTestId("qs-preview")).toContainText("eGFR");
  const rec = p.page.getByTestId("qs-recipients");
  for (const n of ["Sem 5 Project", "Sandeep", "Sangeeth (You)", "Jagan"]) await expect(rec).toContainText(n);
  await expect(rec.locator("li")).toHaveCount(4);                                              // nobody else can be added
  await p.ctx.close();

  const d = await signedIn(browser, doc);
  await d.page.goto("/doctor");
  await d.page.getByTestId("quick-whatsapp").click();
  await d.page.getByTestId("qs-patient").selectOption(String(pat.user.id));
  await expect(d.page.getByTestId("qs-consent")).not.toBeChecked();
  await d.page.getByTestId("qs-consent").check();
  await expect(d.page.getByTestId("qs-preview")).toContainText("Qs Pat");
  await d.ctx.close();
});
