"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Clock,
  Loader2,
  RefreshCw,
  Check,
  X,
  Info,
} from "lucide-react";
import { complianceApi, employeesApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import toast from "react-hot-toast";
import { format, parseISO } from "date-fns";
import { de } from "date-fns/locale";

/* ── Typen ─────────────────────────────────────────────────────────────────── */
interface Violation {
  shift_id: string;
  shift_date: string;
  start_time: string;
  end_time: string;
  employee_id: string | null;
  employee_name: string;
  rest_period_ok: boolean;
  break_ok: boolean;
  minijob_limit_ok: boolean;
  status: string;
}

interface Employee {
  id: string;
  first_name: string;
  last_name: string;
}

/* ── Status-Badge ──────────────────────────────────────────────────────────── */
const STATUS_LABELS: Record<string, string> = {
  planned:            "Geplant",
  confirmed:          "Bestätigt",
  completed:          "Abgeschlossen",
  cancelled:          "Storniert",
  cancelled_absence:  "Abwesenheit",
};

function FlagBadge({ ok, label }: { ok: boolean; label: string }) {
  if (ok) {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
        style={{ backgroundColor: "rgb(var(--ctp-green) / 0.12)", color: "rgb(var(--ctp-green))" }}>
        <Check size={10} /> {label}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
      style={{ backgroundColor: "rgb(var(--ctp-red) / 0.12)", color: "rgb(var(--ctp-red))" }}>
      <X size={10} /> {label}
    </span>
  );
}

/* ── Haupt-Komponente ──────────────────────────────────────────────────────── */
export default function CompliancePage() {
  const { user } = useAuthStore();
  const qc = useQueryClient();

  const [filterEmployee, setFilterEmployee] = useState("");
  const [filterFrom, setFilterFrom]         = useState("");
  const [filterTo, setFilterTo]             = useState("");

  // Mitarbeiter-Liste für Filter-Dropdown (nur für Admin/Manager)
  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list(false).then((r) => r.data),
    enabled: !isEmployee,
  });

  // Violations laden
  const params: Record<string, string> = {};
  if (filterEmployee) params.employee_id = filterEmployee;
  if (filterFrom)     params.from_date   = filterFrom;
  if (filterTo)       params.to_date     = filterTo;

  const { data: violations = [], isLoading } = useQuery<Violation[]>({
    queryKey: ["compliance-violations", params],
    queryFn: () => complianceApi.listViolations(params).then((r) => r.data),
  });

  // "Jetzt prüfen"-Mutation
  const runMutation = useMutation({
    mutationFn: () => complianceApi.run(),
    onSuccess: (res) => {
      const d = res.data as { checked: number; violations: number };
      toast.success(`${d.checked} Dienste geprüft – ${d.violations} Verstöße gefunden`);
      qc.invalidateQueries({ queryKey: ["compliance-violations"] });
    },
    onError: () => toast.error("Compliance-Prüfung fehlgeschlagen"),
  });

  const isEmployee = user?.role === "employee";

  // Summary-Zahlen berechnen
  const totalViolations    = violations.length;
  const restViolations     = violations.filter((v) => !v.rest_period_ok).length;
  const breakViolations    = violations.filter((v) => !v.break_ok).length;
  const minijobViolations  = violations.filter((v) => !v.minijob_limit_ok).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Compliance</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {isEmployee
              ? "Deine arbeitsrechtlichen Prüfungen nach ArbZG"
              : "Arbeitsrechtliche Prüfungen nach ArbZG"}
          </p>
        </div>
        {!isEmployee && (
          <button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
          >
            {runMutation.isPending
              ? <Loader2 size={15} className="animate-spin" />
              : <RefreshCw size={15} />}
            Jetzt prüfen
          </button>
        )}
      </div>

      {/* Summary-Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-card rounded-xl border border-border p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
            style={{ backgroundColor: "rgb(var(--ctp-red) / 0.12)" }}>
            <ShieldX size={20} style={{ color: "rgb(var(--ctp-red))" }} />
          </div>
          <div>
            <div className="text-2xl font-bold text-foreground">{totalViolations}</div>
            <div className="text-xs text-muted-foreground">Verstöße gesamt</div>
          </div>
        </div>
        <div className="bg-card rounded-xl border border-border p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
            style={{ backgroundColor: "rgb(var(--ctp-peach) / 0.12)" }}>
            <ShieldAlert size={20} style={{ color: "rgb(var(--ctp-peach))" }} />
          </div>
          <div>
            <div className="text-2xl font-bold text-foreground">{restViolations}</div>
            <div className="text-xs text-muted-foreground">Ruhezeitverstöße (§5 ArbZG)</div>
          </div>
        </div>
        <div className="bg-card rounded-xl border border-border p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
            style={{ backgroundColor: "rgb(var(--ctp-yellow) / 0.12)" }}>
            <Clock size={20} style={{ color: "rgb(var(--ctp-yellow))" }} />
          </div>
          <div>
            <div className="text-2xl font-bold text-foreground">{breakViolations}</div>
            <div className="text-xs text-muted-foreground">Pausenverstöße (§4 ArbZG)</div>
          </div>
        </div>
      </div>

      {/* Filter */}
      <div className="bg-card rounded-xl border border-border p-4">
        {isEmployee && (
          <p className="text-xs text-muted-foreground mb-3 flex items-center gap-1.5">
            <Info size={13} className="shrink-0" />
            Es werden nur deine eigenen Dienste angezeigt.
          </p>
        )}
        <div className="flex flex-wrap gap-3 items-end">
          {!isEmployee && (
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Mitarbeiter</label>
              <select
                value={filterEmployee}
                onChange={(e) => setFilterEmployee(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-sm"
              >
                <option value="">Alle</option>
                {employees.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.first_name} {e.last_name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Von</label>
            <input
              type="date"
              value={filterFrom}
              onChange={(e) => setFilterFrom(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Bis</label>
            <input
              type="date"
              value={filterTo}
              onChange={(e) => setFilterTo(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-sm"
            />
          </div>
          {(filterEmployee || filterFrom || filterTo) && (
            <button
              onClick={() => { setFilterEmployee(""); setFilterFrom(""); setFilterTo(""); }}
              className="text-xs text-muted-foreground hover:text-foreground px-2 py-1.5"
            >
              Zurücksetzen
            </button>
          )}
        </div>
      </div>

      {/* Minijob-Hinweis */}
      {minijobViolations > 0 && (
        <div className="flex items-start gap-2 text-xs text-muted-foreground bg-card border border-border rounded-lg px-4 py-3">
          <Info size={14} className="shrink-0 mt-0.5" />
          <span>
            Minijob-Limits ({minijobViolations} Einträge) werden nur geprüft, wenn eine
            Abrechnung für den jeweiligen Monat berechnet wurde.
          </span>
        </div>
      )}

      {/* Tabelle */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-32 text-muted-foreground text-sm gap-2">
            <Loader2 size={16} className="animate-spin" /> Wird geladen…
          </div>
        ) : violations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 gap-3">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
              style={{ backgroundColor: "rgb(var(--ctp-green) / 0.12)" }}>
              <ShieldCheck size={24} style={{ color: "rgb(var(--ctp-green))" }} />
            </div>
            <div className="text-center">
              <div className="font-medium text-foreground">Keine Verstöße gefunden</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Alle geprüften Dienste entsprechen den Vorschriften
              </div>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Datum</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Mitarbeiter</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Schicht</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Ruhezeit §5</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Pause §4</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Minijob</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Status</th>
                </tr>
              </thead>
              <tbody>
                {violations.map((v, idx) => (
                  <tr
                    key={v.shift_id}
                    className="border-b border-border last:border-0 hover:bg-muted/40 transition-colors"
                    style={idx % 2 === 1 ? { backgroundColor: "rgb(var(--ctp-surface0) / 0.3)" } : {}}
                  >
                    <td className="px-4 py-3 font-medium text-foreground whitespace-nowrap">
                      {format(parseISO(v.shift_date), "dd.MM.yyyy", { locale: de })}
                    </td>
                    <td className="px-4 py-3 text-foreground">{v.employee_name}</td>
                    <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                      {v.start_time.slice(0, 5)} – {v.end_time.slice(0, 5)}
                    </td>
                    <td className="px-4 py-3">
                      <FlagBadge ok={v.rest_period_ok} label="Ruhezeit" />
                    </td>
                    <td className="px-4 py-3">
                      <FlagBadge ok={v.break_ok} label="Pause" />
                    </td>
                    <td className="px-4 py-3">
                      <FlagBadge ok={v.minijob_limit_ok} label="Minijob" />
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-muted-foreground">
                        {STATUS_LABELS[v.status] ?? v.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Legende */}
      <div className="text-xs text-muted-foreground space-y-0.5">
        <p>• <strong>Ruhezeit §5 ArbZG</strong>: Mindestens 11 Stunden zwischen zwei Diensten</p>
        <p>• <strong>Pause §4 ArbZG</strong>: Ab 6h Arbeit → 30 Min Pause, ab 9h → 45 Min Pause</p>
        <p>• <strong>Minijob-Limit</strong>: Monatsgrenze 556 € / Jahresgrenze 6.672 € (2025)</p>
        <p className="pt-1">Klicke <strong>„Jetzt prüfen"</strong>, um alle Dienste der letzten 365 Tage neu zu evaluieren.</p>
      </div>
    </div>
  );
}
