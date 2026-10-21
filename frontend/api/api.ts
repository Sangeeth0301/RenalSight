/**
 * RenalSight API client (typed).
 * Backend: FastAPI on http://localhost:8000.  Set VITE_API_URL to change it.
 * No hosted back end: every request goes to our own server.
 */

// In a GitHub Codespace the page is served from https://<name>-5173.app.github.dev, so the API is reached through the Vite proxy at /api (same origin).
const inCodespace = typeof location !== "undefined" && /\.app\.github\.dev$/.test(location.hostname);
export const API_URL: string = (import.meta as any).env?.VITE_API_URL ?? (inCodespace ? `${location.origin}/api` : "http://localhost:8000");
export const WS_URL: string = API_URL.replace(/^http/, "ws");

export type Lang = "en" | "ta" | "bn" | "te";
export type Role = "patient" | "doctor" | "caregiver" | "admin";
export type Sex = "male" | "female";

// ------------------------------------------------------------------ errors + token
export class ApiError extends Error {
  constructor(public status: number, public detail: any) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}

const TOKEN_KEY = "renalsight_token";
let memoryToken: string | null = null;
export const auth = {
  get token(): string | null {
    try { return memoryToken ?? localStorage.getItem(TOKEN_KEY); } catch { return memoryToken; }
  },
  set(token: string | null) {
    memoryToken = token;
    try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ }
  },
};

type Query = Record<string, string | number | boolean | null | undefined>;

async function request<T>(method: string, path: string, body?: unknown, query?: Query, signal?: AbortSignal): Promise<T> {
  const url = new URL(API_URL + path);
  Object.entries(query ?? {}).forEach(([k, v]) => v !== undefined && v !== null && url.searchParams.set(k, String(v)));
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth.token) headers["Authorization"] = `Bearer ${auth.token}`;
  let res: Response;
  try {
    res = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal });
  } catch (e) {
    throw new ApiError(0, "network");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    if (res.status === 401) auth.set(null);               // expired token: the app should route to sign-in
    throw new ApiError(res.status, data?.detail ?? data ?? res.statusText);
  }
  return data as T;
}
const safeJson = (t: string) => { try { return JSON.parse(t); } catch { return t; } };
const get = <T>(p: string, q?: Query, s?: AbortSignal) => request<T>("GET", p, undefined, q, s);
const post = <T>(p: string, b?: unknown) => request<T>("POST", p, b ?? {});
const put = <T>(p: string, b?: unknown) => request<T>("PUT", p, b ?? {});
const patch = <T>(p: string, b?: unknown) => request<T>("PATCH", p, b ?? {});
const del = <T>(p: string) => request<T>("DELETE", p);

/** Files that need the Authorization header (PDF / printable page): fetch as a blob, then open it. */
export async function openProtected(path: string, query?: Query) {
  const url = new URL(API_URL + path);
  Object.entries(query ?? {}).forEach(([k, v]) => v != null && url.searchParams.set(k, String(v)));
  const res = await fetch(url, { headers: auth.token ? { Authorization: `Bearer ${auth.token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  const blob = await res.blob();
  window.open(URL.createObjectURL(blob), "_blank");
}

export async function downloadProtected(path: string, filename: string, query?: Query) {
  const url = new URL(API_URL + path);
  Object.entries(query ?? {}).forEach(([k, v]) => v != null && url.searchParams.set(k, String(v)));
  const res = await fetch(url, { headers: auth.token ? { Authorization: `Bearer ${auth.token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await res.blob());
  a.download = filename;
  a.click();
}

// ------------------------------------------------------------------ helpers / types for later modules
async function postForm<T>(path: string, form: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  if (auth.token) headers["Authorization"] = `Bearer ${auth.token}`;
  let res: Response;
  try { res = await fetch(API_URL + path, { method: "POST", headers, body: form }); } catch { throw new ApiError(0, "network"); }
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) { if (res.status === 401) auth.set(null); throw new ApiError(res.status, data?.detail ?? data ?? res.statusText); }
  return data as T;
}

export type RitualKind = "med_morning" | "med_noon" | "med_night" | "water" | "low_salt" | "bp" | "symptoms";
export interface RitualToday { day: string; entries: Partial<Record<RitualKind, any>>; score: number; streak: number; medicine_adherence_7d: number; urgent_symptoms: string[]; urgent_bp: boolean; water_target: number }
export interface RitualSummary { days: { day: string; score: number; meds_taken: number; water: number; low_salt: boolean; bp: { sbp: number; dbp: number } | null }[]; streak: number; medicine_adherence_7d: number; average_score_7d: number }
export interface Channel { id: number; slug: string; name: string; description: string; posts: number }
export interface Post { id: number; channel_id: number; user_id: number; author: string; author_role: Role | null; body: string; created_at: string; mine: boolean; reports: number | null; hidden?: boolean }
export type ProviderKind = "nephrologist" | "dialysis" | "lab" | "pharmacy";
export interface Provider { id: number; kind: ProviderKind; name: string; region: string; city: string; phone: string; languages: Lang[]; services: string; min_stage: number; is_demo: boolean; fit: number | null }
export interface Appointment { id: number; starts_at: string; status: "requested" | "confirmed" | "cancelled"; note: string; patient: { id: number; name: string }; provider: Provider | null; doctor: { id: number; name: string } | null }
export interface CareOverview { specialists_matched: number; appointments_upcoming: number; prescriptions_pending: number; adherence_7d: number; stage: number | null }
export interface ResearchItem { id: string; title: string; source: string; year: number; type: string; doi: string; url: string; tags: string[]; summary: string }
export interface EmergencyCard { name: string; age: number | null; sex: Sex | null; diabetes: boolean; hypertension: boolean; g_stage: string | null; a_category: string | null; egfr: number | null; potassium: number | null; as_of: string | null; doctor: { name: string; code: string | null } | null; medicines: { name: string; dose_mg: number | null; times_per_day: number | null }[]; warning_codes: string[]; avoid: string[]; note: string }
export interface ParsedReport { values: Partial<Record<"scr" | "bun" | "potassium" | "hgb" | "hba1c" | "acr" | "sbp" | "dbp", number>>; matched: { field: string; value: number; raw: string; unit: string; note: string | null }[]; taken_on: string | null; ocr_used: boolean; note: string; message?: string }
export interface AgentTask { id: number; agent: string; kind: string; title: string; body: string; payload: Record<string, any>; requires_approval: boolean; status: "pending" | "approved" | "rejected" | "done"; created_at: string; decided_at: string | null }
export interface CampPlan { region: string; region_name: string; target_people: number; camp_days: number; expected_with_kidney_disease: number; adults_with_diabetes_to_test_each_year_in_region: number; checklist: string[]; assumptions: string[] }

// ------------------------------------------------------------------ types
export interface User { id: number; email: string; name: string; role: Role; language: Lang; birth_year: number | null; age: number | null; sex: Sex | null; diabetes: boolean; hypertension: boolean; doctor_code: string | null; doctor_id: number | null }
export interface AuthResult { access_token: string; token_type: "bearer"; user: User }
export interface Lab { id: number; taken_on: string; scr: number | null; acr: number | null; sbp: number | null; dbp: number | null; hba1c: number | null; hgb: number | null; potassium: number | null; bun: number | null; egfr: number | null; g_stage: string | null; source: string; warning?: string }
export type LabInput = Partial<Pick<Lab, "scr" | "acr" | "sbp" | "dbp" | "hba1c" | "hgb" | "potassium" | "bun">> & { taken_on?: string };
export interface Wound { code: "cracks" | "leak" | "veins" | "pallor" | "flicker"; level: number; cause: "low_egfr" | "albuminuria" | "high_bp" | "anaemia" | "high_potassium"; value: number | null }
export interface KidneyState { has_data: boolean; message?: string; g_stage: string; a_category: string | null; visual_stage: 1 | 2 | 3 | 4 | 5; stage_name: "healthy" | "stressed" | "scarred" | "wounded" | "destroyed"; severity: number; theme: "healthy" | "watch" | "critical"; shrink: number; pulse: "calm" | "slow" | "irregular" | "flatline"; wounds: Wound[]; urgent: boolean; as_of?: string; egfr?: number }
export interface Forecast {
  has_data?: boolean; message?: string; current_egfr: number; slope_mean: number; slope_sd: number; years: number[]; egfr_p10: number[]; egfr_p50: number[]; egfr_p90: number[];
  years_to_stage5_p10: number | null; years_to_stage5_p50: number | null; years_to_stage5_p90: number | null; prob_kf_2y: number; prob_kf_5y: number; prob_kf_10y: number;
  already_stage5: boolean; note: string; scenario: "no_change" | "good_care"; assumptions: string[]; kfre_cross_check: { risk_2y: number; risk_5y: number } | null; labs_used?: number; uses_own_trend?: boolean;
}
export interface ForecastInput { age: number; sex: Sex; egfr: number; diabetes?: boolean; sbp?: number | null; hba1c?: number | null; acr?: number | null; history?: { month: number; egfr: number }[]; scenario?: "no_change" | "good_care"; horizon_years?: number }
export interface Survival { survival_1y: number; survival_3y: number; survival_5y: number; assumptions: string[]; note: string }
export interface PredictCkdInput { age: number; bp?: number; al?: number; su?: number; bgr?: number; bu?: number; sc?: number; hemo?: number; htn?: boolean; dm?: boolean; cad?: boolean; appet_poor?: boolean; pe?: boolean; ane?: boolean }
export interface PredictCkd { probability_ckd: number; risk_level: "low" | "moderate" | "high"; inputs_given: number; inputs_total: number; top_drivers: { feature: string; pushes: string; strength: number }[]; note: string }
export interface CarePlanItem { code: string; text_en: string; params: Record<string, number | string> }
export interface CarePlan { has_data: boolean; message?: string; stage?: string; a_category?: string | null; sections?: Record<string, CarePlanItem[]>; disclaimer?: string }
export interface RxItem { id?: number; drug_key: string; drug_name: string; dose_mg: number | null; times_per_day: number | null; duration_days: number | null; instructions: string | null; reason: string | null; suggested_by_system?: boolean }
export interface PatientRxItem { label: string; status: "awaiting_doctor" }
export interface SafetyWarning { severity: "block" | "warn" | "info"; code: string; text_en: string; drug: string | null }
export interface Safety { ok_to_sign: boolean; blocking: number; warnings: SafetyWarning[]; checked_items: number; egfr_used: number | null; note: string }
export interface Rx {
  id: number; status: "draft" | "submitted" | "signed" | "rejected"; patient: { id: number; name: string }; doctor: { id: number; name: string } | null; created_at: string; submitted_at: string | null; signed_at: string | null;
  supersedes_id: number | null; care_plan: CarePlan; disclaimer: string; items: (RxItem | PatientRxItem)[]; message?: string;
  // doctor view only
  doctor_notes?: string | null; safety?: Safety; snapshot?: Record<string, any>; override_reason?: string | null; reject_reason?: string | null;
}
export interface DoctorPatient { id: number; name: string; age: number | null; sex: Sex | null; diabetes: boolean; hypertension: boolean; email: string; language: Lang; trend: number[]; last_lab: string | null; labs_count: number; slope_per_year: number | null; state: Partial<KidneyState> & { has_data: boolean } }
export interface Notification { id: number; kind: "rx_submitted" | "rx_signed" | "rx_rejected" | "patient_linked" | "message"; title: string; body: string; payload: Record<string, any>; read: boolean; created_at: string }
export interface ThreadMember { id: number; name: string; role: Role; online: boolean }
export interface Message { id: number; thread_id: number; sender_id: number | null; sender_name: string | null; kind: "text" | "attachment" | "system"; body: string; attachment: any | null; created_at: string; client_id?: string | null }
export interface Thread { id: number; kind: "direct" | "room"; title: string; members: ThreadMember[]; last_message: Message | null; unread: number; code?: string; code_expires_at?: string | null }
export type AttachmentInput = { type: "kidney_snapshot" } | { type: "lab"; id: number } | { type: "prescription"; id: number };
export interface RoomTask { id: number; text: string; done: boolean; created_by: number }
export interface BuddyReply { reply: string; provider: string; language: Lang; ai_online: boolean; tools_used: { tool: string; ok: boolean; error?: string }[]; dose_removed: boolean }
export interface PopRegion { code: string; name: string; level: "country" | "state"; population_share_2011: number; has_reported_mortality: boolean; rate_differs_from_national: boolean }
export interface PopEstimate {
  region: string; region_name: string; year: number; scope: string; adults: number; ckd_cases: number; ckd_cases_high_alt: number; prevalence_pct: number; prevalence_pct_high_alt: number;
  stages: Record<"G1" | "G2" | "G3a" | "G3b" | "G4" | "G5", number>; by_age: { age_group: string; cases: number; prevalence_pct: number | null }[];
  needs: Record<string, number>; capacity_gap: null | { year_of_capacity_data: number; dialysis_stations: null | { have: number; need: number; gap: number }; nephrologists: null | { have: number; need: number; gap: number }; source: string };
  reported_ckd_mortality_per_lakh_2023: number | null; scenario: { annual_change_pct: number; dialysis_fraction_of_stage5: number }; meaning: Record<string, string>; assumptions: string[]; sources: string[]; limitations: string;
}
export interface LlmStatus { provider: string; state: "ready" | "cooldown" | "not_configured" | "always_available"; configured: boolean; model?: string; successes?: number; failures?: number; last_error?: string | null; cooldown_seconds_left?: number }

// ------------------------------------------------------------------ transplant hub
export type Tone = "warm" | "formal" | "urgent";
export interface Hospital { id: number; name: string; short_name: string; city: string; state: string; country: string; kind: string; transplant: boolean; phone: string; verified: boolean; note: string }
export interface SeatBoard { hospitals: (Hospital & { seats: Record<string, { total: number; free: number }>; free_total: number })[]; note: string }
export interface ShareLinks { whatsapp: string; telegram: string; sms: string; email: string; chars: number }
export interface Composed { text: string; written_by: "template" | "ai"; language: Lang; tone: Tone; links: ShareLinks; compatible_groups: string[]; tips: string[] }
export interface ComposeInput { hospital: string; patient_name: string; blood_group: string; contact_name?: string; contact_phone?: string; city?: string; age?: number | null; relation?: string; tone?: Tone; language?: Lang; include_phone?: boolean; extra?: string; link?: string; polish?: boolean; send_to?: string }
export interface OrganRequest { id?: number; token: string; hospital_id: number | null; hospital_name: string; patient_name: string; blood_group: string; organ: "kidney" | "liver"; age: number | null; city: string; relation: string; story: string; urgency: "routine" | "soon" | "urgent"; status: "open" | "matched" | "fulfilled" | "closed"; verified: boolean; created_at: string; compatible_groups: string[]; contact_name: string; contact_phone: string; offers?: number }
export interface DonorMatch { pledge_id: number; name: string; blood_group: string; city: string; score: number; can_message: boolean; phone: string; identical_abo: boolean }
export interface DonorOfferRow { id: number; name: string; blood_group: string; phone: string; note: string; compatible: boolean; status: string; created_at: string }
export interface RequestDetail extends OrganRequest { offer_list: DonorOfferRow[]; matches: DonorMatch[] }
export interface RequestInput { hospital_name: string; hospital_id?: number | null; patient_name: string; blood_group: string; organ?: "kidney" | "liver"; age?: number | null; city?: string; contact_name?: string; contact_phone: string; relation?: string; story?: string; urgency?: "routine" | "soon" | "urgent" }
export interface Pledge { id: number; name: string; blood_group: string; city: string; phone: string; kind: "living" | "deceased" | "both"; organs: string[]; family_informed: boolean; consent: boolean; created_at: string; note?: string }
export interface PledgeInput { name: string; blood_group: string; city?: string; phone?: string; kind: "living" | "deceased" | "both"; organs: string[]; family_informed?: boolean; consent: boolean }
export interface TransplantMeta { blood_groups: string[]; tones: Tone[]; relations: string[]; languages: Lang[]; organs_living: string[]; organs_deceased: string[]; journey: { key: string; title: string; body: string }[]; safety: string[] }
export interface Journey { steps: { key: string; title: string; body: string; done: boolean; note: string; done_at: string | null }[]; progress: number; next: string | null }
export interface DialysisRow { id: number; on_date: string; centre: string; pre_weight: number | null; post_weight: number | null; pre_bp: string; post_bp: string; hours: number | null; notes: string; removed_kg: number | null }
export interface IdCard { token: string; name: string; age: number | null; blood_group: string; allergies: string; stage: string | null; egfr: number | null; as_of: string | null; diabetes: boolean; hypertension: boolean; contact_name: string; contact_phone: string; public: boolean; warnings: string[] }

// ------------------------------------------------------------------ endpoints
export const api = {
  health: () => get<{ status: string; tools: number }>("/health"),

  // auth + profile
  register: (b: { email: string; password: string; name: string; role?: Exclude<Role, "admin">; language?: Lang }) => post<AuthResult>("/auth/register", b),
  login: (b: { email: string; password: string }) => post<AuthResult>("/auth/login", b),
  me: () => get<User>("/me"),
  updateProfile: (b: Partial<{ name: string; language: Lang; birth_year: number; sex: Sex; diabetes: boolean; hypertension: boolean }>) => put<User>("/me/profile", b),
  linkDoctor: (code: string) => post<{ doctor: { id: number; name: string } }>("/me/doctor", { code }),
  unlinkDoctor: () => del<void>("/me/doctor"),

  // labs
  labs: () => get<Lab[]>("/labs"),
  addLab: (b: LabInput) => post<Lab>("/labs", b),
  deleteLab: (id: number) => del<void>(`/labs/${id}`),

  // clinical
  myKidney: () => get<KidneyState>("/clinical/me/kidney-state"),
  myForecast: (scenario: "no_change" | "good_care" = "no_change", horizon_years = 15) => get<Forecast>("/clinical/me/forecast", { scenario, horizon_years }),
  kidneyState: (b: { egfr?: number; scr?: number; age?: number; sex?: Sex; acr?: number; sbp?: number; hgb?: number; potassium?: number }) => post<KidneyState>("/clinical/kidney-state", b),
  egfr: (b: { scr: number; age: number; sex: Sex }) => post<{ egfr: number; g_stage: string }>("/clinical/egfr", b),
  stage: (b: { egfr: number; acr?: number }) => post<{ g_stage: string; a_category: string | null; ckd_by_labs: boolean; note: string }>("/clinical/stage", b),
  predictCkd: (b: PredictCkdInput) => post<PredictCkd>("/clinical/predict-ckd", b),
  kfre: (b: { age: number; sex: Sex; egfr: number; acr: number }) => post<{ risk_2y: number; risk_5y: number; note: string }>("/clinical/kfre", b),
  forecast: (b: ForecastInput) => post<Forecast>("/clinical/forecast", b),
  whatIf: (b: { base: ForecastInput; sbp?: number; hba1c?: number; acr?: number; diabetes?: boolean }) => post<{ changes: Record<string, number | boolean>; baseline: Forecast; modified: Forecast; difference_years_median: number | null }>("/clinical/whatif", b),
  survival: (b: { age: number; sex: Sex; egfr: number; acr?: number; diabetes?: boolean; sbp?: number; hba1c?: number; hgb?: number }) => post<Survival>("/clinical/survival", b),

  // care plan and other tools are called through the tool registry
  tools: () => get<{ name: string; module: string; description: string; writes: boolean; input_schema: any }[]>("/tools"),
  callTool: <T = any>(name: string, args: Record<string, unknown> = {}) => post<T>(`/tools/${name}`, args),
  myCarePlan: () => post<CarePlan>("/tools/my_care_plan", {}),

  // prescriptions
  rxList: (status?: string) => get<Rx[]>("/rx", { status }),
  rx: (id: number) => get<Rx>(`/rx/${id}`),
  rxRequest: () => post<Rx>("/rx/request"),
  rxCreateForPatient: (patient_id: number) => post<Rx>("/rx", { patient_id }),
  rxSubmit: (id: number) => post<Rx>(`/rx/${id}/submit`),
  rxFormulary: () => get<Record<string, { name: string; class: string; typical: { dose_mg: number; times_per_day: number }; max_mg_day: number | null }>>("/rx/formulary"),
  rxSetItems: (id: number, items: Partial<RxItem>[]) => put<Rx>(`/rx/${id}/items`, { items }),
  rxSafety: (id: number) => post<Safety>(`/rx/${id}/safety-check`),
  /** 409 => ApiError.detail = { message, safety }: show the override dialog, then call again with override_reason */
  rxSign: (id: number, b: { notes?: string; override_reason?: string } = {}) => post<Rx>(`/rx/${id}/sign`, b),
  rxReject: (id: number, reason: string) => post<Rx>(`/rx/${id}/reject`, { reason }),
  rxRevise: (id: number) => post<Rx>(`/rx/${id}/revise`),
  rxOpenPdf: (id: number) => openProtected(`/rx/${id}/pdf`),
  rxOpenPrintable: (id: number, lang: Lang = "en") => openProtected(`/rx/${id}/print`, { lang }),

  // doctor portal
  doctorPatients: () => get<DoctorPatient[]>("/doctor/patients"),
  doctorPatient: (id: number) => get<{ patient: { id: number; name: string; age: number | null; sex: Sex | null }; snapshot: Record<string, any>; labs: Lab[]; state: KidneyState; forecast: Forecast }>(`/doctor/patients/${id}`),
  doctorQueue: () => get<Rx[]>("/doctor/queue"),

  // notifications
  notifications: (unread = false) => get<Notification[]>("/notifications", { unread }),
  markRead: (id: number) => post<Notification>(`/notifications/${id}/read`),
  markAllRead: () => post<{ ok: boolean }>("/notifications/read-all"),

  // direct line + rooms
  threads: () => get<Thread[]>("/threads"),
  openDirect: (user_id: number) => post<Thread>("/threads/direct", { user_id }),
  messages: (thread: number, before_id?: number, limit = 50) => get<Message[]>(`/threads/${thread}/messages`, { before_id, limit }),
  sendMessage: (thread: number, body: string, attachment?: AttachmentInput) => post<Message>(`/threads/${thread}/messages`, { body, attachment }),
  markThreadRead: (thread: number, up_to: number) => post<{ last_read_id: number }>(`/threads/${thread}/read`, { up_to }),
  createRoom: (title: string) => post<Thread>("/rooms", { title }),
  joinRoom: (code: string) => post<Thread>("/rooms/join", { code }),
  newRoomCode: (id: number) => post<Thread>(`/rooms/${id}/code`),
  leaveRoom: (id: number) => post<void>(`/rooms/${id}/leave`),
  closeRoom: (id: number) => del<void>(`/rooms/${id}`),
  roomTasks: (id: number) => get<RoomTask[]>(`/rooms/${id}/tasks`),
  addRoomTask: (id: number, text: string) => post<RoomTask>(`/rooms/${id}/tasks`, { text }),
  setRoomTask: (id: number, task: number, done: boolean) => patch<RoomTask>(`/rooms/${id}/tasks/${task}`, { done }),

  // AI helpers
  buddyChat: (message: string, language?: Lang) => post<BuddyReply>("/buddy/chat", { message, language }),
  buddyHistory: (limit = 30) => get<{ role: "user" | "assistant"; content: string; provider: string | null; at: string }[]>("/buddy/history", { limit }),
  clearBuddyHistory: () => del<void>("/buddy/history"),
  buddyStatus: () => get<{ ai_online: boolean }>("/buddy/status"),
  analystChat: (message: string, language?: Lang) => post<BuddyReply>("/analyst/chat", { message, language }),

  // population pulse (public)
  popRegions: () => get<{ regions: PopRegion[]; year_range: [number, number]; presets: Record<string, { annual_change_pct: number; label: string }>; defaults: Record<string, any> }>("/population/regions"),
  popEstimate: (q: { region?: string; year?: number; annual_change_pct?: number; dialysis_fraction?: number }) => get<PopEstimate>("/population/estimate", q),
  popSeries: (q: { region?: string; start?: number; end?: number; annual_change_pct?: number; dialysis_fraction?: number }) => get<{ region: string; region_name: string; series: { year: number; adults: number; ckd_cases: number; ckd_cases_high_alt: number; prevalence_pct: number; stage5_people: number; dialysis_stations_needed: number; nephrology_visits_per_year: number }[]; assumptions: string[]; sources: string[] }>("/population/timeseries", q),
  popCompare: (q: { region?: string; year?: number; dialysis_fraction?: number }) => get<{ region: string; year: number; scenarios: { scenario: string; label: string; annual_change_pct: number; ckd_cases: number; prevalence_pct: number; stage5_people: number; dialysis_stations_needed: number; cases_vs_current_trend: number }[]; note: string }>("/population/compare", q),
  popMap: (q: { year?: number; annual_change_pct?: number }) => get<{ year: number; regions: { region: string; name: string; ckd_cases: number; prevalence_pct: number; stage5_people: number; reported_mortality_per_lakh_2023: number | null }[]; note: string }>("/population/map", q),
  popSources: () => get<Record<string, any>>("/population/sources"),
  popSetCapacity: (b: { region: string; year: number; dialysis_stations?: number; nephrologists?: number; source: string }) => put<any>("/population/capacity", b),


  // daily rituals
  ritualsToday: () => get<RitualToday>("/rituals/today"),
  ritualLog: (b: { kind: RitualKind; day?: string; taken?: boolean; glasses?: number; done?: boolean; sbp?: number; dbp?: number; items?: string[] }) => post<RitualToday>("/rituals/log", b),
  ritualsSummary: (days = 14) => get<RitualSummary>("/rituals/summary", { days }),

  // community
  channels: () => get<Channel[]>("/channels"),
  channelPosts: (id: number, before_id?: number) => get<Post[]>(`/channels/${id}/posts`, { before_id }),
  addPost: (id: number, body: string) => post<Post>(`/channels/${id}/posts`, { body }),
  deletePost: (id: number) => del<void>(`/posts/${id}`),
  reportPost: (id: number, reason = "") => post<{ reports: number; hidden: boolean }>(`/posts/${id}/report`, { reason }),
  reportedPosts: () => get<Post[]>("/admin/reported-posts"),
  restorePost: (id: number) => post<{ ok: boolean }>(`/admin/posts/${id}/restore`),

  // care hub
  careProviders: (q: { kind?: ProviderKind; region?: string } = {}) => get<{ stage: number | null; providers: Provider[]; demo_note: string }>("/care-hub/providers", q),
  addProvider: (b: { kind: ProviderKind; name: string; region?: string; city?: string; phone?: string; languages?: Lang[]; services?: string; min_stage?: number }) => post<Provider>("/care-hub/providers", b),
  deleteProvider: (id: number) => del<void>(`/care-hub/providers/${id}`),
  careOverview: () => get<CareOverview>("/care-hub/overview"),
  appointments: () => get<Appointment[]>("/appointments"),
  bookAppointment: (b: { provider_id?: number; with_my_doctor?: boolean; starts_at: string; note?: string }) => post<Appointment>("/appointments", b),
  setAppointmentStatus: (id: number, status: "confirmed" | "cancelled") => post<Appointment>(`/appointments/${id}/status`, { status }),

  // research + offline
  researchSearch: (q: { q?: string; tag?: string; type?: string } = {}) => get<{ results: ResearchItem[]; total: number; tags: string[]; note: string }>("/research/search", q),
  emergencyCard: () => get<EmergencyCard>("/offline/emergency-card"),

  // lab report reading
  reportsCapabilities: () => get<{ text: boolean; csv: boolean; pdf_text: boolean; image_ocr: boolean; max_mb: number }>("/reports/capabilities"),
  reportSamples: (category: string, n = 1) => get<{ category: string; label: string; source: string; samples: { age: number; sex: "male" | "female"; diabetes: boolean; egfr: number; g_stage: string; scr: number; acr: number; sbp: number; dbp: number; hba1c: number; hgb: number; potassium: number; bun: number }[] }>("/reports/samples", { category, n }),
  reportsParseText: (text: string) => { const f = new FormData(); f.append("text", text); return postForm<ParsedReport>("/reports/parse", f); },
  reportsParseFile: (file: File) => { const f = new FormData(); f.append("file", file); return postForm<ParsedReport>("/reports/parse", f); },

  // helper inbox + agents
  inbox: (status?: string) => get<AgentTask[]>("/agents/inbox", { status }),
  agentsRefresh: () => post<{ created: Record<string, number>; patients_checked: number }>("/agents/refresh"),
  approveTask: (id: number, text?: string) => post<{ task: AgentTask; rx_id?: number; thread_id?: number }>(`/agents/tasks/${id}/approve`, text ? { text } : {}),
  rejectTask: (id: number) => post<AgentTask>(`/agents/tasks/${id}/reject`),
  dismissTask: (id: number) => post<AgentTask>(`/agents/tasks/${id}/dismiss`),
  copilotChat: (message: string, language?: Lang) => post<BuddyReply>("/copilot/chat", { message, language }),
  outreachChat: (message: string, language?: Lang) => post<BuddyReply>("/outreach/chat", { message, language }),
  outreachPlan: (b: { region: string; target_people?: number; people_per_camp_day?: number }) => post<{ task_id: number; status: string; plan: CampPlan }>("/tools/outreach_plan_camp", b),
  outreachOverdue: () => post<{ overdue: { patient_id: number; name: string; due: string; days_late: number; tests_per_year: number }[]; count: number }>("/tools/outreach_overdue_patients", {}),

  waStatus: () => get<{ linked: boolean; chrome_open: boolean; checked_at: string | null; login_window_open: boolean; node: boolean; note: string }>("/whatsapp/status"),
  waAllowed: () => get<{ allowed: string[] }>("/whatsapp/allowed"),
  waQr: async (): Promise<string | null> => {
    const res = await fetch(API_URL + "/whatsapp/qr", { headers: auth.token ? { Authorization: `Bearer ${auth.token}` } : {} });
    return res.ok ? URL.createObjectURL(await res.blob()) : null;
  },
  waLogin: () => post<{ started: boolean; message: string }>("/whatsapp/login"),
  waSend: (b: { text: string; recipients: { name: string }[] }) => post<{ job_id: string; recipients: string[] }>("/whatsapp/send", b),
  waJob: (id: string) => get<{ id: string; done: boolean; results: { name: string; ok: boolean; error?: string }[] }>(`/whatsapp/jobs/${id}`),
  translate: (texts: string[], target: Lang) => post<{ target: Lang; available: boolean; translations: string[]; translated: boolean[] }>("/translate", { texts, target }),

  // transplant hub
  txMeta: () => get<TransplantMeta>("/transplant/meta"),
  hospitals: (q: { q?: string; city?: string; transplant?: boolean; limit?: number } = {}) => get<Hospital[]>("/hospitals", q),
  seatBoard: (city?: string) => get<SeatBoard>("/dialysis/seats", { city }),
  setSeats: (id: number, b: { shift: string; total: number; free: number }) => put<Hospital>(`/hospitals/${id}/seats`, b),
  compose: (b: ComposeInput) => post<Composed>("/share/compose", b),
  requests: (all = false) => get<OrganRequest[]>("/requests", all ? { all: true } : undefined),
  createRequest: (b: RequestInput) => post<OrganRequest>("/requests", b),
  request: (id: number) => get<RequestDetail>(`/requests/${id}`),
  setRequestStatus: (id: number, status: string) => patch<OrganRequest>(`/requests/${id}/status`, { status }),
  verifyRequest: (id: number) => post<OrganRequest>(`/requests/${id}/verify`),
  composeForRequest: (id: number, b: { tone?: Tone; language?: Lang; include_phone?: boolean; polish?: boolean; send_to?: string; link?: string }) => post<Composed>(`/requests/${id}/compose`, b),
  contactDonor: (rid: number, pid: number) => post<{ ok: boolean }>(`/requests/${rid}/contact-donor/${pid}`),
  publicRequest: (token: string) => get<OrganRequest & { scam_warning: string }>(`/public/requests/${token}`),
  publicOffer: (token: string, b: { name: string; blood_group?: string; phone: string; note?: string; consent: boolean }) => post<{ ok: boolean; message: string; compatible_hint: boolean }>(`/public/requests/${token}/offers`, b),
  setOfferStatus: (id: number, status: string) => patch<{ ok: boolean }>(`/offers/${id}`, { status }),
  pledge: (b: PledgeInput) => post<Pledge>("/donors/pledge", b),
  myPledge: () => get<Pledge | null>("/donors/mine"),
  withdrawPledge: () => del<{ ok: boolean }>("/donors/mine"),
  donorStats: () => get<{ pledges: number; by_organ: Record<string, number>; by_blood_group: Record<string, number>; open_requests: number }>("/donors/stats"),
  compat: (blood_group: string) => get<{ recipient: string; donor_groups: string[]; note: string }>("/donors/compat", { blood_group }),
  journey: () => get<Journey>("/journey"),
  setStep: (key: string, b: { done: boolean; note?: string }) => put<Journey>(`/journey/${key}`, b),
  dialysis: () => get<{ sessions: DialysisRow[]; interdialytic_gain_kg: number[]; warning: string | null }>("/dialysis/sessions"),
  addDialysis: (b: Partial<DialysisRow> & { on_date: string }) => post<DialysisRow>("/dialysis/sessions", b),
  deleteDialysis: (id: number) => del<{ ok: boolean }>(`/dialysis/sessions/${id}`),
  idCard: () => get<IdCard>("/emergency-card"),
  saveIdCard: (b: { blood_group?: string; allergies?: string; contact_name?: string; contact_phone?: string; public?: boolean }) => put<IdCard>("/emergency-card", b),
  exportFhir: () => downloadProtected("/export/fhir", "renalsight-fhir.json"),
  openReferral: (to: string, reason: string) => openProtected("/export/referral.pdf", { to, reason }),
  publicIdCard: (token: string) => get<IdCard>(`/public/emergency/${token}`),

  // admin
  llmStatus: () => get<LlmStatus[]>("/admin/llm-status"),
};

// ------------------------------------------------------------------ WebSocket (Direct Line and rooms)
export type ServerEvent =
  | { type: "ready"; user_id: number; online: number[] }
  | { type: "message"; message: Message }
  | { type: "typing"; user_id: number }
  | { type: "read"; user_id: number; up_to: number }
  | { type: "presence"; user_id: number; online?: boolean; joined?: boolean; name?: string }
  | { type: "task"; task: RoomTask }
  | { type: "closed" }
  | { type: "pong" }
  | { type: "error"; detail: string };

/** Opens /ws/threads/{id}, sends the auth frame first (the token is never put in the URL) and reconnects with back-off. */
export function connectThread(threadId: number, onEvent: (e: ServerEvent) => void, onStatus?: (s: "connecting" | "open" | "closed") => void) {
  let ws: WebSocket | null = null;
  let stopped = false;
  let attempt = 0;
  const open = () => {
    onStatus?.("connecting");
    ws = new WebSocket(`${WS_URL}/ws/threads/${threadId}`);
    ws.onopen = () => { ws!.send(JSON.stringify({ type: "auth", token: auth.token })); attempt = 0; onStatus?.("open"); };
    ws.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch { /* ignore */ } };
    ws.onclose = (ev) => {
      onStatus?.("closed");
      if (stopped || ev.code === 4401 || ev.code === 4403) return;       // bad token / not a member: do not retry
      setTimeout(open, Math.min(1000 * 2 ** attempt++, 15000));
    };
  };
  open();
  const send = (data: object) => ws?.readyState === WebSocket.OPEN && ws.send(JSON.stringify(data));
  return {
    sendMessage: (body: string, attachment?: AttachmentInput, client_id?: string) => send({ type: "message", body, attachment, client_id }),
    typing: () => send({ type: "typing" }),
    read: (up_to: number) => send({ type: "read", up_to }),
    close: () => { stopped = true; ws?.close(); },
  };
}
