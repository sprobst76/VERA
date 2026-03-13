"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { absencesApi, employeesApi, careAbsencesApi } from "@/lib/api";
import { format, parseISO, addDays, differenceInCalendarDays, getYear } from "date-fns";
import { de } from "date-fns/locale";
import { CalendarOff, Plus, X, Check, Ban, Clock, Umbrella, Heart, Trash2, Info } from "lucide-react";
import toast from "react-hot-toast";
import { useAuthStore } from "@/store/auth";

// ── Constants ─────────────────────────────────────────────────────────────────

const ABSENCE_TYPES = [
  { value: "vacation",        label: "Urlaub" },
  { value: "sick",            label: "Krank" },
  { value: "school_holiday",  label: "Schulferien" },
  { value: "other",           label: "Sonstiges" },
];

const TYPE_STYLE: Record<string, React.CSSProperties> = {
  vacation:       { color: "rgb(var(--ctp-blue))",   backgroundColor: "rgb(var(--ctp-blue) / 0.12)" },
  sick:           { color: "rgb(var(--ctp-red))",    backgroundColor: "rgb(var(--ctp-red) / 0.12)" },
  school_holiday: { color: "rgb(var(--ctp-teal))",   backgroundColor: "rgb(var(--ctp-teal) / 0.12)" },
  other:          { color: "rgb(var(--ctp-overlay1))", backgroundColor: "rgb(var(--ctp-surface1) / 0.5)" },
};

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  pending:  { color: "rgb(var(--ctp-yellow))",  backgroundColor: "rgb(var(--ctp-yellow) / 0.12)" },
  approved: { color: "rgb(var(--ctp-green))",   backgroundColor: "rgb(var(--ctp-green) / 0.12)" },
  rejected: { color: "rgb(var(--ctp-red))",     backgroundColor: "rgb(var(--ctp-red) / 0.12)" },
};

const STATUS_LABELS: Record<string, string> = {
  pending:  "Ausstehend",
  approved: "Genehmigt",
  rejected: "Abgelehnt",
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending:  <Clock size={11} />,
  approved: <Check size={11} />,
  rejected: <Ban size={11} />,
};

// Count working days (Mo–Fr) in range
function countWorkdays(from: string, to: string): number {
  if (!from || !to) return 0;
  let count = 0;
  let d = new Date(from);
  const end = new Date(to);
  while (d <= end) {
    const dow = d.getDay();
    if (dow !== 0 && dow !== 6) count++;
    d = addDays(d, 1);
  }
  return count;
}

const CARE_TYPES = [
  { value: "vacation",  label: "Urlaub" },
  { value: "rehab",     label: "Reha" },
  { value: "hospital",  label: "Krankenhaus" },
  { value: "sick",      label: "Krank" },
  { value: "other",     label: "Sonstiges" },
];

const HANDLING_OPTIONS = [
  { value: "cancelled_unpaid", label: "Dienste stornieren (unbezahlt)" },
  { value: "carry_over",       label: "Dienste beibehalten (Übertrag)" },
  { value: "paid_anyway",      label: "Dienste beibehalten (bezahlt)" },
];

const CARE_TYPE_STYLE: Record<string, React.CSSProperties> = {
  vacation:  { color: "rgb(var(--ctp-blue))",   backgroundColor: "rgb(var(--ctp-blue) / 0.12)" },
  rehab:     { color: "rgb(var(--ctp-mauve))",  backgroundColor: "rgb(var(--ctp-mauve) / 0.12)" },
  hospital:  { color: "rgb(var(--ctp-red))",    backgroundColor: "rgb(var(--ctp-red) / 0.12)" },
  sick:      { color: "rgb(var(--ctp-peach))",  backgroundColor: "rgb(var(--ctp-peach) / 0.12)" },
  other:     { color: "rgb(var(--ctp-overlay1))", backgroundColor: "rgb(var(--ctp-surface1) / 0.5)" },
};

// ── Care Absence Modal ────────────────────────────────────────────────────────

function CareAbsenceModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [type, setType] = useState("vacation");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [description, setDescription] = useState("");
  const [handling, setHandling] = useState("cancelled_unpaid");
  const [notifyEmployees, setNotifyEmployees] = useState(true);

  const createMutation = useMutation({
    mutationFn: () => careAbsencesApi.create({
      type, start_date: startDate, end_date: endDate,
      description: description || null,
      shift_handling: handling,
      notify_employees: notifyEmployees,
    }),
    onSuccess: () => { toast.success("Abwesenheit eingetragen"); onCreated(); },
    onError: () => toast.error("Fehler beim Speichern"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-xl w-full max-w-md border border-border">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-base font-semibold text-foreground">Abwesenheit betreute Person</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-accent rounded-lg transition-colors">
            <X size={16} />
          </button>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Art</label>
              <select value={type} onChange={e => setType(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50">
                {CARE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Dienstbehandlung</label>
              <select value={handling} onChange={e => setHandling(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50">
                {HANDLING_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Von *</label>
              <input type="date" required value={startDate} onChange={e => setStartDate(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Bis *</label>
              <input type="date" required value={endDate} min={startDate} onChange={e => setEndDate(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Beschreibung</label>
            <input type="text" value={description} onChange={e => setDescription(e.target.value)}
              placeholder="z.B. Reha Bad Kreuznach"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
          </div>
          <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
            <input type="checkbox" checked={notifyEmployees} onChange={e => setNotifyEmployees(e.target.checked)}
              className="rounded border-border" />
            Mitarbeiter benachrichtigen
          </label>
          {handling === "cancelled_unpaid" && startDate && endDate && (
            <div className="rounded-lg px-3 py-2 text-xs" style={{ backgroundColor: "rgb(var(--ctp-yellow) / 0.1)", color: "rgb(var(--ctp-yellow))" }}>
              Alle Dienste im Zeitraum werden automatisch storniert.
            </div>
          )}
          <button
            onClick={() => createMutation.mutate()}
            disabled={!startDate || !endDate || createMutation.isPending}
            className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {createMutation.isPending ? "Wird gespeichert…" : "Abwesenheit eintragen"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Create Modal ──────────────────────────────────────────────────────────────

interface CreateModalProps {
  employees: any[];
  ownEmployeeId: string | null;
  isAdmin: boolean;
  onClose: () => void;
  onCreated: () => void;
}

function CreateModal({ employees, ownEmployeeId, isAdmin, onClose, onCreated }: CreateModalProps) {
  const [empId,     setEmpId]     = useState(isAdmin ? "" : (ownEmployeeId ?? ""));
  const [type,      setType]      = useState("vacation");
  const [startDate, setStartDate] = useState(format(new Date(), "yyyy-MM-dd"));
  const [endDate,   setEndDate]   = useState(format(new Date(), "yyyy-MM-dd"));
  const [daysCount, setDaysCount] = useState<number | "">("");
  const [notes,     setNotes]     = useState("");

  const suggestedDays = countWorkdays(startDate, endDate);

  const createMutation = useMutation({
    mutationFn: () =>
      absencesApi.create({
        employee_id: empId,
        type,
        start_date: startDate,
        end_date: endDate,
        days_count: daysCount !== "" ? daysCount : suggestedDays || undefined,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      toast.success(isAdmin ? "Abwesenheit eingetragen" : "Antrag gestellt – wartet auf Genehmigung");
      onCreated();
    },
    onError: (err: any) =>
      toast.error(err?.response?.data?.detail ?? "Fehler beim Speichern"),
  });

  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";
  const labelCls = "block text-xs font-medium text-muted-foreground mb-1";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-md" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-4">
          <h2 className="text-lg font-semibold text-foreground">
            {isAdmin ? "Abwesenheit eintragen" : "Abwesenheitsantrag stellen"}
          </h2>
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground">
            <X size={18} />
          </button>
        </div>

        <div className="px-5 pb-5 space-y-3">
          {/* Employee – admin only */}
          {isAdmin && (
            <div>
              <label className={labelCls}>Mitarbeiter *</label>
              <select className={inputCls} value={empId} onChange={e => setEmpId(e.target.value)}>
                <option value="">– Mitarbeiter wählen –</option>
                {employees.map((e: any) => (
                  <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Type */}
          <div>
            <label className={labelCls}>Art der Abwesenheit *</label>
            <div className="grid grid-cols-2 gap-2">
              {ABSENCE_TYPES.map(t => (
                <button
                  key={t.value}
                  onClick={() => setType(t.value)}
                  className="px-3 py-2 rounded-lg border text-sm font-medium transition-colors text-left"
                  style={
                    type === t.value
                      ? { ...TYPE_STYLE[t.value], borderColor: "transparent" }
                      : { borderColor: "rgb(var(--border))", color: "rgb(var(--muted-foreground))" }
                  }
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Date range */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Von *</label>
              <input type="date" className={inputCls} value={startDate}
                onChange={e => { setStartDate(e.target.value); if (e.target.value > endDate) setEndDate(e.target.value); }} />
            </div>
            <div>
              <label className={labelCls}>Bis *</label>
              <input type="date" className={inputCls} value={endDate} min={startDate}
                onChange={e => setEndDate(e.target.value)} />
            </div>
          </div>

          {/* Days count */}
          <div>
            <label className={labelCls}>
              Urlaubstage (Arbeitstage)
              {suggestedDays > 0 && (
                <span className="ml-1 text-muted-foreground font-normal">
                  · Vorschlag: {suggestedDays} Werktage
                </span>
              )}
            </label>
            <input
              type="number" min={0} step={0.5} placeholder={String(suggestedDays)}
              className={inputCls} value={daysCount}
              onChange={e => setDaysCount(e.target.value === "" ? "" : Number(e.target.value))}
            />
          </div>

          {/* Verrechnung hint */}
          {(type === "vacation" || type === "sick") && (
            <div className="flex gap-2 rounded-lg px-3 py-2.5 text-xs"
              style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.08)", color: "rgb(var(--ctp-blue))" }}>
              <Info size={14} className="shrink-0 mt-0.5" />
              <span>
                {type === "vacation"
                  ? "Urlaub: Bei Genehmigung werden Dienste auf cancelled_absence gesetzt. Urlaubsentgelt (§11 BUrlG) fließt in die Abrechnung ein."
                  : "Krank: Entgeltfortzahlung 100% für 6 Wochen (§3 EFZG), zählt zur Minijob-Grenze."}
              </span>
            </div>
          )}

          {/* Notes */}
          <div>
            <label className={labelCls}>Notiz</label>
            <textarea className={`${inputCls} resize-none`} rows={2}
              value={notes} onChange={e => setNotes(e.target.value)} placeholder="optional" />
          </div>

          <button
            onClick={() => createMutation.mutate()}
            disabled={!empId || !startDate || !endDate || createMutation.isPending}
            className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {createMutation.isPending ? "Wird gespeichert…" : "Abwesenheit eintragen"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type ActiveTab = "employees" | "care";

export default function AbsencesPage() {
  const { user } = useAuthStore();
  const isAdmin = user?.role === "admin";
  const isPrivileged = user?.role === "admin" || user?.role === "manager";
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<ActiveTab>("employees");
  const [showCreate, setShowCreate] = useState(false);
  const [showCareCreate, setShowCareCreate] = useState(false);
  const [filterEmployee, setFilterEmployee] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const currentYear = getYear(new Date());

  const { data: absences = [], isLoading } = useQuery({
    queryKey: ["absences", filterEmployee, filterStatus],
    queryFn: () => absencesApi.list({
      employee_id: filterEmployee || undefined,
      status: filterStatus || undefined,
    }).then(r => r.data),
  });

  const { data: employees = [] } = useQuery({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list().then(r => r.data),
  });

  // Own employee profile (for non-admin: to get employee_id + vacation_days)
  const { data: ownProfile } = useQuery({
    queryKey: ["employees", "me"],
    queryFn: () => employeesApi.me().then(r => r.data),
  });

  // Vacation balances (admin: all employees; employee: own via same endpoint)
  const { data: vacationBalances = [] } = useQuery({
    queryKey: ["vacation-balances", currentYear],
    queryFn: () => employeesApi.vacationBalances(currentYear).then(r => r.data),
  });

  const empMap = Object.fromEntries((employees as any[]).map((e: any) => [e.id, e]));

  // user_id → Anzeigename (für approved_by-Lookup)
  const approverMap: Record<string, string> = {};
  (employees as any[]).forEach((e: any) => {
    if (e.user_id) approverMap[e.user_id] = `${e.first_name} ${e.last_name}`;
  });

  const { data: careAbsences = [], isLoading: careLoading } = useQuery({
    queryKey: ["care-absences"],
    queryFn: () => careAbsencesApi.list().then(r => r.data),
    enabled: isPrivileged,
  });

  const deleteCareAbsenceMutation = useMutation({
    mutationFn: (id: string) => careAbsencesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["care-absences"] });
      qc.invalidateQueries({ queryKey: ["shifts"] });
      toast.success("Abwesenheit gelöscht");
    },
    onError: () => toast.error("Fehler beim Löschen"),
  });

  const approveMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      absencesApi.update(id, { status }),
    onSuccess: (_, { status }) => {
      qc.invalidateQueries({ queryKey: ["absences"] });
      qc.invalidateQueries({ queryKey: ["shifts"] });
      toast.success(status === "approved" ? "Genehmigt – Dienste storniert" : "Abgelehnt");
    },
    onError: () => toast.error("Fehler"),
  });

  // Vacation balance for non-admin
  const usedVacationDays = (absences as any[])
    .filter((a: any) => a.type === "vacation" && a.status === "approved")
    .reduce((sum: number, a: any) => {
      const days = a.days_count ?? differenceInCalendarDays(parseISO(a.end_date), parseISO(a.start_date)) + 1;
      return sum + days;
    }, 0);
  const totalVacationDays = (ownProfile as any)?.vacation_days ?? 0;
  const remainingVacationDays = totalVacationDays - usedVacationDays;

  const handleCreated = () => {
    setShowCreate(false);
    qc.invalidateQueries({ queryKey: ["absences"] });
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold text-foreground flex-1">Abwesenheiten</h1>

        {/* Tab switcher (admin only) */}
        {isPrivileged && (
          <div className="flex gap-1 rounded-lg border border-border p-1">
            <button
              onClick={() => setActiveTab("employees")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${activeTab === "employees" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"}`}
            >
              Mitarbeiter
            </button>
            <button
              onClick={() => setActiveTab("care")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${activeTab === "care" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"}`}
            >
              <Heart size={12} /> Betreute Person
            </button>
          </div>
        )}

        {/* Employee filter (admin/manager, employees tab only) */}
        {isPrivileged && activeTab === "employees" && (
          <select
            value={filterEmployee}
            onChange={e => setFilterEmployee(e.target.value)}
            className="text-sm border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Alle Mitarbeiter</option>
            {(employees as any[]).map((e: any) => (
              <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>
            ))}
          </select>
        )}

        {/* Status-Filter (employees tab only) */}
        {isPrivileged && activeTab === "employees" && (
          <div className="flex gap-1 rounded-lg border border-border p-1">
            {([["", "Alle"], ["pending", "Ausstehend"], ["approved", "Genehmigt"], ["rejected", "Abgelehnt"]] as [string, string][]).map(([v, l]) => (
              <button
                key={v}
                onClick={() => setFilterStatus(v)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${filterStatus === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"}`}
              >
                {l}
              </button>
            ))}
          </div>
        )}

        {activeTab === "employees" ? (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
          >
            <Plus size={16} />
            <span className="hidden sm:inline">Abwesenheit eintragen</span>
          </button>
        ) : isPrivileged ? (
          <button
            onClick={() => setShowCareCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
          >
            <Plus size={16} />
            <span className="hidden sm:inline">Abwesenheit eintragen</span>
          </button>
        ) : null}
      </div>

      {activeTab === "employees" && <>

      {/* Admin: Vacation balances overview */}
      {isPrivileged && (vacationBalances as any[]).length > 0 && (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-3 border-b border-border">
            <Umbrella size={15} style={{ color: "rgb(var(--ctp-blue))" }} />
            <h2 className="text-sm font-semibold text-foreground">Urlaubskonten {currentYear}</h2>
          </div>
          <div className="divide-y divide-border">
            {(vacationBalances as any[]).map((b: any) => {
              const pct = b.entitlement > 0 ? Math.min(100, (b.taken / b.entitlement) * 100) : 0;
              const color = b.remaining <= 3
                ? "rgb(var(--ctp-red))"
                : b.remaining <= 7
                  ? "rgb(var(--ctp-yellow))"
                  : "rgb(var(--ctp-teal))";
              return (
                <div key={b.employee_id} className="flex items-center gap-4 px-5 py-2.5">
                  <div className="w-32 shrink-0 text-sm font-medium text-foreground truncate">
                    {b.first_name} {b.last_name}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="w-full rounded-full h-1.5" style={{ backgroundColor: "rgb(var(--ctp-surface1))" }}>
                      <div
                        className="h-1.5 rounded-full transition-all"
                        style={{ width: `${pct}%`, backgroundColor: color }}
                      />
                    </div>
                  </div>
                  <div className="text-sm tabular-nums shrink-0 text-right w-24">
                    <span className="font-semibold" style={{ color }}>{b.remaining}</span>
                    <span className="text-muted-foreground"> / {b.entitlement} Tage</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Vacation balance (employees only: own) */}
      {!isPrivileged && totalVacationDays > 0 && (
        <div className="bg-card rounded-xl border border-border px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-foreground">Urlaubskonto</span>
            <span className="text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">{remainingVacationDays}</span> / {totalVacationDays} Tage verbleibend
            </span>
          </div>
          <div className="w-full rounded-full h-2" style={{ backgroundColor: "rgb(var(--ctp-surface1))" }}>
            <div
              className="h-2 rounded-full transition-all"
              style={{
                width: `${Math.min(100, (usedVacationDays / totalVacationDays) * 100)}%`,
                backgroundColor: remainingVacationDays <= 3
                  ? "rgb(var(--ctp-red))"
                  : "rgb(var(--ctp-blue))",
              }}
            />
          </div>
          <div className="flex justify-between mt-1 text-xs text-muted-foreground">
            <span>{usedVacationDays} Tage genommen</span>
            <span>{remainingVacationDays} Tage frei</span>
          </div>
        </div>
      )}

      {/* List */}
      {isLoading ? (
        <div className="text-muted-foreground text-sm py-8 text-center">Lade Abwesenheiten…</div>
      ) : (absences as any[]).length === 0 ? (
        <div className="bg-card rounded-xl border border-border p-8 text-center space-y-3">
          <CalendarOff size={32} className="mx-auto text-muted-foreground" />
          <p className="text-muted-foreground">Keine Abwesenheiten eingetragen</p>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
          >
            <Plus size={15} /> Erste Abwesenheit eintragen
          </button>
        </div>
      ) : (
        <div className="bg-card rounded-xl border border-border divide-y divide-border">
          {(absences as any[]).map((a: any) => {
            const emp = empMap[a.employee_id];
            const days = a.days_count
              ?? differenceInCalendarDays(parseISO(a.end_date), parseISO(a.start_date)) + 1;
            const typeLabel = ABSENCE_TYPES.find(t => t.value === a.type)?.label ?? a.type;

            return (
              <div key={a.id} className="flex items-center gap-3 px-4 py-3 flex-wrap sm:flex-nowrap">
                {/* Type badge */}
                <span
                  className="text-xs px-2 py-0.5 rounded-full font-medium shrink-0"
                  style={TYPE_STYLE[a.type] ?? TYPE_STYLE.other}
                >
                  {typeLabel}
                </span>

                {/* Name + dates */}
                <div className="flex-1 min-w-0">
                  {isPrivileged && (
                    <div className="text-sm font-medium text-foreground">
                      {emp ? `${emp.first_name} ${emp.last_name}` : "–"}
                    </div>
                  )}
                  <div className="text-xs text-muted-foreground">
                    {format(parseISO(a.start_date), "d. MMM", { locale: de })} –{" "}
                    {format(parseISO(a.end_date), "d. MMM yyyy", { locale: de })}
                    {" · "}
                    <span className="text-foreground font-medium">{days} Tage</span>
                  </div>
                  {a.notes && (
                    <div className="text-xs text-muted-foreground mt-0.5 truncate">{a.notes}</div>
                  )}
                </div>

                {/* Status badge + Genehmiger-Info */}
                <div className="flex flex-col items-end gap-0.5 shrink-0">
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-medium flex items-center gap-1"
                    style={STATUS_STYLE[a.status] ?? STATUS_STYLE.pending}
                  >
                    {STATUS_ICONS[a.status]}
                    {STATUS_LABELS[a.status] ?? a.status}
                  </span>
                  {a.approved_by && a.status !== "pending" && (
                    <div className="text-xs text-muted-foreground">
                      {a.status === "approved" ? "von" : "abgel."}{" "}
                      {approverMap[a.approved_by] ?? "Admin"}
                      {a.approved_at && `, ${format(parseISO(a.approved_at), "d. MMM", { locale: de })}`}
                    </div>
                  )}
                </div>

                {/* Approve / Reject (admin/manager, pending only) */}
                {isPrivileged && a.status === "pending" && (
                  <div className="flex gap-1 shrink-0">
                    <button
                      onClick={() => approveMutation.mutate({ id: a.id, status: "approved" })}
                      disabled={approveMutation.isPending}
                      title="Genehmigen"
                      className="p-2 rounded hover:bg-accent transition-colors"
                      style={{ color: "rgb(var(--ctp-green))" }}
                    >
                      <Check size={16} />
                    </button>
                    <button
                      onClick={() => approveMutation.mutate({ id: a.id, status: "rejected" })}
                      disabled={approveMutation.isPending}
                      title="Ablehnen"
                      className="p-2 rounded hover:bg-accent transition-colors"
                      style={{ color: "rgb(var(--ctp-red))" }}
                    >
                      <X size={16} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <CreateModal
          employees={employees as any[]}
          ownEmployeeId={(ownProfile as any)?.id ?? null}
          isAdmin={isPrivileged}
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}

      </> /* end activeTab === "employees" */}

      {/* ── Care Absences Tab ──────────────────────────────────────────── */}
      {activeTab === "care" && isPrivileged && (
        <>
          {careLoading ? (
            <div className="text-muted-foreground text-sm py-8 text-center">Lade Abwesenheiten…</div>
          ) : (careAbsences as any[]).length === 0 ? (
            <div className="bg-card rounded-xl border border-border p-8 text-center space-y-3">
              <Heart size={32} className="mx-auto text-muted-foreground" />
              <p className="text-muted-foreground">Keine Abwesenheiten eingetragen</p>
              <button
                onClick={() => setShowCareCreate(true)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
              >
                <Plus size={15} /> Erste Abwesenheit eintragen
              </button>
            </div>
          ) : (
            <div className="bg-card rounded-xl border border-border divide-y divide-border">
              {(careAbsences as any[]).map((a: any) => {
                const days = differenceInCalendarDays(parseISO(a.end_date), parseISO(a.start_date)) + 1;
                const typeLabel = CARE_TYPES.find(t => t.value === a.type)?.label ?? a.type;
                const handlingLabel = HANDLING_OPTIONS.find(o => o.value === a.shift_handling)?.label ?? a.shift_handling;
                return (
                  <div key={a.id} className="flex items-center gap-3 px-4 py-3 flex-wrap sm:flex-nowrap">
                    <span
                      className="text-xs px-2 py-0.5 rounded-full font-medium shrink-0"
                      style={CARE_TYPE_STYLE[a.type] ?? CARE_TYPE_STYLE.other}
                    >
                      {typeLabel}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-foreground">
                        {format(parseISO(a.start_date), "d. MMM", { locale: de })} –{" "}
                        {format(parseISO(a.end_date), "d. MMM yyyy", { locale: de })}
                        <span className="text-muted-foreground font-normal"> · {days} Tage</span>
                      </div>
                      {a.description && (
                        <div className="text-xs text-muted-foreground mt-0.5">{a.description}</div>
                      )}
                      <div className="text-xs text-muted-foreground mt-0.5">{handlingLabel}</div>
                    </div>
                    <button
                      onClick={() => {
                        if (confirm("Abwesenheit löschen?")) deleteCareAbsenceMutation.mutate(a.id);
                      }}
                      title="Löschen"
                      className="p-2 rounded hover:bg-accent transition-colors shrink-0"
                      style={{ color: "rgb(var(--ctp-red))" }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {showCareCreate && (
            <CareAbsenceModal
              onClose={() => setShowCareCreate(false)}
              onCreated={() => {
                setShowCareCreate(false);
                qc.invalidateQueries({ queryKey: ["care-absences"] });
                qc.invalidateQueries({ queryKey: ["shifts"] });
              }}
            />
          )}
        </>
      )}
    </div>
  );
}
