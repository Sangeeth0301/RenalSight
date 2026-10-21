import type { ReactNode } from "react";

/** Minimal markdown for AI answers: **bold**, bullet lists and paragraphs (tables and headings are flattened to plain lines). */
export function Rich({ text }: { text: string }) {
  const lines = text
    .split("\n")
    .filter((l) => !/^\s*\|?[-:| ]{3,}\|?\s*$/.test(l))                                                   // table divider rows
    .map((l) => (l.trim().startsWith("|") ? l.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map((c) => c.trim()).join(" - ") : l.replace(/^#{1,6}\s+/, "")));
  const out: ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => { if (bullets.length) { out.push(<ul key={`u${out.length}`} className="my-1 list-disc space-y-0.5 pl-5">{bullets.map((b, i) => <li key={i}>{inline(b)}</li>)}</ul>); bullets = []; } };
  const inline = (s: string): ReactNode[] => s.split(/(\*\*[^*]+\*\*)/g).map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>));
  lines.forEach((l, i) => {
    if (/^\s*[-*•]\s+/.test(l)) bullets.push(l.replace(/^\s*[-*•]\s+/, ""));
    else { flush(); out.push(l.trim() ? <p key={i} className="my-1">{inline(l)}</p> : <div key={i} className="h-1" />); }
  });
  flush();
  return <>{out}</>;
}

