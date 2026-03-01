"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { shiftsApi, employeesApi, templatesApi, recurringShiftsApi, holidayProfilesApi } from "@/lib/api";
import { format, startOfMonth, endOfMonth, parseISO } from "date-fns";
import { de } from "date-fns/locale";
import { Plus, Trash2, ChevronLeft, ChevronRight, AlertCircle, X, Check, Clock, Pencil, RepeatIcon } from "lucide-react";
import { TimeInput } from "@/components/shared/TimeInput";
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

const WEEKDAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];

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

const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";
const labelCls = "block text-xs font-medium text-muted-foreground mb-1";

// ── Confirm Modal ─────────────────────────────────────────────────────────────

function ConfirmModal({ shift, onClose, onDone }: { shift: any; onClose: () => void; onDone: () => void }) {
  const [actualStart, setActualStart] = useState(shift.actual_start?.slice(0, 5) ?? shift.start_time?.slice(0, 5) ?? "");
  const [actualEnd,   setActualEnd]   = useState(shift.actual_end?.slice(0, 5) ?? shift.end_time?.slice(0, 5) ?? "");
  const [note,        setNote]        = useState("");

  const confirmMutation = useMutation({
    mutationFn: () => shiftsApi.confirm(shift.id, {
      actual_start: actualStart || undefined, actual_end: actualEnd || undefined, confirmation_note: note || undefined,
    }),
    onSuccess: () => { toast.success("Dienst bestätigt"); onDone(); },
    onError:   () => toast.error("Fehler beim Bestätigen"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="text-base font-semibold text-foreground">Dienst bestätigen</h2>
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground"><X size={16} /></button>
        </div>
        <div className="px-5 pb-5 space-y-3">
          <p className="text-sm text-muted-foreground">Geplant: {shift.start_time?.slice(0,5)} – {shift.end_time?.slice(0,5)} Uhr</p>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Ist-Zeit von</label><TimeInput value={actualStart} onChange={setActualStart} /></div>
            <div><label className={labelCls}>Ist-Zeit bis</label><TimeInput value={actualEnd} onChange={setActualEnd} /></div>
          </div>
          <div><label className={labelCls}>Bestätigungsnotiz</label><input type="text" className={inputCls} value={note} onChange={e => setNote(e.target.value)} placeholder="optional" /></div>
          <button onClick={() => confirmMutation.mutate()} disabled={confirmMutation.isPending}
            className="w-full py-2.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-green))", color: "white" }}>
            {confirmMutation.isPending ? "Wird bestätigt…" : "Dienst bestätigen"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Actual Time Modal ─────────────────────────────────────────────────────────

function ActualTimeModal({ shift, onClose, onDone }: { shift: any; onClose: () => void; onDone: () => void }) {
  const [actualStart, setActualStart] = useState(shift.actual_start?.slice(0, 5) ?? "");
  const [actualEnd,   setActualEnd]   = useState(shift.actual_end?.slice(0, 5) ?? "");
  const [notes,       setNotes]       = useState(shift.notes ?? "");

  const updateMutation = useMutation({
    mutationFn: () => shiftsApi.update(shift.id, {
      actual_start: actualStart || undefined, actual_end: actualEnd || undefined, notes: notes || undefined,
    }),
    onSuccess: () => { toast.success("Ist-Zeiten gespeichert"); onDone(); },
    onError: (err: any) => toast.error(err?.response?.data?.detail ?? "Fehler"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="text-base font-semibold text-foreground">Ist-Zeiten eintragen</h2>
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground"><X size={16} /></button>
        </div>
        <div className="px-5 pb-5 space-y-3">
          <p className="text-sm text-muted-foreground">Geplant: {shift.start_time?.slice(0,5)} – {shift.end_time?.slice(0,5)} Uhr</p>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Tatsächlich von</label><TimeInput value={actualStart} onChange={setActualStart} /></div>
            <div><label className={labelCls}>Tatsächlich bis</label><TimeInput value={actualEnd} onChange={setActualEnd} /></div>
          </div>
          <div><label className={labelCls}>Notiz</label><input type="text" className={inputCls} value={notes} onChange={e => setNotes(e.target.value)} placeholder="optional" /></div>
          <button onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending}
            className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
            {updateMutation.isPending ? "Wird gespeichert…" : "Zeiten speichern"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Create Recurring Shift Modal ──────────────────────────────────────────────

function CreateRecurringShiftModal({ employees, templates, profiles, onClose, onDone }: {
  employees: any[]; templates: any[]; profiles: any[]; onClose: () => void; onDone: () => void;
}) {
  const [weekday,     setWeekday]     = useState(0);
  const [startTime,   setStartTime]   = useState("08:00");
  const [endTime,     setEndTime]     = useState("13:00");
  const [breakMin,    setBreakMin]    = useState(0);
  const [employeeId,  setEmployeeId]  = useState("");
  const [templateId,  setTemplateId]  = useState("");
  const [validFrom,   setValidFrom]   = useState("");
  const [validUntil,  setValidUntil]  = useState("");
  const [profileId,   setProfileId]   = useState("");
  const [skipHols,    setSkipHols]    = useState(true);
  const [label,       setLabel]       = useState("");
  const [preview,     setPreview]     = useState<{ generated_count: number; skipped_count: number } | null>(null);
  const [previewing,  setPreviewing]  = useState(false);

  // Auto-preview when inputs change
  useEffect(() => {
    if (!validFrom || !validUntil) { setPreview(null); return; }
    const timer = setTimeout(async () => {
      setPreviewing(true);
      try {
        const res = await recurringShiftsApi.preview({
          weekday, valid_from: validFrom, valid_until: validUntil,
          holiday_profile_id: profileId || null, skip_public_holidays: skipHols,
        });
        setPreview(res.data);
      } catch { setPreview(null); }
      finally { setPreviewing(false); }
    }, 600);
    return () => clearTimeout(timer);
  }, [weekday, validFrom, validUntil, profileId, skipHols]);

  const createMut = useMutation({
    mutationFn: () => recurringShiftsApi.create({
      weekday, start_time: startTime, end_time: endTime, break_minutes: breakMin,
      employee_id: employeeId || null, template_id: templateId || null,
      valid_from: validFrom, valid_until: validUntil,
      holiday_profile_id: profileId || null, skip_public_holidays: skipHols,
      label: label || null,
    }),
    onSuccess: (res) => {
      const d = res.data;
      toast.success(`Regeltermin erstellt – ${d.generated_count} Dienste generiert (${d.skipped_count} übersprungen)`);
      onDone();
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || "Fehler"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3 sticky top-0 bg-card border-b border-border">
          <h2 className="font-semibold text-foreground flex items-center gap-2"><RepeatIcon size={16} />Neuer Regeltermin</h2>
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground"><X size={16} /></button>
        </div>
        <div className="px-5 py-4 space-y-4">

          {/* Basic */}
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className={labelCls}>Wochentag</label>
              <select className={inputCls} value={weekday} onChange={e => setWeekday(+e.target.value)}>
                {WEEKDAY_NAMES.map((n, i) => <option key={i} value={i}>{n}</option>)}
              </select>
            </div>
            <div><label className={labelCls}>Von</label><TimeInput value={startTime} onChange={setStartTime} /></div>
            <div><label className={labelCls}>Bis</label><TimeInput value={endTime} onChange={setEndTime} /></div>
            <div><label className={labelCls}>Pause (Min)</label><input type="number" className={inputCls} value={breakMin} onChange={e => setBreakMin(+e.target.value)} min={0} /></div>
            <div><label className={labelCls}>Bezeichnung</label><input className={inputCls} value={label} onChange={e => setLabel(e.target.value)} placeholder="optional" /></div>
          </div>

          {/* Employee + Template */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Mitarbeiter</label>
              <select className={inputCls} value={employeeId} onChange={e => setEmployeeId(e.target.value)}>
                <option value="">Offen</option>
                {employees.map((e: any) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Vorlage</label>
              <select className={inputCls} value={templateId} onChange={e => setTemplateId(e.target.value)}>
                <option value="">–</option>
                {templates.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          </div>

          {/* Valid range */}
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Gültig von</label><input type="date" className={inputCls} value={validFrom} onChange={e => setValidFrom(e.target.value)} /></div>
            <div><label className={labelCls}>Gültig bis</label><input type="date" className={inputCls} value={validUntil} onChange={e => setValidUntil(e.target.value)} /></div>
          </div>

          {/* Holiday profile */}
          <div>
            <label className={labelCls}>Ferienprofil</label>
            <select className={inputCls} value={profileId} onChange={e => setProfileId(e.target.value)}>
              <option value="">Aktives Profil (automatisch)</option>
              {profiles.map((p: any) => <option key={p.id} value={p.id}>{p.name}{p.is_active ? " ✓" : ""}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
            <input type="checkbox" checked={skipHols} onChange={e => setSkipHols(e.target.checked)} className="rounded" />
            Gesetzliche Feiertage (BW) überspringen
          </label>

          {/* Preview */}
          {(preview || previewing) && (
            <div className="rounded-lg px-3 py-2.5 text-sm"
              style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.1)", color: "rgb(var(--ctp-blue))" }}>
              {previewing ? "Berechne Vorschau…" : (
                <>
                  <span className="font-semibold">{preview!.generated_count}</span> Dienste werden erstellt,{" "}
                  <span className="font-semibold">{preview!.skipped_count}</span> übersprungen
                </>
              )}
            </div>
          )}

          <button onClick={() => createMut.mutate()}
            disabled={!validFrom || !validUntil || createMut.isPending}
            className="w-full py-2.5 rounded-lg text-white text-sm font-medium disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
            {createMut.isPending ? "Wird erstellt…" : "Regeltermin erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Update From Modal ─────────────────────────────────────────────────────────

function UpdateFromModal({ rs, employees, onClose, onDone }: { rs: any; employees: any[]; onClose: () => void; onDone: () => void }) {
  const [fromDate,    setFromDate]   = useState("");
  const [validUntil,  setValidUntil] = useState(rs.valid_until ?? "");
  const [startTime,   setStartTime]  = useState(rs.start_time?.slice(0, 5) ?? "");
  const [endTime,     setEndTime]    = useState(rs.end_time?.slice(0, 5) ?? "");
  const [employeeId,  setEmployeeId] = useState(rs.employee_id ?? "");

  const mut = useMutation({
    mutationFn: () => recurringShiftsApi.updateFrom(rs.id, {
      from_date: fromDate,
      valid_until: validUntil || undefined,
      start_time: startTime || undefined,
      end_time: endTime || undefined,
      employee_id: employeeId || null,
    }),
    onSuccess: (res) => {
      const d = res.data;
      toast.success(`Ab ${fromDate}: ${d.generated_count} Dienste neu generiert`);
      onDone();
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || "Fehler"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="font-semibold text-foreground">Ab Datum ändern</h2>
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground"><X size={16} /></button>
        </div>
        <div className="px-5 pb-5 space-y-3">
          <p className="text-xs text-muted-foreground">
            Geplante (nicht bestätigte) Dienste ab dem gewählten Datum werden neu generiert. Bestätigte Dienste bleiben erhalten.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Ab Datum</label><input type="date" className={inputCls} value={fromDate} onChange={e => setFromDate(e.target.value)} /></div>
            <div>
              <label className={labelCls}>Bis (Enddatum)</label>
              <input type="date" className={inputCls} value={validUntil} onChange={e => setValidUntil(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={labelCls}>Von (Uhrzeit)</label><TimeInput value={startTime} onChange={setStartTime} /></div>
            <div><label className={labelCls}>Bis (Uhrzeit)</label><TimeInput value={endTime} onChange={setEndTime} /></div>
          </div>
          <div>
            <label className={labelCls}>Mitarbeiter</label>
            <select className={inputCls} value={employeeId} onChange={e => setEmployeeId(e.target.value)}>
              <option value="">Offen</option>
              {employees.map((e: any) => <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>)}
            </select>
          </div>
          <button onClick={() => mut.mutate()} disabled={!fromDate || mut.isPending}
            className="w-full py-2.5 rounded-lg text-white text-sm font-medium disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-peach))" }}>
            {mut.isPending ? "Wird aktualisiert…" : "Neu generieren"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Regeltermine Tab ──────────────────────────────────────────────────────────

function RegeltermineTab({ employees, templates }: { employees: any[]; templates: any[] }) {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [updateFromRs, setUpdateFromRs] = useState<any>(null);

  const { data: recurringShifts = [], isLoading } = useQuery({
    queryKey: ["recurring-shifts"],
    queryFn: () => recurringShiftsApi.list().then(r => r.data),
  });

  const { data: profiles = [] } = useQuery({
    queryKey: ["holiday-profiles"],
    queryFn: () => holidayProfilesApi.list().then(r => r.data),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => recurringShiftsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["recurring-shifts"] }); qc.invalidateQueries({ queryKey: ["shifts"] }); toast.success("Regeltermin deaktiviert"); },
    onError: () => toast.error("Fehler beim Löschen"),
  });

  const empMap = Object.fromEntries(employees.map((e: any) => [e.id, e]));
  const tplMap = Object.fromEntries(templates.map((t: any) => [t.id, t]));
  const profileMap = Object.fromEntries((profiles as any[]).map((p: any) => [p.id, p]));

  const refresh = () => { qc.invalidateQueries({ queryKey: ["recurring-shifts"] }); qc.invalidateQueries({ queryKey: ["shifts"] }); };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Regeltermine erzeugen automatisch Dienste für einen ganzen Zeitraum – unter Berücksichtigung von Schulferien und Feiertagen.
        </p>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white shrink-0 ml-4"
          style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
          <Plus size={15} /> Regeltermin
        </button>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground py-6 text-center">Lade…</div>
      ) : (recurringShifts as any[]).length === 0 ? (
        <div className="bg-card rounded-xl border border-border p-8 text-center space-y-3">
          <RepeatIcon size={32} className="mx-auto text-muted-foreground opacity-40" />
          <p className="text-muted-foreground text-sm">Noch keine Regeltermine definiert</p>
          <button onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
            <Plus size={14} /> Ersten Regeltermin anlegen
          </button>
        </div>
      ) : (
        <div className="bg-card rounded-xl border border-border divide-y divide-border">
          {(recurringShifts as any[]).map((rs: any) => {
            const emp = empMap[rs.employee_id];
            const tpl = tplMap[rs.template_id];
            const prof = profileMap[rs.holiday_profile_id];
            return (
              <div key={rs.id} className="px-4 py-3 flex items-center gap-3">
                <div className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: tpl?.color ?? "rgb(var(--ctp-overlay1))" }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-foreground">{rs.weekday_name}</span>
                    <span className="text-sm text-foreground">{rs.start_time?.slice(0,5)} – {rs.end_time?.slice(0,5)}</span>
                    {rs.label && <span className="text-xs text-muted-foreground">{rs.label}</span>}
                    {tpl && <span className="text-xs px-2 py-0.5 rounded-full border border-border text-muted-foreground">{tpl.name}</span>}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap text-xs text-muted-foreground">
                    <span>{emp ? `${emp.first_name} ${emp.last_name}` : "Offen"}</span>
                    <span>·</span>
                    <span>{format(parseISO(rs.valid_from), "d.M.yy", { locale: de })} – {format(parseISO(rs.valid_until), "d.M.yy", { locale: de })}</span>
                    {prof && <span>· {prof.name}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={() => setUpdateFromRs(rs)}
                    className="text-xs px-2.5 py-1.5 rounded-lg border border-border hover:bg-accent text-muted-foreground transition-colors">
                    Ab Datum
                  </button>
                  <button onClick={() => { if (confirm("Regeltermin deaktivieren und zukünftige Dienste löschen?")) deleteMut.mutate(rs.id); }}
                    className="p-2 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showCreate && (
        <CreateRecurringShiftModal
          employees={employees} templates={templates} profiles={profiles as any[]}
          onClose={() => setShowCreate(false)}
          onDone={() => { setShowCreate(false); refresh(); }}
        />
      )}
      {updateFromRs && (
        <UpdateFromModal
          rs={updateFromRs} employees={employees}
          onClose={() => setUpdateFromRs(null)}
          onDone={() => { setUpdateFromRs(null); refresh(); }}
        />
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function ShiftsPage() {
  const { user } = useAuthStore();
  const isPrivileged = user?.role === "admin" || user?.role === "manager";
  const qc = useQueryClient();

  const [tab,            setTab]           = useState<"dienste" | "regeltermine">("dienste");
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
    queryFn: () => shiftsApi.list({ from_date: monthStart, to_date: monthEnd, employee_id: filterEmployee || undefined }).then(r => r.data),
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

  const allowedStatuses = FILTER_STATUSES[statusFilter];
  const filteredShifts = allowedStatuses.length > 0
    ? (shifts as any[]).filter((s: any) => allowedStatuses.includes(s.status))
    : (shifts as any[]);

  const grouped = filteredShifts.reduce((acc: Record<string, any[]>, s: any) => {
    (acc[s.date] ??= []).push(s);
    return acc;
  }, {});
  const sortedDates = Object.keys(grouped).sort();

  const handleCreated  = () => { setShowCreate(false); qc.invalidateQueries({ queryKey: ["shifts"] }); };
  const handleConfirmed= () => { setConfirmShift(null); qc.invalidateQueries({ queryKey: ["shifts"] }); };
  const handleActualSaved = () => { setActualShift(null); qc.invalidateQueries({ queryKey: ["shifts"] }); };

  return (
    <div className="space-y-4">

      {/* ── Header ── */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold text-foreground flex-1">Dienste</h1>

        {/* Tab toggle (privileged only) */}
        {isPrivileged && (
          <div className="flex gap-1 bg-card rounded-lg border border-border p-1">
            <button onClick={() => setTab("dienste")}
              className={`px-3 py-1.5 text-sm rounded font-medium transition-colors ${tab === "dienste" ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}>
              Dienste
            </button>
            <button onClick={() => setTab("regeltermine")}
              className={`px-3 py-1.5 text-sm rounded font-medium transition-colors flex items-center gap-1.5 ${tab === "regeltermine" ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}>
              <RepeatIcon size={13} /> Regeltermine
            </button>
          </div>
        )}

        {tab === "dienste" && (
          <>
            {/* Month nav */}
            <div className="flex items-center gap-1 bg-card rounded-lg border border-border p-1">
              <button onClick={prevMonth} className="p-2.5 hover:bg-accent rounded"><ChevronLeft size={16} /></button>
              <span className="px-3 text-sm font-medium text-foreground min-w-[120px] text-center">
                {format(month, "MMMM yyyy", { locale: de })}
              </span>
              <button onClick={nextMonth} className="p-2.5 hover:bg-accent rounded"><ChevronRight size={16} /></button>
            </div>

            {isPrivileged && (
              <select value={filterEmployee} onChange={e => setFilterEmployee(e.target.value)}
                className="text-sm border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring">
                <option value="">Alle Mitarbeiter</option>
                {(employees as any[]).map((e: any) => (
                  <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>
                ))}
              </select>
            )}

            {isPrivileged && (
              <button onClick={() => setShowCreate(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity">
                <Plus size={16} />
                <span className="hidden sm:inline">Neuer Dienst</span>
              </button>
            )}
          </>
        )}
      </div>

      {/* ── Tab: Regeltermine ── */}
      {tab === "regeltermine" && isPrivileged && (
        <RegeltermineTab employees={employees as any[]} templates={templates as any[]} />
      )}

      {/* ── Tab: Dienste ── */}
      {tab === "dienste" && (
        <>
          {/* Status filter chips */}
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
                      FILTER_STATUSES[key].length > 0 ? FILTER_STATUSES[key].includes(s.status) : true
                    ).length}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Summary bar */}
          <div className="flex gap-4 text-sm">
            <span className="text-muted-foreground">
              <span className="font-semibold text-foreground">{filteredShifts.length}</span> Dienste
            </span>
            {statusFilter === "open" && (
              <span className="text-muted-foreground">
                <span className="font-semibold text-foreground">{filteredShifts.filter((s: any) => !s.employee_id).length}</span> unbesetzt
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

          {/* Shift list */}
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
                          <span className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: tpl?.color ?? "rgb(var(--ctp-overlay1))" }} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-medium text-foreground shrink-0">
                                {shift.start_time?.slice(0,5)} – {shift.end_time?.slice(0,5)}
                              </span>
                              <span className="text-sm text-foreground truncate">{tpl?.name ?? "–"}</span>
                              {shift.recurring_shift_id && (
                                <span title="Aus Regeltermin"><RepeatIcon size={11} className="text-muted-foreground shrink-0" /></span>
                              )}
                              <span className="text-xs px-2 py-0.5 rounded-full font-medium shrink-0 hidden sm:inline"
                                style={STATUS_STYLE[shift.status] ?? STATUS_STYLE.planned}>
                                {STATUS_LABELS[shift.status] ?? shift.status}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                              <span className="text-xs text-muted-foreground truncate">
                                {emp ? `${emp.first_name} ${emp.last_name}` : (
                                  <span className="flex items-center gap-1" style={{ color: "rgb(var(--ctp-red))" }}>
                                    <AlertCircle size={12} /> Offen
                                  </span>
                                )}
                              </span>
                              {hasActualTime && (
                                <span className="text-xs shrink-0 flex items-center gap-1" style={{ color: "rgb(var(--ctp-teal))" }}>
                                  <Clock size={10} />
                                  Ist: {shift.actual_start?.slice(0,5) ?? "–"} – {shift.actual_end?.slice(0,5) ?? "–"}
                                </span>
                              )}
                              {shift.status === "confirmed" && shift.confirmed_at && (
                                <span className="text-xs text-muted-foreground shrink-0 hidden md:inline">
                                  ✓ {format(parseISO(shift.confirmed_at), "d.M. HH:mm")}
                                </span>
                              )}
                              <span className="text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0 sm:hidden"
                                style={STATUS_STYLE[shift.status] ?? STATUS_STYLE.planned}>
                                {STATUS_LABELS[shift.status] ?? shift.status}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            {isPrivileged && shift.status === "planned" && (
                              <button onClick={() => setConfirmShift(shift)} title="Dienst bestätigen"
                                className="p-2.5 rounded hover:bg-accent transition-colors"
                                style={{ color: "rgb(var(--ctp-green))" }}>
                                <Check size={15} />
                              </button>
                            )}
                            {isOwnShift && shift.status === "planned" && (
                              <button onClick={() => setActualShift(shift)} title="Ist-Zeiten eintragen"
                                className="p-2.5 rounded hover:bg-accent transition-colors text-muted-foreground">
                                <Pencil size={14} />
                              </button>
                            )}
                            {isPrivileged && shift.status === "planned" && (
                              <button onClick={() => { if (confirm("Dienst wirklich löschen?")) deleteMutation.mutate(shift.id); }}
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
        </>
      )}

      {/* ── Modals ── */}
      {showCreate && (
        <CreateShiftModal
          templates={templates as any[]} employees={employees as any[]}
          defaultDate={monthStart}
          onClose={() => setShowCreate(false)} onCreated={handleCreated}
        />
      )}
      {confirmShift && <ConfirmModal shift={confirmShift} onClose={() => setConfirmShift(null)} onDone={handleConfirmed} />}
      {actualShift && <ActualTimeModal shift={actualShift} onClose={() => setActualShift(null)} onDone={handleActualSaved} />}
    </div>
  );
}
