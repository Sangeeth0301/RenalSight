import { expect, test } from "@playwright/test";
import { addLab, profile, register, signedIn } from "./helpers";

test("patient adds a lab: eGFR, stage, Living Kidney, forecast, care plan and rituals all respond", async ({ browser, request }) => {
  const a = await register(request, "patient", "Asha Test");
  await profile(request, a, { sex: "female", birth_year: 1964 });
  const { ctx, page } = await signedIn(browser, a);

  await page.goto("/home");
  await expect(page.getByText("Add lab report").first()).toBeVisible();          // no labs yet

  // ---- report guidance: validation, then a real lab
  await page.goto("/reports");
  await page.getByTestId("lab-save").click();
  await expect(page.getByText("Enter at least one value")).toBeVisible();
  await page.getByTestId("lab-scr").fill("99");
  await page.getByTestId("lab-save").click();
  await expect(page.getByText("out of range").first()).toBeVisible();
  await page.getByTestId("lab-scr").fill("2.2");
  await page.getByTestId("lab-acr").fill("340");
  await page.getByTestId("lab-sbp").fill("154");
  await page.getByTestId("lab-hba1c").fill("8.3");
  await page.getByTestId("lab-hgb").fill("11.3");
  await page.getByTestId("lab-potassium").fill("5.1");
  await page.getByTestId("lab-save").click();
  const analysis = page.getByTestId("analysis");
  await expect(analysis).toBeVisible();
  await expect(analysis).toContainText("eGFR");
  await expect(analysis).toContainText("Stage 4");
  await expect(page.getByTestId("lab-row")).toHaveCount(1);

  // ---- living kidney: stage, wounds, tapping a wound explains it
  await page.goto("/kidney");
  await expect(page.getByTestId("stage-chip")).toContainText("Stage 4");
  await expect(page.getByTestId("egfr")).not.toHaveText("-");
  const spots = page.locator('button[aria-label="Cracks"], button[aria-label="Swollen veins"], button[aria-label="Leaking drops"]');
  await expect(spots.first()).toBeVisible();
  await spots.first().click();
  await expect(page.getByText(/Take medicines|Controlling blood pressure|Eat less salt/).first()).toBeVisible();
  await page.keyboard.press("Escape");

  // ---- time machine: chart, slider ages the kidney, what-if, group outlook, no date of death
  await page.goto("/forecast");
  await expect(page.getByTestId("forecast-chart")).toBeVisible();
  await expect(page.getByTestId("case-expected")).toBeVisible();
  await page.getByTestId("year-slider").fill("12");
  await expect(page.getByTestId("year-label")).toHaveText("12");
  await page.getByTestId("wi-sbp").fill("120");
  await page.getByTestId("wi-hba1c").fill("6.8");
  await page.getByTestId("wi-apply").click();
  await expect(page.getByTestId("wi-result")).toBeVisible();
  await expect(page.getByTestId("outlook")).toContainText("These are group averages");
  await expect(page.locator("body")).not.toContainText(/date of death/i);

  // ---- care lab: goal cards, tick progress
  await page.goto("/care");
  await expect(page.getByTestId("lane-quick")).toBeVisible();
  await expect(page.getByTestId("care-progress")).toHaveText(/^0\//);
  await page.getByTestId("tick-avoid_nsaids").click();
  await expect(page.getByTestId("care-progress")).toHaveText(/^1\//);

  // ---- daily rituals: streak and score update
  await page.goto("/rituals");
  await page.getByTestId("med_morning").click();
  await page.getByTestId("med_noon").click();
  await page.getByTestId("med_night").click();
  await page.getByTestId("glass-6").click();
  await page.getByTestId("low-salt").click();
  await expect(page.getByTestId("score")).toHaveText("100%");
  await expect(page.getByTestId("streak")).toContainText("1-day streak");
  await page.getByTestId("sym-breathless").click();
  await expect(page.getByRole("alert")).toContainText(/need a doctor today/i);

  // ---- delete the lab -> kidney page goes back to the empty state
  await page.goto("/reports");
  await page.getByRole("button", { name: "Delete" }).first().click();
  await page.getByTestId("confirm-delete").click();
  await expect(page.getByTestId("lab-row")).toHaveCount(0);
  await ctx.close();
});

test("quick CKD check and eGFR calculator", async ({ browser, request }) => {
  const a = await register(request, "patient", "Quick Test");
  await profile(request, a);
  const { ctx, page } = await signedIn(browser, a);
  await page.goto("/reports");
  await page.getByRole("tab", { name: "Quick CKD check" }).click();
  await page.getByTestId("q-sc").fill("4.1");
  await page.getByTestId("q-hemo").fill("9");
  await page.getByTestId("q-bu").fill("80");
  await page.getByTestId("q-run").click();
  const res = page.getByTestId("q-result");
  await expect(res).toContainText("High");
  await expect(page.getByTestId("q-answered")).toContainText("/14");
  await page.getByRole("tab", { name: "eGFR calculator" }).click();
  await page.getByTestId("c-scr").fill("1.0");
  await page.getByTestId("c-age").fill("60");
  await page.getByTestId("c-run").click();
  await expect(page.getByTestId("c-result")).toContainText("86");
  await ctx.close();
});

test("lab report reader: paste text, check values, apply to the form", async ({ browser, request }) => {
  const a = await register(request, "patient", "Reader");
  await profile(request, a);
  const { ctx, page } = await signedIn(browser, a);
  await page.goto("/reports");
  await page.getByTestId("upload-text").fill("Date: 14/06/2026\nCreatinine 203 umol/L\nPotassium 5.4 mmol/L\nHbA1c 64 mmol/mol\nBP 150/92");
  await page.getByTestId("upload-read").click();
  await expect(page.getByTestId("upload-result")).toContainText("2.3");
  await page.getByTestId("upload-apply").click();
  await expect(page.getByTestId("lab-scr")).toHaveValue("2.3");
  await expect(page.getByTestId("lab-potassium")).toHaveValue("5.4");
  await expect(page.getByTestId("lab-sbp")).toHaveValue("150");
  await page.getByTestId("lab-save").click();
  await expect(page.getByTestId("analysis")).toBeVisible();
  // a photo cannot be read without OCR software: a friendly message, no crash
  await page.getByTestId("upload-file").setInputFiles({ name: "scan.png", mimeType: "image/png", buffer: Buffer.from("fake-png") });
  await expect(page.getByTestId("upload-msg")).toContainText(/photo|type the numbers/i);
  await ctx.close();
});
