import { expect, test } from "@playwright/test";
import { addLab, profile, register } from "./helpers";

// Needs the production build served on :4173 (npm run build && npm run preview): service workers are registered only in production.
test.use({ baseURL: "http://127.0.0.1:4173" });

test("the app opens offline and shows the last saved kidney information", async ({ browser, request }) => {
  const a = await register(request, "patient", "Offline Pat");
  await profile(request, a);
  await addLab(request, a);
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
  await ctx.addInitScript(([t, l]) => { localStorage.setItem("renalsight_token", t as string); localStorage.setItem("renalsight_lang", l as string); }, [a.token, "en"]);
  const page = await ctx.newPage();
  await page.goto("/kidney");
  await expect(page.getByTestId("stage-chip")).toBeVisible();
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await page.reload();                                         // now controlled by the service worker; API responses get cached
  await expect(page.getByTestId("stage-chip")).toBeVisible();

  await ctx.setOffline(true);
  await page.reload();
  await expect(page.getByTestId("stage-chip")).toBeVisible({ timeout: 15_000 });    // served from the cache
  await expect(page.getByRole("heading", { name: "Your living kidney" })).toBeVisible();
  await ctx.setOffline(false);

  // logging out clears the cached personal data
  await page.getByTestId("logout").click();
  const cached = await page.evaluate(async () => (await caches.keys()).includes("rs-api-v1"));
  expect(cached).toBe(false);
  await ctx.close();
});
