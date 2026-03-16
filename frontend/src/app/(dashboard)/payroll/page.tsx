"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Calculator,
  CheckCircle,
  Euro,
  Clock,
  AlertTriangle,
  X,
  Check,
  RotateCcw,
  TrendingUp,
  Users,
  Download,
  Loader2,
} from "lucide-react";
import { payrollApi, employeesApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import toast from "react-hot-toast";

/* ── helpers ──────────────────────────────────────────────────────── */
function eur(v: number | null | undefined) {
  if (v == null) return "–";
  return v.toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}
function hrs(v: number | null | undefined) {
  if (v == null) return "–";
  return `${v.toFixed(2)} h`;
}
function fmt(v: number | null | undefined, decimals = 2) {
  if (v == null) return "–";
  return v.toFixed(decimals);
}

const MINIJOB_MONTHLY = 556;
const MINIJOB_ANNUAL = 6672;

function limitColor(pct: number) {
  if (pct >= 100) return "bg-red-500";
  if (pct >= 90) return "rgb(var(--ctp-peach))";
  return "rgb(var(--ctp-green))";
}

const STATUS_LABELS: Record<string, string> = {
  draft: "Entwurf",
  approved: "Genehmigt",
  paid: "Bezahlt",
};
const STATUS_COLORS: Record<string, string> = {
  draft: "text-muted-foreground bg-muted",
  approved: "text-emerald-700 bg-emerald-100 dark:text-emerald-300 dark:bg-emerald-900/30",
  paid: "text-blue-700 bg-blue-100 dark:text-blue-300 dark:bg-blue-900/30",
};

/* ── types ────────────────────────────────────────────────────────── */
interface PayrollEntry {
  id: string;
  tenant_id: string;
  employee_id: string;
  month: string;
  planned_hours: number | null;
  actual_hours: number | null;
  carryover_hours: number;
  paid_hours: number | null;
  early_hours: number;
  late_hours: number;
  night_hours: number;
  weekend_hours: number;
  sunday_hours: number;
  holiday_hours: number;
  base_wage: number | null;
  early_surcharge: number;
  late_surcharge: number;
  night_surcharge: number;
  weekend_surcharge: number;
  sunday_surcharge: number;
  holiday_surcharge: number;
  total_gross: number | null;
  ytd_gross: number | null;
  annual_limit_remaining: number | null;
  ytd_hours: number;
  annual_hours_target: number | null;
  annual_hours_remaining: number | null;
  monthly_hours_target: number | null;
  wage_details: { splits: { from: string; to: string; rate: number; hours: number; amount: number }[] } | null;
  status: string;
  notes: string | null;
  pdf_path: string | null;
  created_at: string;
}

interface Employee {
  id: string;
  first_name: string;
  last_name: string;
  contract_type: string;
  hourly_rate: number | null;
  vacation_days: number;
}

/* ── EmployeePdfButton ────────────────────────────────────────────── */
function EmployeePdfButton({ entry }: { entry: PayrollEntry }) {
  const [loading, setLoading] = useState(false);
  async function handleDownload() {
    setLoading(true);
    try {
      const response = await payrollApi.downloadPdf(entry.id);
      const url = URL.createObjectURL(response.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `vera-abrechnung-${entry.month.slice(0, 7)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("PDF konnte nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }
  return (
    <button
      onClick={handleDownload}
      disabled={loading}
      className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border border-border text-muted-foreground hover:bg-muted disabled:opacity-50"
    >
      {loading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
      PDF herunterladen
    </button>
  );
}

/* ── DetailModal ──────────────────────────────────────────────────── */
function DetailModal({
  entry,
  employee,
  onClose,
}: {
  entry: PayrollEntry;
  employee: Employee | undefined;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [notes, setNotes] = useState(entry.notes ?? "");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [confirmPending, setConfirmPending] = useState<"approved" | "paid" | null>(null);

  async function handleDownloadPdf() {
    setPdfLoading(true);
    try {
      const response = await payrollApi.downloadPdf(entry.id);
      const url = URL.createObjectURL(response.data as Blob);
      const a = document.createElement("a");
      const empName = employee ? employee.last_name.toLowerCase() : "mitarbeiter";
      const month = entry.month.slice(0, 7);
      a.href = url;
      a.download = `vera-abrechnung-${empName}-${month}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("PDF konnte nicht geladen werden");
    } finally {
      setPdfLoading(false);
    }
  }

  const updateMutation = useMutation({
    mutationFn: (data: { status?: string; notes?: string }) =>
      payrollApi.update(entry.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payroll"] });
      toast.success("Abrechnung aktualisiert");
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Fehler");
    },
  });

  const ytdPct = entry.ytd_gross != null ? Math.min((entry.ytd_gross / MINIJOB_ANNUAL) * 100, 120) : 0;
  const isMinijob = employee?.contract_type === "minijob";
  const overLimit = (entry.ytd_gross ?? 0) > MINIJOB_ANNUAL;
  const nearLimit = !overLimit && (entry.ytd_gross ?? 0) > MINIJOB_ANNUAL * 0.9;

  const totalSurcharges =
    entry.early_surcharge +
    entry.late_surcharge +
    entry.night_surcharge +
    entry.weekend_surcharge +
    entry.sunday_surcharge +
    entry.holiday_surcharge;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-card rounded-2xl border border-border w-full max-w-xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div>
            <div className="font-semibold text-foreground text-lg">
              {employee ? `${employee.first_name} ${employee.last_name}` : "Mitarbeiter"}
            </div>
            <div className="text-sm text-muted-foreground">
              {new Date(entry.month + "T00:00:00").toLocaleDateString("de-DE", {
                month: "long",
                year: "numeric",
              })}
              {" · "}
              <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[entry.status]}`}>
                {STATUS_LABELS[entry.status]}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-muted text-muted-foreground">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Lohnübersicht */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-muted/50 rounded-xl p-3 text-center">
              <div className="text-xs text-muted-foreground mb-1">Bezahlte Std.</div>
              <div className="font-semibold text-foreground">{hrs(entry.paid_hours)}</div>
            </div>
            <div className="bg-muted/50 rounded-xl p-3 text-center">
              <div className="text-xs text-muted-foreground mb-1">Grundlohn</div>
              <div className="font-semibold text-foreground">{eur(entry.base_wage)}</div>
            </div>
            <div
              className="rounded-xl p-3 text-center"
              style={{ backgroundColor: "rgb(var(--ctp-green) / 0.12)", color: "rgb(var(--ctp-green))" }}
            >
              <div className="text-xs opacity-75 mb-1">Brutto gesamt</div>
              <div className="font-bold text-lg">{eur(entry.total_gross)}</div>
            </div>
          </div>

          {/* Stunden-Aufschlüsselung */}
          <div>
            <div className="text-sm font-medium text-foreground mb-2">Stunden-Aufschlüsselung</div>
            <div className="space-y-1 text-sm">
              {[
                { label: "Geplant (Soll)", value: hrs(entry.planned_hours) },
                { label: "Tatsächliche Stunden", value: hrs(entry.actual_hours) },
                { label: "Übertrag Vormonat", value: hrs(entry.carryover_hours) },
                { label: "Bezahlte Stunden", value: hrs(entry.paid_hours), bold: true },
              ].map((r) => (
                <div key={r.label} className="flex justify-between">
                  <span className={r.bold ? "font-medium text-foreground" : "text-muted-foreground"}>{r.label}</span>
                  <span className={r.bold ? "font-semibold text-foreground" : ""}>{r.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Zuschläge */}
          {totalSurcharges > 0 && (
            <div>
              <div className="text-sm font-medium text-foreground mb-2">Zuschläge (§3b EStG)</div>
              <div className="space-y-1 text-sm">
                {entry.early_hours > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Frühzuschlag ({fmt(entry.early_hours)} h)</span>
                    <span>{eur(entry.early_surcharge)}</span>
                  </div>
                )}
                {entry.late_hours > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Spätdienst ({fmt(entry.late_hours)} h)</span>
                    <span>{eur(entry.late_surcharge)}</span>
                  </div>
                )}
                {entry.night_hours > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Nachtzuschlag ({fmt(entry.night_hours)} h)</span>
                    <span>{eur(entry.night_surcharge)}</span>
                  </div>
                )}
                {entry.weekend_hours > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Samstag ({fmt(entry.weekend_hours)} h)</span>
                    <span>{eur(entry.weekend_surcharge)}</span>
                  </div>
                )}
                {entry.sunday_hours > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Sonntag ({fmt(entry.sunday_hours)} h)</span>
                    <span>{eur(entry.sunday_surcharge)}</span>
                  </div>
                )}
                {entry.holiday_hours > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Feiertag ({fmt(entry.holiday_hours)} h)</span>
                    <span>{eur(entry.holiday_surcharge)}</span>
                  </div>
                )}
                <div className="flex justify-between font-medium border-t border-border pt-1 mt-1">
                  <span>Zuschläge gesamt</span>
                  <span>{eur(totalSurcharges)}</span>
                </div>
              </div>
            </div>
          )}

          {/* Lohnaufteilung (bei Vertragsänderung im Monat) */}
          {entry.wage_details?.splits && entry.wage_details.splits.length > 1 && (
            <div>
              <div className="text-sm font-medium text-foreground mb-2">Lohnaufteilung</div>
              <div className="rounded-lg border border-border overflow-hidden text-sm">
                {entry.wage_details.splits.map((s, i) => (
                  <div key={i} className="flex justify-between px-3 py-2 border-b border-border/50 last:border-0">
                    <span className="text-muted-foreground">
                      {new Date(s.from + "T00:00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}–{new Date(s.to + "T00:00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}
                      {" "}·{" "}{s.rate.toLocaleString("de-DE", { minimumFractionDigits: 2 })} €/h × {fmt(s.hours)} h
                    </span>
                    <span className="font-medium">{eur(s.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Jahressoll-Tracking */}
          {entry.monthly_hours_target != null && entry.monthly_hours_target > 0 && (
            <div>
              <div className="text-sm font-medium text-foreground mb-2">Jahressoll</div>
              {(() => {
                const target = entry.monthly_hours_target!;
                const actual = entry.paid_hours ?? 0;
                const annualTarget = entry.annual_hours_target ?? 0;
                const ytdH = entry.ytd_hours ?? 0;
                const remaining = entry.annual_hours_remaining ?? 0;
                const paidThisYear = ytdH + actual;
                const yearPct = annualTarget > 0 ? Math.min((paidThisYear / annualTarget) * 100, 120) : 0;
                const overYear = remaining < 0;
                const nearYear = !overYear && remaining < annualTarget * 0.05;
                return (
                  <>
                    <div className="grid grid-cols-2 gap-2 text-sm mb-3">
                      <div className="bg-muted/40 rounded-lg px-3 py-2">
                        <div className="text-xs text-muted-foreground mb-0.5">Monatssoll</div>
                        <div className="font-semibold">{fmt(target)} Std.</div>
                      </div>
                      <div className="bg-muted/40 rounded-lg px-3 py-2">
                        <div className="text-xs text-muted-foreground mb-0.5">Tatsächlich</div>
                        <div className="font-semibold" style={{ color: actual < target * 0.9 ? "rgb(var(--ctp-peach))" : "rgb(var(--ctp-green))" }}>
                          {fmt(actual)} Std.
                        </div>
                      </div>
                    </div>
                    {annualTarget > 0 && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs text-muted-foreground mb-1">
                          <span>YTD: {fmt(paidThisYear)} / {fmt(annualTarget)} Std.</span>
                          <span style={{ color: overYear ? "rgb(var(--ctp-red))" : remaining < 50 ? "rgb(var(--ctp-peach))" : undefined }}>
                            Restpuffer: {remaining >= 0 ? "+" : ""}{fmt(remaining)} Std.
                          </span>
                        </div>
                        <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${overYear ? "bg-red-500" : nearYear ? "bg-amber-400" : "bg-emerald-500"}`}
                            style={{ width: `${Math.min(yearPct, 100)}%` }}
                          />
                        </div>
                        <div className="text-xs text-muted-foreground">{fmt(yearPct, 0)}% des Jahrssoll erreicht</div>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          )}

          {/* Minijob Jahresgrenze */}
          {isMinijob && entry.ytd_gross != null && (
            <div>
              <div className="text-sm font-medium text-foreground mb-2">Minijob-Jahresgrenze 2025</div>
              {(overLimit || nearLimit) && (
                <div
                  className="flex items-start gap-2 p-3 rounded-lg text-sm mb-3"
                  style={
                    overLimit
                      ? { backgroundColor: "rgb(var(--ctp-red) / 0.12)", color: "rgb(var(--ctp-red))" }
                      : { backgroundColor: "rgb(var(--ctp-peach) / 0.12)", color: "rgb(var(--ctp-peach))" }
                  }
                >
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <span>
                    {overLimit
                      ? `Jahresgrenze überschritten! Brutto YTD: ${eur(entry.ytd_gross)} (Limit: ${eur(MINIJOB_ANNUAL)})`
                      : `Jahresgrenze fast erreicht. Noch ${eur(entry.annual_limit_remaining ?? 0)} verfügbar.`}
                  </span>
                </div>
              )}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-muted-foreground mb-1">
                  <span>YTD: {eur(entry.ytd_gross)}</span>
                  <span>Limit: {eur(MINIJOB_ANNUAL)}</span>
                </div>
                <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${overLimit ? "bg-red-500" : nearLimit ? "bg-amber-400" : "bg-emerald-500"}`}
                    style={{ width: `${Math.min(ytdPct, 100)}%` }}
                  />
                </div>
                <div className="text-xs text-muted-foreground">
                  {fmt(ytdPct, 0)}% ausgeschöpft · {eur(entry.annual_limit_remaining)} verbleibend
                </div>
              </div>
            </div>
          )}

          {/* Notizen */}
          {entry.status !== "paid" && (
            <div>
              <label className="text-sm font-medium text-foreground block mb-1.5">Notizen</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground resize-none focus:outline-none focus:ring-2"
                style={{ focusRingColor: "rgb(var(--ctp-blue))" } as React.CSSProperties}
                placeholder="Interne Notiz…"
              />
              <button
                onClick={() => updateMutation.mutate({ notes })}
                disabled={updateMutation.isPending || notes === (entry.notes ?? "")}
                className="mt-1.5 text-xs px-3 py-1 rounded-lg border border-border text-muted-foreground hover:bg-muted disabled:opacity-40"
              >
                Notiz speichern
              </button>
            </div>
          )}
          {entry.status === "paid" && entry.notes && (
            <div>
              <div className="text-sm font-medium text-foreground mb-1">Notizen</div>
              <p className="text-sm text-muted-foreground">{entry.notes}</p>
            </div>
          )}

          {/* Aktionsbuttons */}
          <div className="flex flex-col gap-2 pt-1">
            {confirmPending ? (
              <div className="rounded-xl p-4 text-sm space-y-3"
                style={{ backgroundColor: "rgb(var(--ctp-peach) / 0.10)", border: "1px solid rgb(var(--ctp-peach) / 0.30)" }}>
                <div className="flex items-start gap-2" style={{ color: "rgb(var(--ctp-peach))" }}>
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <div>
                    <div className="font-semibold">
                      {confirmPending === "approved" ? "Abrechnung genehmigen?" : "Als bezahlt markieren?"}
                    </div>
                    <div className="text-xs opacity-80 mt-0.5">
                      {confirmPending === "approved"
                        ? `Brutto ${eur(entry.total_gross)} wird festgeschrieben. Dienste sollten danach nicht mehr geändert werden.`
                        : "Dieser Schritt schließt den Monat endgültig ab. Eine Rückbuchung ist nur über Zurücksetzen möglich."}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => { updateMutation.mutate({ status: confirmPending }); setConfirmPending(null); }}
                    disabled={updateMutation.isPending}
                    className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
                    style={{ backgroundColor: confirmPending === "approved" ? "rgb(var(--ctp-green))" : "rgb(var(--ctp-blue))" }}
                  >
                    {confirmPending === "approved" ? "Ja, genehmigen" : "Ja, als bezahlt markieren"}
                  </button>
                  <button
                    onClick={() => setConfirmPending(null)}
                    className="flex-1 py-2 rounded-lg text-sm font-medium border border-border text-muted-foreground hover:bg-muted"
                  >
                    Abbrechen
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2 flex-wrap">
                {entry.status === "draft" && (
                  <button
                    onClick={() => setConfirmPending("approved")}
                    disabled={updateMutation.isPending}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                    style={{ backgroundColor: "rgb(var(--ctp-green))" }}
                  >
                    <Check size={14} /> Genehmigen
                  </button>
                )}
                {entry.status === "approved" && (
                  <>
                    <button
                      onClick={() => setConfirmPending("paid")}
                      disabled={updateMutation.isPending}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                      style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
                    >
                      <Euro size={14} /> Als bezahlt markieren
                    </button>
                    <button
                      onClick={() => updateMutation.mutate({ status: "draft" })}
                      disabled={updateMutation.isPending}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border border-border text-muted-foreground hover:bg-muted disabled:opacity-50"
                    >
                      <RotateCcw size={14} /> Zurücksetzen
                    </button>
                  </>
                )}
                {entry.status === "paid" && (
                  <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <CheckCircle size={16} style={{ color: "rgb(var(--ctp-green))" }} />
                    Abrechnung abgeschlossen
                  </div>
                )}
                {entry.status !== "draft" && (
                  <button
                    onClick={handleDownloadPdf}
                    disabled={pdfLoading}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border border-border text-muted-foreground hover:bg-muted disabled:opacity-50"
                  >
                    {pdfLoading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                    PDF
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── EmployeeRow ──────────────────────────────────────────────────── */
function EmployeeRow({
  entry,
  employee,
  onCalculate,
  calculating,
  onClick,
}: {
  entry: PayrollEntry;
  employee: Employee | undefined;
  onCalculate: () => void;
  calculating: boolean;
  onClick: () => void;
}) {
  const isMinijob = employee?.contract_type === "minijob";
  const hasJahressoll = (entry.monthly_hours_target ?? 0) > 0;
  const ytdPct = entry.ytd_gross != null ? Math.min((entry.ytd_gross / MINIJOB_ANNUAL) * 100, 100) : 0;
  const overLimit = (entry.ytd_gross ?? 0) > MINIJOB_ANNUAL;
  const nearLimit = !overLimit && ytdPct >= 90;
  const annualTarget = entry.annual_hours_target ?? 0;
  const paidThisYear = (entry.ytd_hours ?? 0) + (entry.paid_hours ?? 0);
  const yearHoursPct = annualTarget > 0 ? Math.min((paidThisYear / annualTarget) * 100, 100) : 0;
  const overYearH = (entry.annual_hours_remaining ?? 0) < 0;
  const nearYearH = !overYearH && yearHoursPct >= 95;

  return (
    <div
      onClick={onClick}
      className="flex items-center gap-3 p-3 rounded-xl border border-border hover:bg-muted/50 cursor-pointer transition-colors"
    >
      {/* Avatar */}
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 text-white"
        style={{ backgroundColor: "rgb(var(--ctp-mauve))" }}
      >
        {employee ? employee.first_name[0] + employee.last_name[0] : "?"}
      </div>

      {/* Name + Typ */}
      <div className="min-w-0 flex-1">
        <div className="font-medium text-foreground text-sm truncate">
          {employee ? `${employee.first_name} ${employee.last_name}` : entry.employee_id.slice(0, 8)}
        </div>
        <div className="text-xs text-muted-foreground capitalize">{employee?.contract_type ?? "–"}</div>
      </div>

      {/* Stunden */}
      <div className="hidden sm:block text-right shrink-0 w-20">
        <div className="text-sm font-medium text-foreground">{hrs(entry.paid_hours)}</div>
        {hasJahressoll ? (
          <div className="mt-0.5">
            <div className="h-1 rounded-full bg-muted overflow-hidden w-20 ml-auto">
              <div
                className={`h-full rounded-full ${overYearH ? "bg-red-500" : nearYearH ? "bg-amber-400" : "bg-emerald-500"}`}
                style={{ width: `${yearHoursPct}%` }}
              />
            </div>
            <div className={`text-xs mt-0.5 ${overYearH ? "text-red-500" : nearYearH ? "text-amber-500" : "text-muted-foreground"}`}>
              {overYearH ? "Über Soll!" : `${fmt(yearHoursPct, 0)}% Soll`}
            </div>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground">Stunden</div>
        )}
      </div>

      {/* Brutto */}
      <div className="text-right shrink-0 w-24">
        <div className="text-sm font-semibold text-foreground">{eur(entry.total_gross)}</div>
        {isMinijob && entry.ytd_gross != null && (
          <div className="mt-0.5">
            <div className="h-1 rounded-full bg-muted overflow-hidden w-20 ml-auto">
              <div
                className={`h-full rounded-full ${overLimit ? "bg-red-500" : nearLimit ? "bg-amber-400" : "bg-emerald-500"}`}
                style={{ width: `${ytdPct}%` }}
              />
            </div>
            <div className={`text-xs mt-0.5 ${overLimit ? "text-red-500" : nearLimit ? "text-amber-500" : "text-muted-foreground"}`}>
              {overLimit ? "Limit!" : `${fmt(ytdPct, 0)}% YTD`}
            </div>
          </div>
        )}
      </div>

      {/* Status */}
      <div className="shrink-0">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[entry.status]}`}>
          {STATUS_LABELS[entry.status]}
        </span>
      </div>

      {/* Neu berechnen */}
      {entry.status === "draft" && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCalculate();
          }}
          disabled={calculating}
          className="shrink-0 p-1.5 rounded-lg hover:bg-muted text-muted-foreground disabled:opacity-40"
          title="Neu berechnen"
        >
          <Calculator size={14} />
        </button>
      )}
    </div>
  );
}

/* ── PayrollPage ──────────────────────────────────────────────────── */
export default function PayrollPage() {
  const { user } = useAuthStore();
  const qc = useQueryClient();

  const [month, setMonth] = useState(() => {
    const d = new Date();
    d.setDate(1);
    return d.toISOString().slice(0, 10); // YYYY-MM-01
  });
  const [selectedEntry, setSelectedEntry] = useState<PayrollEntry | null>(null);
  const [calculatingAll, setCalculatingAll] = useState(false);
  const [calculatingId, setCalculatingId] = useState<string | null>(null);

  const isPrivileged = user?.role === "admin" || user?.role === "manager";
  const isEmployee = user?.role === "employee";

  const { data: entries = [], isLoading } = useQuery<PayrollEntry[]>({
    queryKey: ["payroll", month],
    queryFn: async () => {
      const res = await payrollApi.list({ month });
      return res.data;
    },
    enabled: !!user,
  });

  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: async () => {
      const res = await employeesApi.list(true);
      return res.data;
    },
    enabled: isPrivileged,
  });

  const empMap = Object.fromEntries(employees.map((e) => [e.id, e]));

  // Summary stats
  const totalGross = entries.reduce((s, e) => s + (e.total_gross ?? 0), 0);
  const totalHours = entries.reduce((s, e) => s + (e.paid_hours ?? 0), 0);
  const countApproved = entries.filter((e) => e.status === "approved").length;
  const countPaid = entries.filter((e) => e.status === "paid").length;

  const calcAllMutation = useMutation({
    mutationFn: () => payrollApi.calculateAll(month),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payroll", month] });
      toast.success("Alle Abrechnungen berechnet");
      setCalculatingAll(false);
    },
    onError: () => {
      toast.error("Fehler beim Berechnen");
      setCalculatingAll(false);
    },
  });

  const calcOneMutation = useMutation({
    mutationFn: ({ employee_id }: { employee_id: string }) =>
      payrollApi.calculate({ employee_id, month }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payroll", month] });
      toast.success("Abrechnung neu berechnet");
      setCalculatingId(null);
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Fehler");
      setCalculatingId(null);
    },
  });

  function changeMonth(delta: number) {
    const d = new Date(month + "T00:00:00");
    d.setMonth(d.getMonth() + delta);
    d.setDate(1);
    setMonth(d.toISOString().slice(0, 10));
  }

  const monthLabel = new Date(month + "T00:00:00").toLocaleDateString("de-DE", {
    month: "long",
    year: "numeric",
  });

  if (isEmployee) {
    // Employee self-service: own payslips, read-only with download
    const ownEntry = entries[0] ?? null;
    return (
      <div className="space-y-5">
        {/* Header with month nav */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h1 className="text-2xl font-bold text-foreground">Meine Abrechnung</h1>
          <div className="flex items-center gap-1 bg-card border border-border rounded-xl px-1 py-1">
            <button onClick={() => changeMonth(-1)} className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground">
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm font-medium text-foreground px-2 min-w-[120px] text-center">{monthLabel}</span>
            <button onClick={() => changeMonth(1)} className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground">
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {isLoading && (
          <div className="text-center py-12 text-muted-foreground text-sm">Lade…</div>
        )}

        {!isLoading && !ownEntry && (
          <div className="bg-card rounded-xl border border-border p-10 text-center">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.12)", color: "rgb(var(--ctp-blue))" }}>
              <Euro size={28} />
            </div>
            <div className="font-medium text-foreground mb-1">Keine Abrechnung für {monthLabel}</div>
            <p className="text-sm text-muted-foreground">Die Abrechnung für diesen Monat wurde noch nicht erstellt.</p>
          </div>
        )}

        {!isLoading && ownEntry && (
          <div className="bg-card rounded-xl border border-border p-5 space-y-5">
            {/* Status header */}
            <div className="flex items-center justify-between">
              <div>
                <div className="text-lg font-semibold text-foreground">{monthLabel}</div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[ownEntry.status]}`}>
                  {STATUS_LABELS[ownEntry.status]}
                </span>
              </div>
              {ownEntry.status !== "draft" && (
                <EmployeePdfButton entry={ownEntry} />
              )}
            </div>

            {/* Key figures */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-muted/50 rounded-xl p-3 text-center">
                <div className="text-xs text-muted-foreground mb-1">Bezahlte Std.</div>
                <div className="font-semibold text-foreground">{hrs(ownEntry.paid_hours)}</div>
              </div>
              <div className="bg-muted/50 rounded-xl p-3 text-center">
                <div className="text-xs text-muted-foreground mb-1">Grundlohn</div>
                <div className="font-semibold text-foreground">{eur(ownEntry.base_wage)}</div>
              </div>
              <div className="rounded-xl p-3 text-center"
                style={{ backgroundColor: "rgb(var(--ctp-green) / 0.12)", color: "rgb(var(--ctp-green))" }}>
                <div className="text-xs opacity-75 mb-1">Brutto gesamt</div>
                <div className="font-bold text-lg">{eur(ownEntry.total_gross)}</div>
              </div>
            </div>

            {/* Hours breakdown */}
            <div>
              <div className="text-sm font-medium text-foreground mb-2">Stunden</div>
              <div className="space-y-1 text-sm">
                {[
                  { label: "Geplant (Soll)", value: hrs(ownEntry.planned_hours) },
                  { label: "Ist-Zeit", value: hrs(ownEntry.actual_hours) },
                  { label: "Übertrag Vormonat", value: hrs(ownEntry.carryover_hours) },
                  { label: "Bezahlte Stunden", value: hrs(ownEntry.paid_hours), bold: true },
                ].map((r) => (
                  <div key={r.label} className="flex justify-between">
                    <span className={r.bold ? "font-medium text-foreground" : "text-muted-foreground"}>{r.label}</span>
                    <span className={r.bold ? "font-semibold text-foreground" : ""}>{r.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Surcharges */}
            {(ownEntry.early_surcharge + ownEntry.late_surcharge + ownEntry.night_surcharge +
              ownEntry.weekend_surcharge + ownEntry.sunday_surcharge + ownEntry.holiday_surcharge) > 0 && (
              <div>
                <div className="text-sm font-medium text-foreground mb-2">Zuschläge (§3b EStG)</div>
                <div className="space-y-1 text-sm">
                  {ownEntry.early_hours > 0 && <div className="flex justify-between"><span className="text-muted-foreground">Frühzuschlag ({fmt(ownEntry.early_hours)} h)</span><span>{eur(ownEntry.early_surcharge)}</span></div>}
                  {ownEntry.late_hours > 0 && <div className="flex justify-between"><span className="text-muted-foreground">Spätdienst ({fmt(ownEntry.late_hours)} h)</span><span>{eur(ownEntry.late_surcharge)}</span></div>}
                  {ownEntry.night_hours > 0 && <div className="flex justify-between"><span className="text-muted-foreground">Nachtzuschlag ({fmt(ownEntry.night_hours)} h)</span><span>{eur(ownEntry.night_surcharge)}</span></div>}
                  {ownEntry.weekend_hours > 0 && <div className="flex justify-between"><span className="text-muted-foreground">Samstag ({fmt(ownEntry.weekend_hours)} h)</span><span>{eur(ownEntry.weekend_surcharge)}</span></div>}
                  {ownEntry.sunday_hours > 0 && <div className="flex justify-between"><span className="text-muted-foreground">Sonntag ({fmt(ownEntry.sunday_hours)} h)</span><span>{eur(ownEntry.sunday_surcharge)}</span></div>}
                  {ownEntry.holiday_hours > 0 && <div className="flex justify-between"><span className="text-muted-foreground">Feiertag ({fmt(ownEntry.holiday_hours)} h)</span><span>{eur(ownEntry.holiday_surcharge)}</span></div>}
                </div>
              </div>
            )}

            {/* Jahressoll (eigene Ansicht) */}
            {(ownEntry.monthly_hours_target ?? 0) > 0 && (() => {
              const annual = ownEntry.annual_hours_target ?? 0;
              const paidY = (ownEntry.ytd_hours ?? 0) + (ownEntry.paid_hours ?? 0);
              const yearPct = annual > 0 ? Math.min((paidY / annual) * 100, 100) : 0;
              const over = (ownEntry.annual_hours_remaining ?? 0) < 0;
              return (
                <div>
                  <div className="text-sm font-medium text-foreground mb-2">Jahressoll</div>
                  <div className="space-y-1 text-sm mb-2">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Monatssoll</span>
                      <span>{fmt(ownEntry.monthly_hours_target)} Std.</span>
                    </div>
                    {annual > 0 && (
                      <>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Jahressoll gesamt</span>
                          <span>{fmt(annual)} Std.</span>
                        </div>
                        <div className="flex justify-between font-medium">
                          <span className="text-muted-foreground">Geleistet YTD</span>
                          <span>{fmt(paidY)} Std.</span>
                        </div>
                        <div className="flex justify-between" style={{ color: over ? "rgb(var(--ctp-red))" : "rgb(var(--ctp-green))" }}>
                          <span>Restpuffer</span>
                          <span>{(ownEntry.annual_hours_remaining ?? 0) >= 0 ? "+" : ""}{fmt(ownEntry.annual_hours_remaining)} Std.</span>
                        </div>
                      </>
                    )}
                  </div>
                  {annual > 0 && (
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full ${over ? "bg-red-500" : yearPct >= 95 ? "bg-amber-400" : "bg-emerald-500"}`}
                        style={{ width: `${yearPct}%` }}
                      />
                    </div>
                  )}
                </div>
              );
            })()}

            {ownEntry.notes && (
              <div>
                <div className="text-sm font-medium text-foreground mb-1">Notizen</div>
                <p className="text-sm text-muted-foreground">{ownEntry.notes}</p>
              </div>
            )}
          </div>
        )}

        <div className="rounded-xl p-4 text-sm"
          style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.08)", color: "rgb(var(--ctp-blue))" }}>
          <div className="font-medium mb-1">Berechnungsgrundlage</div>
          <ul className="list-disc list-inside space-y-0.5 opacity-85">
            <li>Nur bestätigte & abgeschlossene Dienste fließen ein</li>
            <li>Zuschläge gem. §3b EStG (Nacht, Sonn- u. Feiertag steuerfrei)</li>
            <li>PDF-Download verfügbar sobald Abrechnung genehmigt ist</li>
          </ul>
        </div>
      </div>
    );
  }

  // Missing employees (active, no entry yet for this month)
  const missingEmployees = employees.filter(
    (emp) => !entries.find((e) => e.employee_id === emp.id)
  );

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-2xl font-bold text-foreground">Abrechnung</h1>
        <div className="flex items-center gap-2">
          {/* Month nav */}
          <div className="flex items-center gap-1 bg-card border border-border rounded-xl px-1 py-1">
            <button
              onClick={() => changeMonth(-1)}
              className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm font-medium text-foreground px-2 min-w-[120px] text-center">
              {monthLabel}
            </span>
            <button
              onClick={() => changeMonth(1)}
              className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground"
            >
              <ChevronRight size={16} />
            </button>
          </div>

          {/* CSV Export */}
          {entries.length > 0 && (
            <button
              onClick={() => {
                const header = ["Mitarbeiter", "Monat", "Stunden", "Grundlohn", "Zuschläge", "Brutto", "Status"];
                const rows = entries.map((e) => {
                  const emp = empMap[e.employee_id];
                  const name = emp ? `${emp.last_name} ${emp.first_name}` : e.employee_id;
                  const surcharges = (e.early_surcharge ?? 0) + (e.late_surcharge ?? 0) +
                    (e.night_surcharge ?? 0) + (e.weekend_surcharge ?? 0) +
                    (e.sunday_surcharge ?? 0) + (e.holiday_surcharge ?? 0);
                  return [
                    name,
                    e.month.slice(0, 7),
                    (e.paid_hours ?? 0).toFixed(2).replace(".", ","),
                    (e.base_wage ?? 0).toFixed(2).replace(".", ","),
                    surcharges.toFixed(2).replace(".", ","),
                    (e.total_gross ?? 0).toFixed(2).replace(".", ","),
                    e.status,
                  ];
                });
                const bom = "\uFEFF";
                const content = bom + [header, ...rows].map(r =>
                  r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(";")
                ).join("\r\n");
                const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `abrechnung_${monthLabel.replace(" ", "_")}.csv`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border border-border text-muted-foreground hover:bg-accent transition-colors"
            >
              <Download size={14} />
              <span className="hidden sm:inline">CSV</span>
            </button>
          )}

          {/* Calculate all */}
          <button
            onClick={() => {
              setCalculatingAll(true);
              calcAllMutation.mutate();
            }}
            disabled={calculatingAll || calcAllMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
          >
            <Calculator size={14} />
            <span className="hidden sm:inline">Alle berechnen</span>
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: "Lohnsumme",
            value: eur(totalGross),
            icon: <Euro size={16} />,
            color: "var(--ctp-green)",
          },
          {
            label: "Stunden",
            value: hrs(totalHours),
            icon: <Clock size={16} />,
            color: "var(--ctp-blue)",
          },
          {
            label: "Genehmigt",
            value: `${countApproved} / ${entries.length}`,
            icon: <CheckCircle size={16} />,
            color: "var(--ctp-teal)",
          },
          {
            label: "Bezahlt",
            value: `${countPaid} / ${entries.length}`,
            icon: <TrendingUp size={16} />,
            color: "var(--ctp-mauve)",
          },
        ].map((card) => (
          <div key={card.label} className="bg-card rounded-xl border border-border p-4">
            <div className="flex items-center gap-2 mb-2">
              <span style={{ color: `rgb(${card.color})` }}>{card.icon}</span>
              <span className="text-xs text-muted-foreground">{card.label}</span>
            </div>
            <div className="text-lg font-bold text-foreground">{card.value}</div>
          </div>
        ))}
      </div>

      {/* Status pipeline */}
      {entries.length > 0 && (
        <div className="bg-card rounded-xl border border-border px-4 py-3 flex items-center gap-6 text-sm">
          <span className="text-muted-foreground font-medium shrink-0">Status:</span>
          {(["draft", "approved", "paid"] as const).map((s) => {
            const count = entries.filter((e) => e.status === s).length;
            return (
              <div key={s} className="flex items-center gap-1.5">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[s]}`}>
                  {STATUS_LABELS[s]}
                </span>
                <span className="text-foreground font-semibold">{count}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Employee list */}
      <div className="space-y-2">
        {isLoading && (
          <div className="text-center py-12 text-muted-foreground text-sm">Lade Abrechnungen…</div>
        )}

        {!isLoading && entries.length === 0 && (
          <div className="bg-card rounded-xl border border-border p-10 text-center">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.12)", color: "rgb(var(--ctp-blue))" }}
            >
              <Users size={28} />
            </div>
            <div className="font-medium text-foreground mb-1">Keine Abrechnungen für {monthLabel}</div>
            <p className="text-sm text-muted-foreground mb-4">
              Klicke auf „Alle berechnen" um Abrechnungen für alle aktiven Mitarbeiter zu erstellen.
            </p>
            <button
              onClick={() => {
                setCalculatingAll(true);
                calcAllMutation.mutate();
              }}
              disabled={calculatingAll}
              className="px-4 py-2 rounded-xl text-sm font-medium text-white"
              style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
            >
              <Calculator size={14} className="inline mr-1.5" />
              Alle berechnen
            </button>
          </div>
        )}

        {entries.map((entry) => (
          <EmployeeRow
            key={entry.id}
            entry={entry}
            employee={empMap[entry.employee_id]}
            calculating={calculatingId === entry.employee_id}
            onCalculate={() => {
              setCalculatingId(entry.employee_id);
              calcOneMutation.mutate({ employee_id: entry.employee_id });
            }}
            onClick={() => setSelectedEntry(entry)}
          />
        ))}

        {/* Missing employees (no entry yet) */}
        {missingEmployees.length > 0 && entries.length > 0 && (
          <div className="pt-2">
            <div className="text-xs text-muted-foreground mb-1.5 px-1">Noch keine Abrechnung:</div>
            {missingEmployees.map((emp) => (
              <div
                key={emp.id}
                className="flex items-center gap-3 p-3 rounded-xl border border-dashed border-border opacity-60"
              >
                <div
                  className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 text-white"
                  style={{ backgroundColor: "rgb(var(--ctp-overlay0))" }}
                >
                  {emp.first_name[0] + emp.last_name[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm text-foreground">
                    {emp.first_name} {emp.last_name}
                  </div>
                  <div className="text-xs text-muted-foreground capitalize">{emp.contract_type}</div>
                </div>
                <button
                  onClick={() => {
                    setCalculatingId(emp.id);
                    calcOneMutation.mutate({ employee_id: emp.id });
                  }}
                  disabled={calculatingId === emp.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-muted text-muted-foreground disabled:opacity-40"
                >
                  <Calculator size={12} /> Berechnen
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Info box */}
      <div
        className="rounded-xl p-4 text-sm"
        style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.08)", color: "rgb(var(--ctp-blue))" }}
      >
        <div className="font-medium mb-1">Berechnungsgrundlage</div>
        <ul className="list-disc list-inside space-y-0.5 opacity-85">
          <li>Nur bestätigte & abgeschlossene Dienste fließen ein</li>
          <li>Zuschläge gem. §3b EStG (Nacht, Sonn- u. Feiertag steuerfrei)</li>
          <li>Minijob-Grenze 2025: 556 €/Monat · 6.672 €/Jahr</li>
          <li>Urlaubsanspruch wird gem. §11 BUrlG (Referenzzeitraum) vergütet</li>
        </ul>
      </div>

      {/* Detail modal */}
      {selectedEntry && (
        <DetailModal
          entry={selectedEntry}
          employee={empMap[selectedEntry.employee_id]}
          onClose={() => setSelectedEntry(null)}
        />
      )}
    </div>
  );
}
