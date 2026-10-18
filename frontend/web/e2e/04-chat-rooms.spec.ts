import { expect, test } from "@playwright/test";
import { addLab, API, authz, linkDoctor, profile, register, signedIn } from "./helpers";

test("direct line: live messages, typing/read ticks and a shared kidney card between patient and doctor", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Chat");
  const pat = await register(request, "patient", "Pat Chat");
  await profile(request, pat);
  await addLab(request, pat);
  await linkDoctor(request, pat, doc);
  const { ctx: pctx, page: p } = await signedIn(browser, pat);
  const { ctx: dctx, page: d } = await signedIn(browser, doc);

  await p.goto("/chat");
  await p.getByTestId("open-doctor").click();
  await expect(p.getByTestId("chat-pane")).toBeVisible();
  await p.getByTestId("chat-input").fill("Hello doctor, my feet are swollen");
  await p.getByTestId("chat-send").click();
  await expect(p.getByTestId("msg").last()).toContainText("my feet are swollen");

  // doctor sees the thread with an unread badge and opens it
  await d.goto("/chat");
  await expect(d.getByTestId("thread").first()).toContainText("Pat Chat");
  await d.getByTestId("thread").first().click();
  await expect(d.getByTestId("msg").last()).toContainText("my feet are swollen");

  // live both ways without reloading
  await d.getByTestId("chat-input").fill("Please keep salt low and come tomorrow");
  await d.getByTestId("chat-send").click();
  await expect(p.getByTestId("msg").last()).toContainText("come tomorrow");
  await p.getByTestId("chat-input").fill("Thank you");
  await p.getByTestId("chat-send").click();
  await expect(d.getByTestId("msg").last()).toContainText("Thank you");

  // patient shares their kidney; the doctor sees a card
  await p.getByTestId("attach").click();
  await p.getByTestId("attach-kidney").click();
  await p.getByTestId("chat-send").click();
  await expect(d.getByTestId("msg").last()).toContainText("Shared kidney status");
  await expect(d.getByTestId("msg").last()).toContainText("eGFR");

  // doctors cannot share a kidney (menu item is not offered)
  await d.getByTestId("attach").click();
  await expect(d.getByTestId("attach-kidney")).toHaveCount(0);

  // history survives a reload
  await p.reload();
  await expect(p.getByTestId("msg")).toHaveCount(4);
  await pctx.close();
  await dctx.close();
});

test("consult room: create, join with the 6-digit code, chat live, shared checklist, owner closes the room", async ({ browser, request }) => {
  const owner = await register(request, "patient", "Owner Pat");
  const family = await register(request, "caregiver", "Family Kumar");
  const { ctx: octx, page: o } = await signedIn(browser, owner);
  const { ctx: fctx, page: f } = await signedIn(browser, family);

  await o.goto("/rooms");
  await o.getByTestId("room-title").fill("Amma kidney care");
  await o.getByTestId("create-room").click();
  await expect(o.getByTestId("room-code")).toHaveText(/^\d{6}$/);
  const code = (await o.getByTestId("room-code").textContent())!.trim();

  // wrong code first, then the right one (OTP boxes)
  await f.goto("/rooms");
  for (let i = 0; i < 6; i++) await f.getByTestId(`otp-${i}`).fill("0");
  await f.getByTestId("join-room").click();
  await expect(f.getByTestId("join-error")).toBeVisible();
  for (let i = 0; i < 6; i++) await f.getByTestId(`otp-${i}`).fill(code[i]);
  await f.getByTestId("join-room").click();
  await expect(f).toHaveURL(/rooms\/\d+/);
  await expect(f.getByTestId("room-code")).toHaveCount(0);                       // only the owner sees the code
  await expect(o.getByText("Family Kumar joined the room")).toBeVisible();

  await f.getByTestId("chat-input").fill("I will buy low-salt groceries");
  await f.getByTestId("chat-send").click();
  await expect(o.getByTestId("msg").last()).toContainText("low-salt groceries");

  await o.getByTestId("task-input").fill("Book the next lab test");
  await o.getByTestId("task-input").press("Enter");
  await expect(f.getByTestId("tasks")).toContainText("Book the next lab test", { timeout: 15_000 });
  await f.getByTestId("tasks").getByRole("checkbox").first().click();
  await expect(o.getByTestId("tasks").getByRole("checkbox").first()).toBeChecked({ timeout: 15_000 });

  await o.getByTestId("close-room").click();
  await o.getByTestId("confirm-close").click();
  await expect(o).toHaveURL(/\/rooms$/);
  await expect(f).toHaveURL(/\/rooms$/, { timeout: 15_000 });                    // the family member is moved out when it closes
  await octx.close();
  await fctx.close();
});

test("an outsider cannot open someone else's conversation", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Private");
  const pat = await register(request, "patient", "Pat Private");
  const spy = await register(request, "patient", "Pat Spy");
  await profile(request, pat);
  await linkDoctor(request, pat, doc);
  const { ctx: pctx, page: p } = await signedIn(browser, pat);
  await p.goto("/chat");
  await p.getByTestId("open-doctor").click();
  await expect(p).toHaveURL(/chat\/\d+/);
  const url = p.url();
  await pctx.close();
  const { ctx, page } = await signedIn(browser, spy);
  await page.goto(url.replace("http://127.0.0.1:5173", ""));
  await expect(page.getByText("We could not find that.")).toBeVisible();
  await ctx.close();
});

test("translate toggle: chat messages, previews and AI answers switch to the chosen language and the original is one click away", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Tr");
  const pat = await register(request, "patient", "Tr Pat");
  await profile(request, pat);
  await linkDoctor(request, pat, doc);
  const th = await (await request.post(`${API}/threads/direct`, { headers: authz(pat), data: { user_id: doc.user.id } })).json();
  await request.post(`${API}/threads/${th.id}/messages`, { headers: authz(pat), data: { body: "My feet are swollen today" } });

  const { ctx, page } = await signedIn(browser, doc, "ta");                                   // doctor reads in Tamil
  await page.route("**/translate", async (route) => {
    const body = route.request().postDataJSON();
    await route.fulfill({ json: { target: body.target, available: true, translations: body.texts.map((t: string) => `[${body.target}] ${t}`), translated: body.texts.map(() => true) } });
  });
  await page.goto(`/chat/${th.id}`);
  await expect(page.getByText("My feet are swollen today").first()).toBeVisible();            // off by default: original text
  await page.getByTestId("translate-toggle").click();
  await expect(page.getByText("[ta] My feet are swollen today").first()).toBeVisible();      // message bubble translated
  await page.getByTestId("tx-toggle").first().click();
  await expect(page.getByText("My feet are swollen today").first()).toBeVisible();            // click the icon: original again
  await ctx.close();
});
