"use client";

/**
 * AvailabilityGrid – weekly availability editor
 *
 * Data format (matches backend availability_prefs JSON):
 *   { "0": { available: true, from_time: "08:00", to_time: "20:00", note: "" }, … }
 * Keys 0–6 correspond to Mon–Sun (Python weekday convention).
 */

export type DayPrefs = {
  available: boolean;
  from_time: string;
  to_time: string;
  note: string;
};

export type AvailabilityPrefs = Record<string, DayPrefs>;

const DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const DAY_LABELS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];

function defaultDay(available = true): DayPrefs {
  return { available, from_time: "08:00", to_time: "20:00", note: "" };
}

export function emptyAvailabilityPrefs(): AvailabilityPrefs {
  return Object.fromEntries(
    Array.from({ length: 7 }, (_, i) => [String(i), defaultDay(i < 5)])
  );
}

interface Props {
  value: AvailabilityPrefs | null;
  onChange: (v: AvailabilityPrefs) => void;
  readOnly?: boolean;
}

export function AvailabilityGrid({ value, onChange, readOnly = false }: Props) {
  const prefs: AvailabilityPrefs = value ?? emptyAvailabilityPrefs();

  function update(day: number, patch: Partial<DayPrefs>) {
    const current = prefs[String(day)] ?? defaultDay();
    onChange({ ...prefs, [String(day)]: { ...current, ...patch } });
  }

  const inputCls =
    "px-2 py-1 rounded-md border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-1 focus:ring-ring";

  return (
    <div className="space-y-1.5">
      {Array.from({ length: 7 }, (_, i) => {
        const day = prefs[String(i)] ?? defaultDay(i < 5);
        return (
          <div
            key={i}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 transition-colors ${
              day.available ? "bg-muted/40" : "bg-muted/20 opacity-60"
            }`}
          >
            {/* Day label */}
            <span className="w-7 text-xs font-semibold text-muted-foreground shrink-0">
              {DAY_NAMES[i]}
            </span>

            {/* Available toggle */}
            {!readOnly ? (
              <button
                type="button"
                onClick={() => update(i, { available: !day.available })}
                className={`shrink-0 w-8 h-4 rounded-full transition-colors relative ${
                  day.available
                    ? "bg-[rgb(var(--ctp-green))]"
                    : "bg-border"
                }`}
                title={DAY_LABELS[i]}
              >
                <span
                  className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                    day.available ? "translate-x-4" : "translate-x-0.5"
                  }`}
                />
              </button>
            ) : (
              <span
                className={`shrink-0 w-2 h-2 rounded-full ${
                  day.available ? "bg-[rgb(var(--ctp-green))]" : "bg-muted-foreground/30"
                }`}
              />
            )}

            {/* Status label + time range */}
            {day.available ? (
              <>
                <span className="text-xs text-green-600 dark:text-green-400 shrink-0 hidden sm:inline">
                  Verfügbar
                </span>
                {!readOnly ? (
                  <div className="flex items-center gap-1 ml-auto">
                    <input
                      type="time"
                      value={day.from_time}
                      onChange={(e) => update(i, { from_time: e.target.value })}
                      className={inputCls}
                    />
                    <span className="text-xs text-muted-foreground">–</span>
                    <input
                      type="time"
                      value={day.to_time}
                      onChange={(e) => update(i, { to_time: e.target.value })}
                      className={inputCls}
                    />
                  </div>
                ) : (
                  <span className="text-xs text-muted-foreground ml-auto">
                    {day.from_time} – {day.to_time}
                  </span>
                )}
              </>
            ) : (
              <span className="text-xs text-muted-foreground ml-2">Nicht verfügbar</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
