"use client";

/**
 * 24-Stunden-Zeiteingabe als zwei Zahlenfelder (HH + MM).
 * Umgeht das AM/PM-Problem von <input type="time"> in manchen Browsern.
 * value / onChange kompatibel mit dem "HH:MM"-Format des restlichen Codes.
 */
interface TimeInputProps {
  value: string;          // "HH:MM"
  onChange: (v: string) => void;
  className?: string;
  disabled?: boolean;
}

export function TimeInput({ value, onChange, className = "", disabled }: TimeInputProps) {
  const [hh, mm] = (value || "").split(":").map((p) => p ?? "");

  function setHH(raw: string) {
    const n = Math.min(23, Math.max(0, parseInt(raw, 10) || 0));
    onChange(`${String(n).padStart(2, "0")}:${mm || "00"}`);
  }

  function setMM(raw: string) {
    const n = Math.min(59, Math.max(0, parseInt(raw, 10) || 0));
    onChange(`${hh || "00"}:${String(n).padStart(2, "0")}`);
  }

  const base =
    "w-14 text-center px-1 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <div className={`flex items-center gap-1 ${className}`}>
      <input
        type="number"
        min={0}
        max={23}
        value={hh || ""}
        onChange={(e) => setHH(e.target.value)}
        placeholder="HH"
        disabled={disabled}
        className={base}
      />
      <span className="text-muted-foreground font-medium select-none">:</span>
      <input
        type="number"
        min={0}
        max={59}
        value={mm || ""}
        onChange={(e) => setMM(e.target.value)}
        placeholder="MM"
        disabled={disabled}
        className={base}
      />
    </div>
  );
}
