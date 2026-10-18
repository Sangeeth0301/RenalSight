/** One-click sharing helpers: wa.me deep links work on phones and WhatsApp Web, and let the person pick any contact or group. */
export const normalizePhone = (p: string, cc = "91") => {
  const d = p.replace(/\D/g, "");
  return d.length === 10 ? cc + d : d;
};
export const waLink = (text: string, phone?: string) => `https://wa.me/${phone ? normalizePhone(phone) : ""}?text=${encodeURIComponent(text)}`;
export const tgLink = (text: string) => `https://t.me/share/url?url=%20&text=${encodeURIComponent(text)}`;
export const smsLink = (text: string, phone?: string) => `sms:${phone ? "+" + normalizePhone(phone) : ""}?body=${encodeURIComponent(text)}`;
export const mailLink = (text: string) => `mailto:?subject=${encodeURIComponent("Kind request: kidney donor needed")}&body=${encodeURIComponent(text)}`;

export interface Contact { id: string; name: string; phone: string; sent?: boolean }
const KEY = "renalsight_contacts_v1";
/** Contacts stay in this browser only; nothing is uploaded to the server. */
export function loadContacts(): Contact[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; }
}
export function saveContacts(c: Contact[]) {
  try { localStorage.setItem(KEY, JSON.stringify(c.slice(0, 300))); } catch { /* ignore */ }
}
/** Accepts "Name, number" or "Name number" lines or bare numbers. */
export function parseContacts(raw: string): Contact[] {
  return raw.split(/\n|;/).map((l) => l.trim()).filter(Boolean).map((l, i) => {
    const m = l.match(/(\+?[\d][\d\s-]{6,})/);
    const phone = m ? m[1].replace(/[\s-]/g, "") : "";
    const name = l.replace(m ? m[1] : "", "").replace(/[,:-]+$/g, "").replace(/^[,:-]+/g, "").trim() || phone;
    return phone ? { id: `${Date.now()}-${i}`, name, phone } : null;
  }).filter(Boolean) as Contact[];
}
