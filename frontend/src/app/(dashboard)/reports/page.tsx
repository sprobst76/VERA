"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { employeesApi, shiftsApi, payrollApi, shiftTypesApi, reportsApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import {
  format, startOfMonth, endOfMonth, subMonths, addMonths, parseISO,
} from "date-fns";
import { de } from "date-fns/locale";
import {
  ChevronLeft, ChevronRight, Clock, AlertTriangle,
  CheckCircle2, TrendingUp, Download, Layers, CalendarOff,
} from "lucide-react";

// ── CSV helpers ───────────────────────────────────────────────────────────────

function downloadCsv(filename: string, rows: string[][]) {
  const bom = "\uFEFF"; // Excel-compatible UTF-8 BOM
  const content = bom + rows.map(r =>
    r.map(cell => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(";")
  ).join("\r\n");
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function calcShiftHours(start: string, end: string, breakMin: number): number {
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  let mins = eh * 60 + em - (sh * 60 + sm) - (breakMin || 0);
  if (mins < 0) mins += 24 * 60; // overnight
  return Math.max(0, mins / 60);
}

function fmtHours(h: number): string {
  if (h === 0) return "0h";
  const hours = Math.floor(h);
  const mins = Math.round((h - hours) * 60);
  return mins > 0 ? `${hours}h ${mins}min` : `${hours}h`;
}

function fmtEuro(n: number | null | undefined): string {
  if (n == null) return "–";
  return n.toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, icon: Icon, color, children }: {
  title: string; icon: React.ElementType; color: string; children: React.ReactNode;
}) {
  return (
    <div className="bg-card rounded-xl border border-border overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-4 border-b border-border">
        <Icon size={16} style={{ color: `rgb(var(${color}))` }} />
        <h2 className="font-semibold text-foreground">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

// ── 1. Stundenbericht ─────────────────────────────────────────────────────────

function HoursReport({ shifts, employees, isPrivileged, monthLabel }: {
  shifts: any[]; employees: any[]; isPrivileged: boolean; monthLabel: string;
}) {
  const empMap = useMemo(() =>
    Object.fromEntries(employees.map((e: any) => [e.id, e])),
    [employees]
  );

  // Group by employee_id
  const byEmployee = useMemo(() => {
    const map: Record<string, { planned: number; actual: number; count: number }> = {};
    for (const s of shifts) {
      if (s.status === "cancelled" || s.status === "cancelled_absence") continue;
      const id = s.employee_id ?? "__open__";
      if (!map[id]) map[id] = { planned: 0, actual: 0, count: 0 };
      map[id].count++;
      map[id].planned += calcShiftHours(s.start_time, s.end_time, s.break_minutes);
      if (s.actual_start && s.actual_end) {
        map[id].actual += calcShiftHours(s.actual_start, s.actual_end, s.break_minutes);
      }
    }
    return map;
  }, [shifts]);

  const rows = useMemo(() => {
    return Object.entries(byEmployee)
      .filter(([id]) => id !== "__open__")
      .map(([empId, data]) => {
        const emp = empMap[empId];
        return {
          id: empId,
          name: emp ? `${emp.first_name} ${emp.last_name}` : "Unbekannt",
          contract: emp?.contract_type ?? "–",
          ...data,
          hasActual: data.actual > 0,
          diff: data.actual > 0 ? data.actual - data.planned : null,
        };
      })
      .sort((a, b) => a.name.localeCompare(b.name, "de"));
  }, [byEmployee, empMap]);

  const totals = useMemo(() => rows.reduce(
    (acc, r) => ({ planned: acc.planned + r.planned, count: acc.count + r.count }),
    { planned: 0, count: 0 }
  ), [rows]);

  const exportCsv = () => {
    const CONTRACT_LABELS: Record<string, string> = {
      minijob: "Minijob", part_time: "Teilzeit", full_time: "Vollzeit",
    };
    const header = ["Mitarbeiter", "Vertragsart", "Dienste", "Soll-Stunden", "Ist-Stunden", "Differenz"];
    const dataRows = rows.map(r => [
      r.name,
      CONTRACT_LABELS[r.contract] ?? r.contract,
      String(r.count),
      r.planned.toFixed(2).replace(".", ","),
      r.actual > 0 ? r.actual.toFixed(2).replace(".", ",") : "",
      r.diff != null ? r.diff.toFixed(2).replace(".", ",") : "",
    ]);
    downloadCsv(`stundenbericht_${monthLabel.replace(" ", "_")}.csv`, [header, ...dataRows]);
  };

  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">Keine Dienste in diesem Monat.</p>;
  }

  const CONTRACT_LABELS: Record<string, string> = {
    minijob: "Minijob", part_time: "Teilzeit", full_time: "Vollzeit",
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs uppercase tracking-wide">
            {isPrivileged && <th className="text-left pb-2 pr-4 font-medium">Mitarbeiter</th>}
            {isPrivileged && <th className="text-left pb-2 pr-4 font-medium">Vertragsart</th>}
            <th className="text-right pb-2 pr-4 font-medium">Dienste</th>
            <th className="text-right pb-2 pr-4 font-medium">Soll-Stunden</th>
            <th className="text-right pb-2 pr-4 font-medium">Ist-Stunden</th>
            <th className="text-right pb-2 font-medium">Differenz</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => (
            <tr key={r.id} className="hover:bg-accent/30 transition-colors">
              {isPrivileged && (
                <td className="py-2.5 pr-4 font-medium text-foreground">{r.name}</td>
              )}
              {isPrivileged && (
                <td className="py-2.5 pr-4 text-muted-foreground text-xs">
                  {CONTRACT_LABELS[r.contract] ?? r.contract}
                </td>
              )}
              <td className="py-2.5 pr-4 text-right tabular-nums">{r.count}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-foreground">
                {fmtHours(r.planned)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-muted-foreground">
                {r.hasActual ? fmtHours(r.actual) : <span className="text-xs">–</span>}
              </td>
              <td className="py-2.5 text-right tabular-nums text-xs font-medium">
                {r.diff != null ? (
                  <span style={{
                    color: r.diff >= 0
                      ? "rgb(var(--ctp-green))"
                      : "rgb(var(--ctp-red))"
                  }}>
                    {r.diff >= 0 ? "+" : ""}{fmtHours(r.diff)}
                  </span>
                ) : (
                  <span className="text-muted-foreground">–</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
        {isPrivileged && (
          <tfoot>
            <tr className="border-t border-border font-semibold text-foreground">
              <td className="pt-2.5 pr-4">Gesamt</td>
              <td className="pt-2.5 pr-4" />
              <td className="pt-2.5 pr-4 text-right tabular-nums">{totals.count}</td>
              <td className="pt-2.5 pr-4 text-right tabular-nums">{fmtHours(totals.planned)}</td>
              <td className="pt-2.5 pr-4" />
              <td className="pt-2.5" />
            </tr>
          </tfoot>
        )}
      </table>
      {isPrivileged && rows.length > 0 && (
        <div className="mt-4 flex justify-end">
          <button
            onClick={exportCsv}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-accent transition-colors"
          >
            <Download size={13} />
            CSV exportieren
          </button>
        </div>
      )}
    </div>
  );
}

// ── 2. Minijob-Auslastung ─────────────────────────────────────────────────────

function MinijobUtilization({ employees, payrollEntries, selectedMonth }: {
  employees: any[]; payrollEntries: any[]; selectedMonth: Date;
}) {
  const minijobEmps = employees.filter((e: any) => e.contract_type === "minijob");

  if (minijobEmps.length === 0) {
    return <p className="text-sm text-muted-foreground">Keine Minijob-Mitarbeiter vorhanden.</p>;
  }

  const payrollMap = useMemo(() =>
    Object.fromEntries(payrollEntries.map((p: any) => [p.employee_id, p])),
    [payrollEntries]
  );

  const MONTHLY_LIMIT = 556;
  const ANNUAL_LIMIT = 6672;

  return (
    <div className="space-y-4">
      {minijobEmps.map((emp: any) => {
        const p = payrollMap[emp.id];
        const monthlyGross = p?.total_gross ?? null;
        const ytdGross = p?.ytd_gross ?? null;
        const annualLimit = emp.annual_salary_limit ?? ANNUAL_LIMIT;

        const monthPct = monthlyGross != null ? Math.min(100, (monthlyGross / MONTHLY_LIMIT) * 100) : null;
        const yearPct = ytdGross != null ? Math.min(100, (ytdGross / annualLimit) * 100) : null;

        const isMonthCritical = monthPct != null && monthPct >= 90;
        const isYearCritical = yearPct != null && yearPct >= 90;

        return (
          <div key={emp.id} className="border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="font-medium text-foreground text-sm">
                {emp.first_name} {emp.last_name}
              </span>
              {!p && (
                <span className="text-xs text-muted-foreground">
                  Keine Abrechnung für diesen Monat
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Monat */}
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Monat</span>
                  <span className="tabular-nums">
                    {monthlyGross != null ? fmtEuro(monthlyGross) : "–"}
                    <span className="text-muted-foreground"> / {fmtEuro(MONTHLY_LIMIT)}</span>
                  </span>
                </div>
                <div className="h-2 rounded-full bg-accent overflow-hidden">
                  {monthPct != null && (
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${monthPct}%`,
                        backgroundColor: isMonthCritical
                          ? "rgb(var(--ctp-red))"
                          : monthPct >= 70
                            ? "rgb(var(--ctp-peach))"
                            : "rgb(var(--ctp-green))",
                      }}
                    />
                  )}
                </div>
                {monthPct != null && (
                  <p className="text-xs text-right mt-0.5 tabular-nums"
                    style={{ color: isMonthCritical ? "rgb(var(--ctp-red))" : "rgb(var(--muted-foreground))" }}>
                    {monthPct.toFixed(0)}%{isMonthCritical ? " ⚠ Limit fast erreicht!" : ""}
                  </p>
                )}
              </div>

              {/* Jahr */}
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Jahr {selectedMonth.getFullYear()}</span>
                  <span className="tabular-nums">
                    {ytdGross != null ? fmtEuro(ytdGross) : "–"}
                    <span className="text-muted-foreground"> / {fmtEuro(annualLimit)}</span>
                  </span>
                </div>
                <div className="h-2 rounded-full bg-accent overflow-hidden">
                  {yearPct != null && (
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${yearPct}%`,
                        backgroundColor: isYearCritical
                          ? "rgb(var(--ctp-red))"
                          : yearPct >= 70
                            ? "rgb(var(--ctp-peach))"
                            : "rgb(var(--ctp-blue))",
                      }}
                    />
                  )}
                </div>
                {yearPct != null && (
                  <p className="text-xs text-right mt-0.5 tabular-nums"
                    style={{ color: isYearCritical ? "rgb(var(--ctp-red))" : "rgb(var(--muted-foreground))" }}>
                    {yearPct.toFixed(0)}%{isYearCritical ? " ⚠ Jahresgrenze fast erreicht!" : ""}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <p className="text-xs text-muted-foreground">
        Monatsgrenze 2025: 556 €  · Jahresgrenze: 6.672 €.
        Die Werte basieren auf berechneten Abrechnungseinträgen – zuerst auf der Abrechnungsseite berechnen.
      </p>
    </div>
  );
}

// ── 3. Diensttypen-Auswertung ─────────────────────────────────────────────────

function ShiftTypeReport({ shifts, shiftTypes }: { shifts: any[]; shiftTypes: any[] }) {
  const typeMap = useMemo(() =>
    Object.fromEntries(shiftTypes.map((st: any) => [st.id, st])),
    [shiftTypes]
  );

  const byType = useMemo(() => {
    const map: Record<string, { name: string; color: string; count: number; hours: number }> = {
      __none__: { name: "Kein Typ", color: "rgb(var(--ctp-overlay1))", count: 0, hours: 0 },
    };
    for (const s of shifts) {
      if (s.status === "cancelled" || s.status === "cancelled_absence") continue;
      const key = s.shift_type_id ?? "__none__";
      if (!map[key]) {
        const st = typeMap[key];
        if (!st) continue;
        map[key] = { name: st.name, color: st.color, count: 0, hours: 0 };
      }
      map[key].count++;
      map[key].hours += calcShiftHours(s.start_time, s.end_time, s.break_minutes);
    }
    return Object.entries(map)
      .filter(([, v]) => v.count > 0)
      .sort((a, b) => b[1].hours - a[1].hours);
  }, [shifts, typeMap]);

  const totalHours = byType.reduce((s, [, v]) => s + v.hours, 0);

  if (byType.length === 0) {
    return <p className="text-sm text-muted-foreground">Keine Dienste mit Diensttyp in diesem Monat.</p>;
  }

  return (
    <div className="space-y-3">
      {byType.map(([key, { name, color, count, hours }]) => {
        const pct = totalHours > 0 ? (hours / totalHours) * 100 : 0;
        return (
          <div key={key}>
            <div className="flex items-center justify-between text-sm mb-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: key === "__none__" ? "rgb(var(--ctp-overlay1))" : color }} />
                <span className="font-medium text-foreground">{name}</span>
                <span className="text-xs text-muted-foreground">{count} Dienste</span>
              </div>
              <div className="flex items-center gap-3 text-xs tabular-nums">
                <span className="text-muted-foreground">{pct.toFixed(0)}%</span>
                <span className="font-medium text-foreground w-14 text-right">{fmtHours(hours)}</span>
              </div>
            </div>
            <div className="h-2 rounded-full bg-accent overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${pct}%`, backgroundColor: key === "__none__" ? "rgb(var(--ctp-overlay1))" : color }}
              />
            </div>
          </div>
        );
      })}
      <p className="text-xs text-muted-foreground pt-1">
        Gesamt: {fmtHours(totalHours)} in {byType.reduce((s, [, v]) => s + v.count, 0)} Diensten
      </p>
    </div>
  );
}

// ── 4. Compliance-Warnungen ───────────────────────────────────────────────────

function ComplianceWarnings({ shifts, employees }: { shifts: any[]; employees: any[] }) {
  const empMap = useMemo(() =>
    Object.fromEntries(employees.map((e: any) => [e.id, `${e.first_name} ${e.last_name}`])),
    [employees]
  );

  const active = shifts.filter(
    (s: any) => s.status !== "cancelled" && s.status !== "cancelled_absence"
  );

  const openShifts = active.filter((s: any) => !s.employee_id);
  const restViolations = active.filter((s: any) => s.employee_id && !s.rest_period_ok);
  const breakViolations = active.filter((s: any) => s.employee_id && !s.break_ok);
  const minijobViolations = active.filter((s: any) => s.employee_id && !s.minijob_limit_ok);

  type Entry = { ok: boolean; count: number; label: string; items: any[] };

  const sections: Entry[] = [
    {
      ok: openShifts.length === 0,
      count: openShifts.length,
      label: "Offene Dienste (kein Mitarbeiter zugewiesen)",
      items: openShifts,
    },
    {
      ok: restViolations.length === 0,
      count: restViolations.length,
      label: "Ruhezeit-Verstöße (< 11h zwischen Diensten)",
      items: restViolations,
    },
    {
      ok: breakViolations.length === 0,
      count: breakViolations.length,
      label: "Pausen-Verstöße (ArbZG §4)",
      items: breakViolations,
    },
    {
      ok: minijobViolations.length === 0,
      count: minijobViolations.length,
      label: "Minijob-Limit-Überschreitungen",
      items: minijobViolations,
    },
  ];

  const hasAnyIssue = sections.some((s) => !s.ok);

  return (
    <div className="space-y-3">
      {!hasAnyIssue && (
        <div className="flex items-center gap-2 p-3 rounded-lg"
          style={{ backgroundColor: "rgb(var(--ctp-green) / 0.10)" }}>
          <CheckCircle2 size={16} style={{ color: "rgb(var(--ctp-green))" }} />
          <span className="text-sm font-medium" style={{ color: "rgb(var(--ctp-green))" }}>
            Keine Compliance-Probleme in diesem Monat.
          </span>
        </div>
      )}

      {sections.map((sec) => (
        <details key={sec.label} open={!sec.ok}>
          <summary className="flex items-center gap-2 cursor-pointer select-none py-2 hover:text-foreground transition-colors">
            {sec.ok
              ? <CheckCircle2 size={15} style={{ color: "rgb(var(--ctp-green))" }} />
              : <AlertTriangle size={15} style={{ color: "rgb(var(--ctp-peach))" }} />
            }
            <span className={`text-sm ${sec.ok ? "text-muted-foreground" : "text-foreground font-medium"}`}>
              {sec.ok ? "✓ " : `${sec.count}× `}{sec.label}
            </span>
          </summary>

          {!sec.ok && (
            <div className="mt-2 ml-6 space-y-1">
              {sec.items.slice(0, 10).map((s: any) => (
                <div key={s.id} className="text-xs text-muted-foreground flex gap-2">
                  <span className="tabular-nums shrink-0">
                    {format(parseISO(s.date), "dd.MM.", { locale: de })}
                  </span>
                  <span>{s.start_time?.slice(0, 5)}–{s.end_time?.slice(0, 5)}</span>
                  {s.employee_id && (
                    <span className="text-foreground">{empMap[s.employee_id] ?? "–"}</span>
                  )}
                </div>
              ))}
              {sec.items.length > 10 && (
                <p className="text-xs text-muted-foreground">
                  … und {sec.items.length - 10} weitere
                </p>
              )}
            </div>
          )}
        </details>
      ))}
    </div>
  );
}

// ── Absences Report ───────────────────────────────────────────────────────────

const ABSENCE_TYPE_LABELS: Record<string, string> = {
  vacation:   "Urlaub",
  sick:       "Krank",
  unpaid:     "Unbezahlt",
  other:      "Sonstiges",
  compensatory: "Ausgleich",
};

const ABSENCE_STATUS_STYLE: Record<string, string> = {
  pending:  "text-ctp-yellow",
  approved: "text-ctp-green",
  rejected: "text-ctp-red",
};

function AbsencesReport({ absences, isPrivileged, year }: {
  absences: any[]; isPrivileged: boolean; year: number;
}) {
  if (absences.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-2">
        Keine Abwesenheiten im Jahr {year}.
      </p>
    );
  }

  // Gruppiere nach Typ für Zusammenfassung
  const byType: Record<string, number> = {};
  for (const a of absences) {
    byType[a.absence_type] = (byType[a.absence_type] ?? 0) + a.days_in_year;
  }

  return (
    <div className="space-y-4">
      {/* Zusammenfassung */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(byType).map(([type, days]) => (
          <span key={type} className="text-xs bg-accent rounded-full px-2.5 py-1 text-foreground border border-border">
            {ABSENCE_TYPE_LABELS[type] ?? type}: <strong>{days}</strong> Tage
          </span>
        ))}
      </div>

      {/* Tabelle */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              {isPrivileged && <th className="text-left pb-2 pr-4 font-medium">Mitarbeiter</th>}
              <th className="text-left pb-2 pr-4 font-medium">Typ</th>
              <th className="text-left pb-2 pr-4 font-medium">Von</th>
              <th className="text-left pb-2 pr-4 font-medium">Bis</th>
              <th className="text-right pb-2 pr-4 font-medium">Tage</th>
              <th className="text-left pb-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {absences.map((a) => (
              <tr key={a.id} className="border-b border-border/50 hover:bg-accent/30 transition-colors">
                {isPrivileged && (
                  <td className="py-2 pr-4 text-foreground">
                    {a.first_name} {a.last_name}
                  </td>
                )}
                <td className="py-2 pr-4 text-muted-foreground">
                  {ABSENCE_TYPE_LABELS[a.absence_type] ?? a.absence_type}
                </td>
                <td className="py-2 pr-4 tabular-nums">{a.start_date}</td>
                <td className="py-2 pr-4 tabular-nums">{a.end_date}</td>
                <td className="py-2 pr-4 text-right tabular-nums font-medium">{a.days_in_year}</td>
                <td className={`py-2 text-xs ${ABSENCE_STATUS_STYLE[a.status] ?? "text-muted-foreground"}`}>
                  {a.status}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={isPrivileged ? 4 : 3} className="pt-3 text-muted-foreground text-xs">
                Gesamt {year}
              </td>
              <td className="pt-3 text-right font-semibold">
                {absences.reduce((s, a) => s + a.days_in_year, 0)} Tage
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

// ── Hauptseite ────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const { user } = useAuthStore();
  const isPrivileged = user?.role === "admin" || user?.role === "manager";

  const [selectedMonth, setSelectedMonth] = useState(() => startOfMonth(new Date()));
  const monthStart = format(selectedMonth, "yyyy-MM-dd");
  const monthEnd = format(endOfMonth(selectedMonth), "yyyy-MM-dd");
  const monthLabel = format(selectedMonth, "MMMM yyyy", { locale: de });

  const { data: employees = [] } = useQuery({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list().then((r) => r.data),
    enabled: isPrivileged,
  });

  const { data: shifts = [], isLoading: shiftsLoading } = useQuery({
    queryKey: ["shifts", monthStart, monthEnd],
    queryFn: () => shiftsApi.list({ from_date: monthStart, to_date: monthEnd }).then((r) => r.data),
  });

  const { data: payrollEntries = [] } = useQuery({
    queryKey: ["payroll", monthStart],
    queryFn: () => payrollApi.list({ month: monthStart }).then((r) => r.data),
    enabled: isPrivileged,
  });

  const { data: shiftTypes = [] } = useQuery({
    queryKey: ["shift-types"],
    queryFn: () => shiftTypesApi.list().then((r) => r.data),
  });

  const selectedYear = selectedMonth.getFullYear();
  const { data: absences = [] } = useQuery({
    queryKey: ["report-absences", selectedYear],
    queryFn: () => reportsApi.absences(selectedYear).then((r) => r.data),
  });

  const handleCsvExport = async () => {
    try {
      const resp = await reportsApi.exportCsv({ from: monthStart, to: monthEnd });
      const blob = new Blob([resp.data], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `stundenbericht_${monthLabel.replace(" ", "_")}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // fallback to client-side export handled in HoursReport
    }
  };

  // Quick stats for summary row
  const activeShifts = (shifts as any[]).filter(
    (s: any) => s.status !== "cancelled" && s.status !== "cancelled_absence"
  );
  const totalHours = activeShifts.reduce(
    (sum: number, s: any) => sum + calcShiftHours(s.start_time, s.end_time, s.break_minutes), 0
  );
  const confirmedCount = activeShifts.filter((s: any) => s.status === "confirmed").length;
  const openCount = activeShifts.filter((s: any) => !s.employee_id).length;
  const complianceIssues = activeShifts.filter(
    (s: any) => s.employee_id && (!s.rest_period_ok || !s.break_ok || !s.minijob_limit_ok)
  ).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-foreground">Berichte</h1>

        <div className="flex items-center gap-2">
          {isPrivileged && (
            <button
              onClick={handleCsvExport}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:bg-accent transition-colors"
            >
              <Download size={13} /> CSV exportieren
            </button>
          )}
          {/* Month picker */}
          <div className="flex items-center gap-1 bg-card border border-border rounded-lg p-1">
          <button
            onClick={() => setSelectedMonth((m) => startOfMonth(subMonths(m, 1)))}
            className="p-1.5 rounded hover:bg-accent transition-colors"
          >
            <ChevronLeft size={16} className="text-muted-foreground" />
          </button>
          <span className="text-sm font-medium text-foreground px-3 min-w-36 text-center capitalize">
            {monthLabel}
          </span>
          <button
            onClick={() => setSelectedMonth((m) => startOfMonth(addMonths(m, 1)))}
            className="p-1.5 rounded hover:bg-accent transition-colors"
          >
            <ChevronRight size={16} className="text-muted-foreground" />
          </button>
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          {
            label: "Dienste gesamt",
            value: shiftsLoading ? "…" : activeShifts.length,
            icon: Clock,
            color: "--ctp-blue",
          },
          {
            label: "Soll-Stunden",
            value: shiftsLoading ? "…" : fmtHours(totalHours),
            icon: TrendingUp,
            color: "--ctp-sapphire",
          },
          {
            label: "Bestätigt",
            value: shiftsLoading ? "…" : confirmedCount,
            icon: CheckCircle2,
            color: "--ctp-green",
          },
          {
            label: openCount > 0 || complianceIssues > 0 ? "⚠ Probleme" : "Alles OK",
            value: shiftsLoading ? "…" : openCount + complianceIssues,
            icon: openCount + complianceIssues > 0 ? AlertTriangle : CheckCircle2,
            color: openCount + complianceIssues > 0 ? "--ctp-peach" : "--ctp-green",
          },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-card rounded-xl border border-border p-4">
            <div className="flex items-center gap-2 mb-2">
              <Icon size={14} style={{ color: `rgb(var(${color}))` }} />
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
            <div className="text-xl font-bold text-foreground tabular-nums">{value}</div>
          </div>
        ))}
      </div>

      {/* Section 1: Stundenbericht */}
      <Section title="Stundenbericht" icon={Clock} color="--ctp-blue">
        <HoursReport
          shifts={shifts as any[]}
          employees={employees as any[]}
          isPrivileged={isPrivileged}
          monthLabel={monthLabel}
        />
      </Section>

      {/* Section 2: Minijob-Auslastung (only privileged) */}
      {isPrivileged && (
        <Section title="Minijob-Auslastung" icon={TrendingUp} color="--ctp-green">
          <MinijobUtilization
            employees={employees as any[]}
            payrollEntries={payrollEntries as any[]}
            selectedMonth={selectedMonth}
          />
        </Section>
      )}

      {/* Section 3: Diensttypen */}
      {(shiftTypes as any[]).length > 0 && (
        <Section title="Diensttypen-Auswertung" icon={Layers} color="--ctp-mauve">
          <ShiftTypeReport shifts={shifts as any[]} shiftTypes={shiftTypes as any[]} />
        </Section>
      )}

      {/* Section 4: Compliance */}
      <Section title="Compliance-Warnungen" icon={AlertTriangle} color="--ctp-peach">
        <ComplianceWarnings shifts={shifts as any[]} employees={employees as any[]} />
      </Section>

      {/* Section 5: Abwesenheiten */}
      <Section title={`Abwesenheiten ${selectedYear}`} icon={CalendarOff} color="--ctp-teal">
        <AbsencesReport
          absences={absences as any[]}
          isPrivileged={isPrivileged}
          year={selectedYear}
        />
      </Section>
    </div>
  );
}
