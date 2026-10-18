import { expect, test } from "@playwright/test";
import { PASSWORD, uniq } from "./helpers";

test("language popup opens on first visit and switches instantly without any network call", async ({ page }) => {
  const calls: string[] = [];
  page.on("request", (r) => { if (r.url().includes(":8000")) calls.push(r.url()); });
  await page.goto("/");
  await expect(page.getByTestId("language-dialog")).toBeVisible();
  await page.getByTestId("lang-ta").click();
  await expect(page.getByTestId("language-dialog")).toBeHidden();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("சிறுநீரகங்கள்");
  await expect(page.locator("html")).toHaveAttribute("lang", "ta");
  expect(calls).toEqual([]);                                   // switching never needs the API or a key

  // persists after reload, and the globe reopens the popup
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("சிறுநீரகங்கள்");
  await page.getByTestId("globe").click();
  await page.getByTestId("lang-te").click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("కిడ్నీ");
  await page.getByTestId("globe").click();
  await page.getByTestId("lang-bn").click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("কিডনি");
  await page.getByTestId("globe").click();
  await page.getByTestId("lang-en").click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("kidneys");
});

test("register -> onboarding -> home, then log out and sign in again", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("renalsight_lang", "en"));
  const email = `${uniq("ui")}@example.com`;
  await page.goto("/register");
  await page.getByTestId("name").fill("Test Patient");
  await page.getByTestId("email").fill(email);
  await page.getByTestId("password").fill("short");
  await page.getByTestId("submit").click();                      // browser validation blocks a short password
  await expect(page).toHaveURL(/register/);
  await page.getByTestId("password").fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page).toHaveURL(/onboarding/);

  await page.getByTestId("birth-year").fill("1960");
  await page.getByTestId("sex-female").click();
  await page.getByTestId("diabetes").check();
  await page.getByTestId("save-profile").click();
  await page.getByText("Skip for now").click();                  // doctor link is optional
  await page.getByTestId("finish").click();
  await expect(page).toHaveURL(/home/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Welcome, Test Patient");

  await page.getByTestId("logout").click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/home");
  await expect(page).toHaveURL(/login/);                          // protected route redirects

  await page.getByTestId("email").fill(email);
  await page.getByTestId("password").fill("wrong-password");
  await page.getByTestId("submit").click();
  await expect(page.getByText("Wrong email or password")).toBeVisible();
  await page.getByTestId("password").fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page).toHaveURL(/home/);
});

test("duplicate email is rejected with a clear message", async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem("renalsight_lang", "en"));
  const email = `${uniq("dup")}@example.com`;
  await request.post("http://127.0.0.1:8000/auth/register", { data: { email, password: PASSWORD, name: "A" } });
  await page.goto("/register");
  await page.getByTestId("name").fill("B");
  await page.getByTestId("email").fill(email);
  await page.getByTestId("password").fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByText("already registered")).toBeVisible();
});
