import { useQuery } from "@tanstack/react-query";
import { Building2, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { api, type Hospital } from "@/lib/api";
import { useDebounced } from "./ui";

/** Type "AIIMS", "KMCH" or "Kolkata" and pick from the directory, or keep any hospital name you typed. */
export function HospitalPicker({ value, onChange, onPick, placeholder }: { value: string; onChange: (v: string) => void; onPick?: (h: Hospital) => void; placeholder?: string }) {
  const [open, setOpen] = useState(false);
  const q = useDebounced(value, 200);
  const res = useQuery({ queryKey: ["hospitals", q], queryFn: () => api.hospitals({ q, limit: 8 }), enabled: open && q.trim().length >= 2 });
  return (
    <div className="relative">
      <input className="input" value={value} placeholder={placeholder ?? "AIIMS, KMCH, Apollo Kolkata..."} data-testid="hospital-input" autoComplete="off"
        onChange={(e) => { onChange(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)} />
      {open && (res.data?.length ?? 0) > 0 && (
        <ul className="card absolute z-50 mt-1 max-h-72 w-full overflow-auto p-1" role="listbox">
          {res.data!.map((h) => (
            <li key={h.id}>
              <button type="button" role="option" aria-selected={false} className="flex w-full items-start gap-3 rounded-xl px-3 py-2 text-left hover:bg-[var(--surface-2)]"
                onMouseDown={(e) => { e.preventDefault(); onChange(h.name); onPick?.(h); setOpen(false); }}>
                <Building2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                <span className="min-w-0 flex-1"><span className="block truncate font-medium">{h.name}</span><span className="block text-xs text-muted">{[h.city, h.state, h.country].filter(Boolean).join(", ")}{h.transplant ? " · transplant programme" : ""}</span></span>
                {h.verified && <CheckCircle2 className="h-4 w-4 text-ok" />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
