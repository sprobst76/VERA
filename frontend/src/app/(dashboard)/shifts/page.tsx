"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { shiftsApi, employeesApi, templatesApi } from "@/lib/api";
import { format, startOfMonth, endOfMonth, parseISO } from "date-fns";
import { de } from "date-fns/locale";
import { Plus, Trash2, ChevronLeft, ChevronRight, AlertCircle, X, Check, Clock, Pencil } from "lucide-react";
import toast from "react-hot-toast";
import { useAuthStore } from "@/store/auth";
import { CreateShiftModal } from "@/components/shared/CreateShiftModal";

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  planned:            "Geplant",
  confirmed:          "Bestätigt",
  completed:          "Abgeschlossen",
  cancelled:          "Storniert",
  cancelled_absence:  "Storniert (Abwesenheit)",
};

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  planned:           { color: "rgb(var(--ctp-blue))",     backgroundColor: "rgb(var(--ctp-blue) / 0.12)" },
  confirmed:         { color: "rgb(var(--ctp-green))",    backgroundColor: "rgb(var(--ctp-green) / 0.12)" },
  completed:         { color: "rgb(var(--ctp-overlay1))", backgroundColor: "rgb(var(--ctp-surface1) / 0.6)" },
  cancelled:         { color: "rgb(var(--ctp-red))",      backgroundColor: "rgb(var(--ctp-red) / 0.12)" },
  cancelled_absence: { color: "rgb(var(--ctp-red))",      backgroundColor: "rgb(var(--ctp-red) / 0.12)" },
};

type StatusFilter = "open" | "confirmed" | "completed" | "all";

const FILTER_LABELS: { key: StatusFilter; label: string }[] = [
  { key: "open",      label: "Offen" },
  { key: "confirmed", label: "Bestätigt" },
  { key: "completed", label: "Abgeschlossen" },
  { key: "all",       label: "Alle" },
];

const FILTER_STATUSES: Record<StatusFilter, string[]> = {
  open:      ["planned"],
  confirmed: ["confirmed"],
  completed: ["completed", "cancelled", "cancelled_absence"],
  all:       [],
};

// ── Confirm Modal ─────────────────────────────────────────────────────────────

function ConfirmModal({ shift, onClose, onDone }: { shift: any; onClose: () => void; onDone: () => void }) {
  const [actualStart, setActualStart] = useState(shift.actual_start?.slice(0, 5) ?? shift.start_time?.slice(0, 5) ?? "");
  const [actualEnd,   setActualEnd]   = useState(shift.actual_end?.slice(0, 5) ?? shift.end_time?.slice(0, 5) ?? "");
  const [note,        setNote]        = useState("");

  const confirmMutation = useMutation({
    mutationFn: () =>
      shiftsApi.confirm(shift.id, {
        actual_start: actualStart || undefined,
        actual_end: actualEnd || undefined,
        confirmation_note: note || undefined,
      }),
    onSuccess: () => { toast.success("Dienst bestätigt"); onDone(); },
    onError:   () => toast.error("Fehler beim Bestätigen"),
  });

  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";
  const labelCls = "block text-xs font-medium text-muted-foreground mb-1";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="text-base font-semibold text-foreground">Dienst bestätigen</h2>
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground"><X size={16} /></button>
        </div>
        <div className="px-5 pb-5 space-y-3">
          <p className="text-sm text-muted-foreground">
            Geplant: {shift.start_time?.slice(0,5)} – {shift.end_time?.slice(0,5)} Uhr
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Ist-Zeit von</label>
              <input type="time" className={inputCls} value={actualStart} onChange={e => setActualStart(e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>Ist-Zeit bis</label>
              <input type="time" className={inputCls} value={actualEnd} onChange={e => setActualEnd(e.target.value)} />
            </div>
          </div>
          <div>
            <label className={labelCls}>Bestätigungsnotiz</label>
            <input type="text" className={inputCls} value={note} onChange={e => setNote(e.target.value)} placeholder="optional" />
          </div>
          <button
            onClick={() => confirmMutation.mutate()}
            disabled={confirmMutation.isPending}
            className="w-full py-2.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-green))", color: "white" }}
          >
            {confirmMutation.isPending ? "Wird bestätigt…" : "Dienst bestätigen"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Actual Time Modal (for employees) ────────────────────────────────────────

function ActualTimeModal({ shift, onClose, onDone }: { shift: any; onClose: () => void; onDone: () => void }) {
  const [actualStart, setActualStart] = useState(shift.actual_start?.slice(0, 5) ?? "");
  const [actualEnd,   setActualEnd]   = useState(shift.actual_end?.slice(0, 5) ?? "");
  const [notes,       setNotes]       = useState(shift.notes ?? "");

  const updateMutation = useMutation({
    mutationFn: () =>
      shiftsApi.update(shift.id, {
        actual_start: actualStart || undefined,
        actual_end: actualEnd || undefined,
        notes: notes || undefined,
      }),
    onSuccess: () => { toast.success("Ist-Zeiten gespeichert"); onDone(); },
    onError: (err: any) => toast.error(err?.response?.data?.detail ?? "Fehler"),
  });

  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";
  const labelCls = "block text-xs font-medium text-muted-foreground mb-1";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="text-base font-semibold text-foreground">Ist-Zeiten eintragen</h2>
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground"><X size={16} /></button>
        </div>
        <div className="px-5 pb-5 space-y-3">
          <p className="text-sm text-muted-foreground">
            Geplant: {shift.start_time?.slice(0,5)} – {shift.end_time?.slice(0,5)} Uhr
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Tatsächlich von</label>
              <input type="time" className={inputCls} value={actualStart} onChange={e => setActualStart(e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>Tatsächlich bis</label>
              <input type="time" className={inputCls} value={actualEnd} onChange={e => setActualEnd(e.target.value)} />
            </div>
          </div>
          <div>
            <label className={labelCls}>Notiz</label>
            <input type="text" className={inputCls} value={notes} onChange={e => setNotes(e.target.value)} placeholder="optional" />
          </div>
          <button
            onClick={() => updateMutation.mutate()}
            disabled={updateMutation.isPending}
            className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {updateMutation.isPending ? "Wird gespeichert…" : "Zeiten speichern"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function ShiftsPage() {
  const { user } = useAuthStore();
  const isPrivileged = user?.role === "admin" || user?.role === "manager";
  const qc = useQueryClient();

  const [month,          setMonth]          = useState(new Date());
  const [filterEmployee, setFilterEmployee] = useState("");
  const [statusFilter,   setStatusFilter]   = useState<StatusFilter>("open");
  const [showCreate,     setShowCreate]     = useState(false);
  const [confirmShift,   setConfirmShift]   = useState<any>(null);
  const [actualShift,    setActualShift]    = useState<any>(null);

  const monthStart = format(startOfMonth(month), "yyyy-MM-dd");
  const monthEnd   = format(endOfMonth(month), "yyyy-MM-dd");

  const { data: shifts = [], isLoading } = useQuery({
    queryKey: ["shifts", monthStart, monthEnd, filterEmployee],
    queryFn: () =>
      shiftsApi.list({ from_date: monthStart, to_date: monthEnd, employee_id: filterEmployee || undefined })
        .then(r => r.data),
  });

  const { data: employees = [] } = useQuery({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list().then(r => r.data),
  });

  const { data: templates = [] } = useQuery({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then(r => r.data),
  });

  const { data: ownProfile } = useQuery({
    queryKey: ["employees", "me"],
    queryFn: () => import("@/lib/api").then(m => m.employeesApi.me()).then(r => r.data),
    enabled: !isPrivileged,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => shiftsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["shifts"] }); toast.success("Dienst gelöscht"); },
    onError:   () => toast.error("Löschen fehlgeschlagen"),
  });

  const templateMap = Object.fromEntries((templates as any[]).map((t: any) => [t.id, t]));
  const employeeMap = Object.fromEntries((employees as any[]).map((e: any) => [e.id, e]));

  const prevMonth = () => setMonth(m => { const d = new Date(m); d.setMonth(d.getMonth() - 1); return d; });
  const nextMonth = () => setMonth(m => { const d = new Date(m); d.setMonth(d.getMonth() + 1); return d; });

  // Apply status filter client-side
  const allowedStatuses = FILTER_STATUSES[statusFilter];
  const filteredShifts = allowedStatuses.length > 0
    ? (shifts as any[]).filter((s: any) => allowedStatuses.includes(s.status))
    : (shifts as any[]);

  const grouped = filteredShifts.reduce((acc: Record<string, any[]>, s: any) => {
    (acc[s.date] ??= []).push(s);
    return acc;
  }, {});
  const sortedDates = Object.keys(grouped).sort();

  const handleCreated = () => { setShowCreate(false); qc.invalidateQueries({ queryKey: ["shifts"] }); };
  const handleConfirmed = () => { setConfirmShift(null); qc.invalidateQueries({ queryKey: ["shifts"] }); };
  const handleActualSaved = () => { setActualShift(null); qc.invalidateQueries({ queryKey: ["shifts"] }); };

  return (
    <div className="space-y-4">

      {/* ── Header ── */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold text-foreground flex-1">Dienste</h1>

        {/* Month nav */}
        <div className="flex items-center gap-1 bg-card rounded-lg border border-border p-1">
          <button onClick={prevMonth} className="p-2.5 hover:bg-accent rounded"><ChevronLeft size={16} /></button>
          <span className="px-3 text-sm font-medium text-foreground min-w-[120px] text-center">
            {format(month, "MMMM yyyy", { locale: de })}
          </span>
          <button onClick={nextMonth} className="p-2.5 hover:bg-accent rounded"><ChevronRight size={16} /></button>
        </div>

        {/* Employee filter – privileged only */}
        {isPrivileged && (
          <select value={filterEmployee} onChange={e => setFilterEmployee(e.target.value)}
            className="text-sm border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring">
            <option value="">Alle Mitarbeiter</option>
            {(employees as any[]).map((e: any) => (
              <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>
            ))}
          </select>
        )}

        {/* New shift – privileged only */}
        {isPrivileged && (
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity">
            <Plus size={16} />
            <span className="hidden sm:inline">Neuer Dienst</span>
          </button>
        )}
      </div>

      {/* ── Status filter chips ── */}
      <div className="flex gap-2 flex-wrap">
        {FILTER_LABELS.map(({ key, label }) => (
          <button key={key} onClick={() => setStatusFilter(key)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${
              statusFilter === key
                ? "bg-primary text-primary-foreground border-transparent"
                : "border-border text-muted-foreground hover:bg-accent"
            }`}>
            {label}
            {key !== "all" && (
              <span className="ml-1.5 opacity-70">
                {(shifts as any[]).filter((s: any) =>
                  FILTER_STATUSES[key].length > 0
                    ? FILTER_STATUSES[key].includes(s.status)
                    : true
                ).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Summary bar ── */}
      <div className="flex gap-4 text-sm">
        <span className="text-muted-foreground">
          <span className="font-semibold text-foreground">{filteredShifts.length}</span> Dienste
        </span>
        {statusFilter === "open" && (
          <span className="text-muted-foreground">
            <span className="font-semibold text-foreground">
              {filteredShifts.filter((s: any) => !s.employee_id).length}
            </span> unbesetzt
          </span>
        )}
        <span className="text-muted-foreground">
          Stunden:{" "}
          <span className="font-semibold text-foreground">
            {filteredShifts.reduce((sum: number, s: any) => {
              const start = new Date(`2000-01-01T${s.start_time}`);
              const end   = new Date(`2000-01-01T${s.end_time}`);
              return sum + (end.getTime() - start.getTime()) / 3600000 - (s.break_minutes ?? 0) / 60;
            }, 0).toFixed(1)}
          </span>
        </span>
      </div>

      {/* ── Shift list ── */}
      {isLoading ? (
        <div className="text-muted-foreground text-sm py-8 text-center">Lade Dienste…</div>
      ) : sortedDates.length === 0 ? (
        <div className="bg-card rounded-xl border border-border p-8 text-center space-y-3">
          <p className="text-muted-foreground">Keine Dienste in diesem Zeitraum</p>
          {isPrivileged && statusFilter === "open" && (
            <button onClick={() => setShowCreate(true)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity">
              <Plus size={15} /> Ersten Dienst anlegen
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {sortedDates.map(date => (
            <div key={date}>
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1 px-1">
                {format(parseISO(date), "EEEE, d. MMMM", { locale: de })}
              </div>
              <div className="bg-card rounded-xl border border-border divide-y divide-border">
                {grouped[date].map((shift: any) => {
                  const tpl = templateMap[shift.template_id];
                  const emp = employeeMap[shift.employee_id];
                  const isOwnShift = !isPrivileged && ownProfile && shift.employee_id === (ownProfile as any).id;
                  const hasActualTime = shift.actual_start || shift.actual_end;

                  return (
                    <div key={shift.id} className="flex items-center gap-2 px-3 py-3 sm:px-4">
                      {/* Template color dot */}
                      <span className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: tpl?.color ?? "rgb(var(--ctp-overlay1))" }} />

                      {/* Main content */}
                      <div className="flex-1 min-w-0">
                        {/* Row 1: planned time + template name + status */}
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-foreground shrink-0">
                            {shift.start_time?.slice(0,5)} – {shift.end_time?.slice(0,5)}
                          </span>
                          <span className="text-sm text-foreground truncate">{tpl?.name ?? "–"}</span>
                          <span className="text-xs px-2 py-0.5 rounded-full font-medium shrink-0 hidden sm:inline"
                            style={STATUS_STYLE[shift.status] ?? STATUS_STYLE.planned}>
                            {STATUS_LABELS[shift.status] ?? shift.status}
                          </span>
                        </div>

                        {/* Row 2: employee + actual time (if differs) */}
                        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                          <span className="text-xs text-muted-foreground truncate">
                            {emp ? `${emp.first_name} ${emp.last_name}` : (
                              <span className="flex items-center gap-1" style={{ color: "rgb(var(--ctp-red))" }}>
                                <AlertCircle size={12} /> Offen
                              </span>
                            )}
                          </span>
                          {/* Ist-Zeit anzeigen wenn vorhanden */}
                          {hasActualTime && (
                            <span className="text-xs shrink-0 flex items-center gap-1"
                              style={{ color: "rgb(var(--ctp-teal))" }}>
                              <Clock size={10} />
                              Ist: {shift.actual_start?.slice(0,5) ?? "–"} – {shift.actual_end?.slice(0,5) ?? "–"}
                            </span>
                          )}
                          {/* Bestätigt von */}
                          {shift.status === "confirmed" && shift.confirmed_at && (
                            <span className="text-xs text-muted-foreground shrink-0 hidden md:inline">
                              ✓ {format(parseISO(shift.confirmed_at), "d.M. HH:mm")}
                            </span>
                          )}
                          {/* Status badge mobile */}
                          <span className="text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0 sm:hidden"
                            style={STATUS_STYLE[shift.status] ?? STATUS_STYLE.planned}>
                            {STATUS_LABELS[shift.status] ?? shift.status}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 shrink-0">
                        {/* Bestätigen-Button (admin/manager, nur planned) */}
                        {isPrivileged && shift.status === "planned" && (
                          <button onClick={() => setConfirmShift(shift)}
                            title="Dienst bestätigen"
                            className="p-2.5 rounded hover:bg-accent transition-colors"
                            style={{ color: "rgb(var(--ctp-green))" }}>
                            <Check size={15} />
                          </button>
                        )}

                        {/* Ist-Zeit eintragen (eigener Dienst, vor Bestätigung) */}
                        {isOwnShift && shift.status === "planned" && (
                          <button onClick={() => setActualShift(shift)}
                            title="Ist-Zeiten eintragen"
                            className="p-2.5 rounded hover:bg-accent transition-colors text-muted-foreground">
                            <Pencil size={14} />
                          </button>
                        )}

                        {/* Löschen (nur privileged, nur planned) */}
                        {isPrivileged && shift.status === "planned" && (
                          <button
                            onClick={() => { if (confirm("Dienst wirklich löschen?")) deleteMutation.mutate(shift.id); }}
                            className="p-2.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Modals ── */}
      {showCreate && (
        <CreateShiftModal
          templates={templates as any[]}
          employees={employees as any[]}
          defaultDate={monthStart}
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}
      {confirmShift && (
        <ConfirmModal shift={confirmShift} onClose={() => setConfirmShift(null)} onDone={handleConfirmed} />
      )}
      {actualShift && (
        <ActualTimeModal shift={actualShift} onClose={() => setActualShift(null)} onDone={handleActualSaved} />
      )}
    </div>
  );
}
