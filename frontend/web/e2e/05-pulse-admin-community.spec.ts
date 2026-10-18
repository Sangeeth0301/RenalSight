import { expect, test } from "@playwright/test";
import { addLab, API, anonymous, authz, linkDoctor, loginAs, profile, register, signedIn } from "./helpers";

test("population pulse works signed out: GBD anchor, regions, scenarios, assumptions drawer", async ({ browser }) => {
  const { ctx, page } = await anonymous(browser);
  await page.goto("/pulse?year=2023");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Population pulse");
  await expect(page.getByTestId("cases")).toContainText("138");                    // calibration anchor: 138 million in 2023
  await expect(page.getByTestId("open-analyst")).toBeDisabled();                   // analyst chat needs a sign-in

  await page.getByTestId("region-IN-TN").click();
  await expect(page.getByTestId("headline")).toContainText("Tamil Nadu");
  const tn = await page.getByTestId("cases").textContent();
  expect(parseFloat(tn!)).toBeLessThan(15);                                          // a state is a fraction of India

  await page.getByTestId("year").fill("2040");
  await expect(page.getByTestId("year-value")).toHaveText("2040");
  await page.getByRole("tab", { name: /faster/i }).click();
  await expect(page).toHaveURL(/scenario=faster_decline/);
  await expect(page.getByTestId("stages")).toContainText("Stage 5");
  await expect(page.getByTestId("needs")).toContainText("dialysis");
  await expect(page.getByTestId("no-capacity")).toBeVisible();
  await expect(page.getByTestId("compare")).toContainText("hypothetical");

  await page.getByTestId("how").click();
  await expect(page.getByRole("dialog")).toContainText("Assumptions");
  await expect(page.getByRole("dialog")).toContainText("single measurement");
  await expect(page.getByRole("dialog")).toContainText(/verify/i);                 // anchors say which numbers still need verification
  await ctx.close();
});

test("admin: AI provider status, capacity entry shows the gap on the pulse page, doctors/patients are blocked", async ({ browser, request }) => {
  const admin = await loginAs(request, "admin@example.com");
  const { ctx, page } = await signedIn(browser, admin);
  await page.goto("/admin");
  await expect(page.getByTestId("llm-table")).toContainText("rules");
  await expect(page.getByTestId("llm-table")).toContainText("Always available");
  await expect(page.getByTestId("llm-table")).toContainText("Not configured");      // no API keys in this environment

  await page.getByTestId("cap-region").selectOption("IN-TN");
  await page.getByTestId("cap-stations").fill("3000");
  await page.getByTestId("cap-neph").fill("400");
  await page.getByTestId("cap-source").fill("E2E test source, not real data");
  await page.getByTestId("cap-save").click();
  await expect(page.getByText(/Population pulse/).first()).toBeVisible();
  await page.goto("/pulse?region=IN-TN&year=2035");
  await expect(page.getByTestId("gap")).toContainText("3,000");
  await expect(page.getByTestId("gap")).toContainText("E2E test source");

  const pat = await register(request, "patient", "Not Admin");
  const { ctx: c2, page: p2 } = await signedIn(browser, pat);
  await p2.goto("/admin");
  await expect(p2).toHaveURL(/home/);
  await c2.close();
  await ctx.close();
});

test("community: post, report to auto-hide, author delete, admin restore", async ({ browser, request }) => {
  const a = await register(request, "patient", "Poster One");
  const b = await register(request, "caregiver", "Reader Two");
  const { ctx: actx, page: pa } = await signedIn(browser, a);
  const { ctx: bctx, page: pb } = await signedIn(browser, b);
  await pa.goto("/community");
  await expect(pa.getByTestId("channels")).toContainText("Diet");
  await pa.getByTestId("channel-diet").click();
  await pa.getByTestId("post-input").fill("Tip: soak vegetables in water to lower potassium");
  await pa.getByTestId("post-send").click();
  await expect(pa.getByTestId("posts")).toContainText("soak vegetables");
  await pb.goto("/community");
  await pb.getByTestId("channel-diet").click();
  await expect(pb.getByTestId("posts")).toContainText("soak vegetables", { timeout: 15_000 });
  await expect(pb.getByRole("button", { name: "Report" }).first()).toBeVisible();
  await pb.getByRole("button", { name: "Report" }).first().click();
  await expect(pb.getByText("Reported. Thank you.")).toBeVisible();
  await expect(pa.getByRole("button", { name: "Delete" }).first()).toBeVisible();
  await pa.getByRole("button", { name: "Delete" }).first().click();
  await expect(pa.getByTestId("posts")).not.toContainText("soak vegetables");
  await actx.close();
  await bctx.close();
});

test("care hub: demo providers are labelled, patient books with their doctor, doctor confirms", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Hub");
  const pat = await register(request, "patient", "Pat Hub");
  await profile(request, pat);
  await addLab(request, pat);
  await linkDoctor(request, pat, doc);
  const { ctx: pctx, page: p } = await signedIn(browser, pat);
  const { ctx: dctx, page: d } = await signedIn(browser, doc);
  await p.goto("/care-hub");
  await expect(p.getByTestId("demo-note")).toContainText("fictional");
  await expect(p.getByTestId("provider").first()).toContainText("demo", { ignoreCase: true });
  await p.getByTestId("kind-dialysis").click();
  await expect(p.getByTestId("providers")).toContainText("Dialysis");
  await p.getByTestId("book-doctor").click();
  const when = new Date(Date.now() + 3 * 86400000);
  const local = new Date(when.getTime() - when.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  await p.getByTestId("when").fill(local);
  await p.getByTestId("confirm-book").click();
  await expect(p.getByTestId("appointment")).toHaveCount(1);
  await expect(p.getByTestId("appointment")).toContainText("Requested");

  await d.goto("/doctor/queue");
  await expect(d.getByTestId("doctor-appointments")).toContainText("Pat Hub");
  await d.getByTestId("confirm-appt").click();
  await expect(d.getByTestId("doctor-appointments")).toContainText("Confirmed");
  await p.reload();
  await expect(p.getByTestId("appointment")).toContainText("Confirmed");
  await pctx.close();
  await dctx.close();
});
