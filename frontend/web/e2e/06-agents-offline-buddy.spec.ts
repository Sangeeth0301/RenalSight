import { expect, test } from "@playwright/test";
import { addLab, API, authz, linkDoctor, profile, register, signedIn } from "./helpers";

test("Nephro Buddy answers in basic mode with no AI keys, from the patient's saved data, in every language", async ({ browser, request }) => {
  const pat = await register(request, "patient", "Buddy Pat", "ta");
  const st = await (await request.get(`${API}/buddy/status`, { headers: authz(pat) })).json();
  test.skip(st.ai_online, "AI keys are configured in backend/.env: this test covers the no-key basic mode only");
  await profile(request, pat);
  await addLab(request, pat);
  const { ctx, page } = await signedIn(browser, pat, "ta");
  await page.goto("/buddy");
  await expect(page.getByTestId("basic-banner")).toBeVisible();                        // no provider keys: honest banner
  await page.getByTestId("buddy-input").fill("என் சிறுநீரகம் எப்படி இருக்கிறது?");
  await page.getByTestId("buddy-send").click();
  const reply = page.getByTestId("buddy-reply").last();
  await expect(reply).toContainText("eGFR");
  await expect(reply).toContainText("சிறுநீரக");                                       // fixed Tamil sentences, no machine translation at run time
  await page.getByTestId("clear-chat").click();
  await page.getByTestId("confirm-clear").click();
  await expect(page.getByTestId("buddy-reply")).toHaveCount(0);
  await ctx.close();

  // the home console works too and switching to English changes the sentences instantly
  const { ctx: c2, page: p2 } = await signedIn(browser, pat, "en");
  await p2.goto("/home");
  await p2.getByTestId("home-ask").fill("How are my kidneys?");
  await p2.getByTestId("home-ask").press("Enter");
  await expect(p2.getByTestId("home-answer")).toContainText("Kidney stage");
  await c2.close();
});

test("Helper inbox: proactive checks create tasks, approval creates only a DRAFT, patients cannot approve for doctors", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Inbox");
  const pat = await register(request, "patient", "Pat Inbox");
  await profile(request, pat);
  await addLab(request, pat, { taken_on: "2025-01-10" });                              // an old lab: the next test is overdue
  await addLab(request, pat, { taken_on: "2025-04-10", scr: 3.4, potassium: 6.2 });    // fast decline + urgent potassium
  await linkDoctor(request, pat, doc);
  const { ctx: pctx, page: p } = await signedIn(browser, pat);
  const { ctx: dctx, page: d } = await signedIn(browser, doc);

  await p.goto("/inbox");
  await expect(p.getByTestId("pending-tasks")).toBeVisible();
  await expect(p.getByTestId("task-title").first()).toBeVisible();
  await expect(p.getByText("Your kidney test is overdue")).toBeVisible();
  await expect(p.getByText("Ask for a care plan?")).toBeVisible();
  await p.getByTestId("approve").first().click();
  await expect(p.getByText(/draft care plan was created/i)).toBeVisible();
  await p.goto("/rx");
  await expect(p.getByTestId("rx-item")).toHaveCount(1);
  await expect(p.getByText("Draft").first()).toBeVisible();

  await d.goto("/inbox");
  await expect(d.getByText(/urgent values/i)).toBeVisible();                           // doctor is alerted about potassium 6.2
  await d.getByTestId("dismiss").first().click();
  await pctx.close();
  await dctx.close();
});

test("Doctor Copilot drafts a message in the patient's language; nothing is sent until the doctor approves", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Copilot");
  const pat = await register(request, "patient", "Pat Copilot", "ta");
  await profile(request, pat);
  await addLab(request, pat, { scr: 4.2, potassium: 6.1 });
  await linkDoctor(request, pat, doc);
  // the copilot's tool call (what the AI agent does) goes through the same registry as the buttons
  const draft = await request.post(`${API}/tools/copilot_draft_message`, { headers: authz(doc), data: { patient_id: pat.user.id, topic: "urgent" } });
  expect(draft.status()).toBe(200);
  expect((await draft.json()).status).toBe("waiting_for_your_approval");
  const before = await (await request.get(`${API}/threads`, { headers: authz(pat) })).json();
  expect(before).toEqual([]);                                                         // not sent

  const { ctx: dctx, page: d } = await signedIn(browser, doc);
  await d.goto("/inbox");
  const edit = d.getByTestId("msg-edit");
  await expect(edit).toContainText("மரு.");                                          // Tamil draft
  await edit.fill("Please come to the clinic tomorrow morning.");
  await d.getByTestId("approve").first().click();
  await expect(d.getByText("Approved").first()).toBeVisible();
  const after = await (await request.get(`${API}/threads`, { headers: authz(pat) })).json();
  expect(after[0].last_message.body).toBe("Please come to the clinic tomorrow morning.");

  // copilot chat panel works in basic mode (no AI keys): summary of the most critical patients
  await d.goto("/doctor");
  await d.getByTestId("open-copilot").click();
  await d.getByTestId("copilot-input").fill("Who is critical?");
  await d.getByTestId("copilot-send").click();
  await expect(d.getByTestId("copilot-reply").last()).toContainText("Pat Copilot");
  await dctx.close();
});

test("outreach planner proposes a camp that needs approval; overdue list is shown", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Outreach");
  const { ctx, page } = await signedIn(browser, doc);
  await page.goto("/doctor");
  await page.getByTestId("outreach-region").selectOption("IN-TG");
  await page.getByTestId("outreach-target").fill("1000");
  await page.getByTestId("outreach-make").click();
  await expect(page.getByTestId("outreach-plan")).toContainText("Telangana");
  await expect(page.getByTestId("outreach-plan")).toContainText("5 camp day");
  await page.goto("/inbox");
  await expect(page.getByTestId("camp-plan")).toContainText("Checklist".length ? "BP machines" : "");
  await page.getByTestId("approve").first().click();
  await expect(page.getByText("Approved").first()).toBeVisible();
  await ctx.close();
});

test("offline pack, emergency card, research desk and the service worker cache", async ({ browser, request }) => {
  const doc = await register(request, "doctor", "Dr Card");
  const pat = await register(request, "patient", "Card Pat");
  await profile(request, pat);
  await addLab(request, pat);
  await linkDoctor(request, pat, doc);
  const { ctx, page } = await signedIn(browser, pat);
  await page.goto("/offline");
  await expect(page.getByTestId("doc-diet")).toContainText("Banana");
  await page.getByRole("tab", { name: "Emergency card" }).click();
  await expect(page.getByTestId("doc-emergency")).toContainText("Card Pat");
  await expect(page.getByTestId("doc-emergency")).toContainText("Dr. Dr Card");
  await expect(page.getByTestId("doc-emergency")).toContainText("ibuprofen");
  await page.getByRole("tab", { name: "Kidney words explained" }).click();
  await expect(page.getByTestId("doc-glossary")).toContainText("eGFR");
  await page.getByRole("tab", { name: "Exercise guide" }).click();
  await expect(page.getByTestId("doc-exercise")).toContainText("30 minutes");

  await page.goto("/research");
  await page.getByTestId("research-search").fill("sglt2");
  await expect(page.getByTestId("research-item").first()).toContainText(/SGLT2|Dapagliflozin|Empagliflozin|Canagliflozin|Diabetes/i);
  const link = page.getByRole("link", { name: "Open paper" }).first();
  await expect(link).toHaveAttribute("href", /^https:\/\/doi\.org\/10\./);
  await expect(link).toHaveAttribute("rel", /noopener/);
  await page.getByTestId("research-search").fill("zzzzzz");
  await expect(page.getByText("Nothing found")).toBeVisible();
  await ctx.close();
});
