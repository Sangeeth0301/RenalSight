import QRCode from "qrcode";
import { useEffect, useState } from "react";

export function QR({ value, size = 168, className }: { value: string; size?: number; className?: string }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let live = true;
    QRCode.toDataURL(value, { width: size * 2, margin: 1, color: { dark: "#0f172a", light: "#ffffff" } }).then((u) => { if (live) setSrc(u); }).catch(() => setSrc(""));
    return () => { live = false; };
  }, [value, size]);
  return src ? <img src={src} width={size} height={size} alt="QR code" className={className} style={{ borderRadius: 12, background: "#fff", padding: 4 }} /> : <div style={{ width: size, height: size }} className="skeleton" />;
}
