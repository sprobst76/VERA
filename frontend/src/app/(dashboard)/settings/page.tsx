"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi, holidayProfilesApi, employeesApi, adminSettingsApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import toast from "react-hot-toast";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { Settings, KeyRound, User, ShieldCheck, Eye, EyeOff, CalendarDays, Plus, Trash2, ChevronDown, ChevronUp, Check, Phone, Mail, Send, Server, Pencil } from "lucide-react";
import { format, parseISO } from "date-fns";
import { de } from "date-fns/locale";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  manager: "Verwalter",
  employee: "Mitarbeiter",
};

const ROLE_COLORS: Record<string, string> = {
  admin: "--ctp-red",
  manager: "--ctp-peach",
  employee: "--ctp-blue",
};

function PasswordField({ label, value, onChange, placeholder, required }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; required?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label className="text-xs text-muted-foreground block mb-1">{label}</label>
      <div className="relative">
        <input
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          placeholder={placeholder || "••••••••"}
          className="w-full border border-border rounded-lg px-3 py-2 pr-10 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button type="button" onClick={() => setVisible((v) => !v)}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors" tabIndex={-1}>
          {visible ? <EyeOff size={15} /> : <Eye size={15} />}
        </button>
      </div>
    </div>
  );
}

// ── Ferienprofile Section ─────────────────────────────────────────────────────

function AddPeriodModal({ profileId, onClose, onDone }: { profileId: string; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [color, setColor] = useState("#a6e3a1");

  const dateError = startDate && endDate && endDate < startDate;

  const mut = useMutation({
    mutationFn: () => holidayProfilesApi.addPeriod(profileId, { name, start_date: startDate, end_date: endDate, color }),
    onSuccess: () => { toast.success("Ferienperiode hinzugefügt"); onDone(); },
    onError: () => toast.error("Fehler beim Hinzufügen"),
  });

  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="font-semibold text-foreground">Ferien hinzufügen</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-accent text-muted-foreground">✕</button>
        </div>
        <div className="px-5 pb-5 space-y-3">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Bezeichnung</label>
            <input className={inputCls} value={name} onChange={e => setName(e.target.value)} placeholder="z.B. Herbstferien" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Von</label>
              <input type="date" className={inputCls} value={startDate} onChange={e => setStartDate(e.target.value)} />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Bis (einschl.)</label>
              <input type="date" className={inputCls} value={endDate} onChange={e => setEndDate(e.target.value)} />
            </div>
          </div>
          {dateError && (
            <p className="text-xs text-destructive">Enddatum muss nach dem Startdatum liegen.</p>
          )}
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Farbe</label>
            <div className="flex items-center gap-2">
              <input type="color" value={color} onChange={e => setColor(e.target.value)} className="h-8 w-16 rounded border border-border cursor-pointer" />
              <span className="text-xs text-muted-foreground">wird im Kalender angezeigt</span>
            </div>
          </div>
          <button
            onClick={() => mut.mutate()}
            disabled={!name || !startDate || !endDate || !!dateError || mut.isPending}
            className="w-full py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-opacity"
            style={{ backgroundColor: "rgb(var(--ctp-green))" }}>
            {mut.isPending ? "Wird gespeichert…" : "Hinzufügen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function AddCustomDayModal({ profileId, onClose, onDone }: { profileId: string; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState("");
  const [date, setDate] = useState("");
  const [color, setColor] = useState("#fab387");

  const mut = useMutation({
    mutationFn: () => holidayProfilesApi.addCustomDay(profileId, { name, date, color }),
    onSuccess: () => { toast.success("Beweglicher Tag hinzugefügt"); onDone(); },
    onError: () => toast.error("Fehler"),
  });

  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="font-semibold text-foreground">Beweglicher Ferientag</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-accent text-muted-foreground">✕</button>
        </div>
        <div className="px-5 pb-5 space-y-3">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Bezeichnung</label>
            <input className={inputCls} value={name} onChange={e => setName(e.target.value)} placeholder="z.B. Konferenztag" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Datum</label>
            <input type="date" className={inputCls} value={date} onChange={e => setDate(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Farbe</label>
            <input type="color" value={color} onChange={e => setColor(e.target.value)} className="h-8 w-16 rounded border border-border cursor-pointer" />
          </div>
          <button
            onClick={() => mut.mutate()}
            disabled={!name || !date || mut.isPending}
            className="w-full py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-peach))" }}>
            {mut.isPending ? "Wird gespeichert…" : "Hinzufügen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateProfileModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState("");
  const [state, setState] = useState("BW");
  const [isActive, setIsActive] = useState(false);
  const [presetBW, setPresetBW] = useState(true);

  const mut = useMutation({
    mutationFn: () => holidayProfilesApi.create({ name, state, is_active: isActive, preset_bw: presetBW }),
    onSuccess: () => { toast.success("Ferienprofil erstellt"); onDone(); },
    onError: (err: any) => toast.error(err?.response?.data?.detail || "Fehler"),
  });

  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="font-semibold text-foreground">Neues Ferienprofil</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-accent text-muted-foreground">✕</button>
        </div>
        <div className="px-5 pb-5 space-y-3">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Name</label>
            <input className={inputCls} value={name} onChange={e => setName(e.target.value)} placeholder="z.B. BW 2025/26" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Bundesland</label>
            <select className={inputCls} value={state} onChange={e => setState(e.target.value)}>
              <option value="BW">Baden-Württemberg (BW)</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
            <input type="checkbox" checked={presetBW} onChange={e => setPresetBW(e.target.checked)} className="rounded" />
            BW 2025/26 Schulferien vorausfüllen
          </label>
          <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
            <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} className="rounded" />
            Als aktives Profil setzen
          </label>
          <button
            onClick={() => mut.mutate()}
            disabled={!name || mut.isPending}
            className="w-full py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
            {mut.isPending ? "Wird erstellt…" : "Profil erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EditPeriodRow({ profileId, vp, onDone, onCancel }: {
  profileId: string; vp: any; onDone: () => void; onCancel: () => void;
}) {
  const [name, setName] = useState(vp.name);
  const [startDate, setStartDate] = useState(vp.start_date);
  const [endDate, setEndDate] = useState(vp.end_date);
  const [color, setColor] = useState(vp.color ?? "#a6e3a1");

  const dateError = startDate && endDate && endDate < startDate;

  const mut = useMutation({
    mutationFn: () => holidayProfilesApi.updatePeriod(profileId, vp.id, { name, start_date: startDate, end_date: endDate, color }),
    onSuccess: () => { toast.success("Gespeichert"); onDone(); },
    onError: () => toast.error("Fehler beim Speichern"),
  });

  const inputCls = "px-2 py-1 rounded border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <div className="space-y-2 py-1 px-1 rounded-lg bg-muted/40 border border-border">
      <input className={`w-full ${inputCls}`} value={name} onChange={e => setName(e.target.value)} placeholder="Bezeichnung" />
      <div className="flex gap-2 items-center flex-wrap">
        <input type="date" className={inputCls} value={startDate} onChange={e => setStartDate(e.target.value)} />
        <span className="text-xs text-muted-foreground">–</span>
        <input type="date" className={inputCls} value={endDate} onChange={e => setEndDate(e.target.value)} />
        <input type="color" value={color} onChange={e => setColor(e.target.value)} className="h-6 w-10 rounded border border-border cursor-pointer" />
      </div>
      {dateError && <p className="text-xs text-destructive">Enddatum muss nach dem Startdatum liegen.</p>}
      <div className="flex gap-2">
        <button onClick={() => mut.mutate()} disabled={!name || !!dateError || mut.isPending}
          className="flex items-center gap-1 text-xs px-2.5 py-1 rounded bg-primary text-primary-foreground disabled:opacity-50">
          <Check size={11} /> Speichern
        </button>
        <button onClick={onCancel} className="text-xs px-2.5 py-1 rounded border border-border hover:bg-accent text-muted-foreground">
          Abbrechen
        </button>
      </div>
    </div>
  );
}

function HolidayProfileCard({ profile, onRefresh }: { profile: any; onRefresh: () => void }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [showAddPeriod, setShowAddPeriod] = useState(false);
  const [showAddCustom, setShowAddCustom] = useState(false);
  const [editingPeriodId, setEditingPeriodId] = useState<string | null>(null);

  const { data: detail } = useQuery({
    queryKey: ["holiday-profile", profile.id],
    queryFn: () => holidayProfilesApi.get(profile.id).then(r => r.data),
    enabled: expanded,
  });

  const toggleActiveMut = useMutation({
    mutationFn: () => holidayProfilesApi.update(profile.id, { is_active: !profile.is_active }),
    onSuccess: () => { onRefresh(); toast.success(profile.is_active ? "Profil deaktiviert" : "Profil aktiviert"); },
    onError: () => toast.error("Fehler"),
  });

  const deleteMut = useMutation({
    mutationFn: () => holidayProfilesApi.delete(profile.id),
    onSuccess: () => { onRefresh(); toast.success("Profil gelöscht"); },
    onError: (err: any) => toast.error(err?.response?.data?.detail || "Fehler beim Löschen"),
  });

  const deletePeriodMut = useMutation({
    mutationFn: (periodId: string) => holidayProfilesApi.deletePeriod(profile.id, periodId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["holiday-profile", profile.id] }); onRefresh(); },
    onError: () => toast.error("Fehler"),
  });

  const deleteCustomMut = useMutation({
    mutationFn: (dayId: string) => holidayProfilesApi.deleteCustomDay(profile.id, dayId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["holiday-profile", profile.id] }); onRefresh(); },
    onError: () => toast.error("Fehler"),
  });

  const handleAddDone = () => {
    setShowAddPeriod(false);
    setShowAddCustom(false);
    qc.invalidateQueries({ queryKey: ["holiday-profile", profile.id] });
    onRefresh();
  };

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Header row */}
      <div className="flex items-center gap-3 px-4 py-3 bg-background">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-foreground text-sm">{profile.name}</span>
            <span className="text-xs px-2 py-0.5 rounded-full border border-border text-muted-foreground">{profile.state}</span>
            {profile.is_active && (
              <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ backgroundColor: "rgb(var(--ctp-green) / 0.15)", color: "rgb(var(--ctp-green))" }}>
                <Check size={11} className="inline mr-0.5" />Aktiv
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {profile.vacation_period_count} Ferienperiode{profile.vacation_period_count !== 1 ? "n" : ""} · {profile.custom_holiday_count} bewegliche Tag{profile.custom_holiday_count !== 1 ? "e" : ""}
          </p>
        </div>

        <div className="flex items-center gap-1">
          <button onClick={() => toggleActiveMut.mutate()} disabled={toggleActiveMut.isPending}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-border hover:bg-accent transition-colors text-muted-foreground">
            {profile.is_active ? "Deaktivieren" : "Aktivieren"}
          </button>
          <button onClick={() => { if (confirm("Profil wirklich löschen?")) deleteMut.mutate(); }}
            className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
            <Trash2 size={14} />
          </button>
          <button onClick={() => setExpanded(e => !e)} className="p-1.5 rounded hover:bg-accent text-muted-foreground">
            {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && detail && (
        <div className="px-4 pb-4 bg-card border-t border-border space-y-4 pt-3">
          {/* Vacation Periods */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Ferienperioden</h4>
              <button onClick={() => setShowAddPeriod(true)}
                className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-border hover:bg-accent text-foreground">
                <Plus size={11} /> Ferien
              </button>
            </div>
            {detail.vacation_periods.length === 0 ? (
              <p className="text-xs text-muted-foreground">Keine Ferienperioden</p>
            ) : (
              <div className="space-y-1.5">
                {detail.vacation_periods.map((vp: any) => (
                  editingPeriodId === vp.id ? (
                    <EditPeriodRow
                      key={vp.id}
                      profileId={profile.id}
                      vp={vp}
                      onDone={() => { setEditingPeriodId(null); qc.invalidateQueries({ queryKey: ["holiday-profile", profile.id] }); onRefresh(); }}
                      onCancel={() => setEditingPeriodId(null)}
                    />
                  ) : (
                    <div key={vp.id} className="flex items-center gap-2 text-sm">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: vp.color ?? "#a6e3a1" }} />
                      <span className="flex-1 text-foreground">{vp.name}</span>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {format(parseISO(vp.start_date), "d.M.", { locale: de })} – {format(parseISO(vp.end_date), "d.M.yy", { locale: de })}
                      </span>
                      <button onClick={() => setEditingPeriodId(vp.id)}
                        className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground">
                        <Pencil size={12} />
                      </button>
                      <button onClick={() => deletePeriodMut.mutate(vp.id)}
                        className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )
                ))}
              </div>
            )}
          </div>

          {/* Custom Holidays */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Bewegliche Tage</h4>
              <button onClick={() => setShowAddCustom(true)}
                className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-border hover:bg-accent text-foreground">
                <Plus size={11} /> Tag
              </button>
            </div>
            {detail.custom_holidays.length === 0 ? (
              <p className="text-xs text-muted-foreground">Keine beweglichen Ferientage</p>
            ) : (
              <div className="space-y-1">
                {detail.custom_holidays.map((ch: any) => (
                  <div key={ch.id} className="flex items-center gap-2 text-sm">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: ch.color }} />
                    <span className="flex-1 text-foreground">{ch.name}</span>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {format(parseISO(ch.date), "d.M.yyyy", { locale: de })}
                    </span>
                    <button onClick={() => deleteCustomMut.mutate(ch.id)}
                      className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {showAddPeriod && <AddPeriodModal profileId={profile.id} onClose={() => setShowAddPeriod(false)} onDone={handleAddDone} />}
      {showAddCustom && <AddCustomDayModal profileId={profile.id} onClose={() => setShowAddCustom(false)} onDone={handleAddDone} />}
    </div>
  );
}

// ── Mein Profil Section (Employee only) ──────────────────────────────────────

function MeinProfilSection() {
  const qc = useQueryClient();

  const { data: profile, isLoading } = useQuery({
    queryKey: ["employees", "me"],
    queryFn: () => employeesApi.me().then(r => r.data),
  });

  const [phone, setPhone] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [initialized, setInitialized] = useState(false);

  if (!initialized && profile) {
    setPhone((profile as any).phone ?? "");
    setEmail((profile as any).email ?? "");
    setInitialized(true);
  }

  const saveMut = useMutation({
    mutationFn: () => employeesApi.updateMe({ phone: phone || null, email: email || null }),
    onSuccess: () => {
      toast.success("Profil gespeichert");
      qc.invalidateQueries({ queryKey: ["employees", "me"] });
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || "Fehler beim Speichern"),
  });

  const CONTRACT_LABELS: Record<string, string> = {
    minijob: "Minijob",
    part_time: "Teilzeit",
    full_time: "Vollzeit",
    ehrenamt: "Ehrenamt",
  };

  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <div className="bg-card rounded-xl border border-border p-5 space-y-4">
      <div className="flex items-center gap-2">
        <User size={18} style={{ color: "rgb(var(--ctp-sapphire))" }} />
        <h2 className="font-semibold text-foreground">Mein Profil</h2>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Lade…</p>
      ) : profile ? (
        <>
          {/* Read-only info */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-xs text-muted-foreground mb-0.5">Vorname</div>
              <div className="font-medium text-foreground">{(profile as any).first_name}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-0.5">Nachname</div>
              <div className="font-medium text-foreground">{(profile as any).last_name}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-0.5">Vertragstyp</div>
              <div className="font-medium text-foreground capitalize">
                {CONTRACT_LABELS[(profile as any).contract_type] ?? (profile as any).contract_type}
              </div>
            </div>
            {(profile as any).hourly_rate != null && (
              <div>
                <div className="text-xs text-muted-foreground mb-0.5">Stundenlohn</div>
                <div className="font-medium text-foreground">
                  {((profile as any).hourly_rate as number).toLocaleString("de-DE", { style: "currency", currency: "EUR" })} / h
                </div>
              </div>
            )}
            {(profile as any).weekly_hours != null && (
              <div>
                <div className="text-xs text-muted-foreground mb-0.5">Vertragsstunden / Woche</div>
                <div className="font-medium text-foreground">{(profile as any).weekly_hours} h</div>
              </div>
            )}
            {(profile as any).full_time_percentage != null && (
              <div>
                <div className="text-xs text-muted-foreground mb-0.5">Vollzeitanteil</div>
                <div className="font-medium text-foreground">{(profile as any).full_time_percentage} %</div>
              </div>
            )}
          </div>

          {/* Editable fields */}
          <div className="space-y-3 pt-1 border-t border-border">
            <p className="text-xs text-muted-foreground">Bearbeitbare Felder:</p>
            <div>
              <label className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                <Phone size={12} /> Telefon
              </label>
              <input
                type="tel"
                className={inputCls}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+49 …"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                <Mail size={12} /> Kontakt-E-Mail
              </label>
              <input
                type="email"
                className={inputCls}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="vorname@example.com"
              />
            </div>
            <button
              onClick={() => saveMut.mutate()}
              disabled={saveMut.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ backgroundColor: "rgb(var(--ctp-sapphire))" }}
            >
              {saveMut.isPending ? "Wird gespeichert…" : (<><Check size={15} />Speichern</>)}
            </button>
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Kein Mitarbeiterprofil verknüpft.</p>
      )}
    </div>
  );
}

// ── SMTP-Konfiguration (Admin only) ───────────────────────────────────────────

function SMTPSection() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [host, setHost] = useState("");
  const [port, setPort] = useState("587");
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [fromEmail, setFromEmail] = useState("");

  const { data: cfg, isLoading } = useQuery({
    queryKey: ["admin-settings-smtp"],
    queryFn: () => adminSettingsApi.getSmtp().then(r => r.data),
  });

  const saveMutation = useMutation({
    mutationFn: () => adminSettingsApi.updateSmtp({
      host, port: Number(port), user, password, from_email: fromEmail,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-settings-smtp"] });
      toast.success("SMTP-Konfiguration gespeichert");
      setEditing(false);
      setPassword("");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Fehler beim Speichern"),
  });

  const testMutation = useMutation({
    mutationFn: () => adminSettingsApi.testSmtp(),
    onSuccess: (r: any) => toast.success(r.data?.detail || "Test-Mail gesendet"),
    onError: (e: any) => toast.error(e?.response?.data?.detail || "SMTP-Fehler"),
  });

  const startEdit = () => {
    setHost(cfg?.host ?? "");
    setPort(String(cfg?.port ?? 587));
    setUser(cfg?.user ?? "");
    setPassword("");
    setFromEmail(cfg?.from_email ?? "");
    setEditing(true);
  };

  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Server size={16} className="text-muted-foreground" />
          <span className="font-semibold text-sm">E-Mail (SMTP)</span>
          {cfg?.configured && (
            <span className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ backgroundColor: "rgb(var(--ctp-green) / 0.15)", color: "rgb(var(--ctp-green))" }}>
              Konfiguriert
            </span>
          )}
        </div>
        {!editing && !isLoading && (
          <button onClick={startEdit}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
            <Settings size={13} /> {cfg?.configured ? "Bearbeiten" : "Einrichten"}
          </button>
        )}
      </div>

      {!editing ? (
        <dl className="divide-y divide-border text-sm">
          <div className="px-5 py-3 flex justify-between gap-4">
            <dt className="text-muted-foreground">SMTP-Server</dt>
            <dd>{cfg?.host ? `${cfg.host}:${cfg.port}` : <span className="text-muted-foreground italic">nicht gesetzt</span>}</dd>
          </div>
          <div className="px-5 py-3 flex justify-between gap-4">
            <dt className="text-muted-foreground">Benutzer</dt>
            <dd>{cfg?.user || <span className="text-muted-foreground italic">nicht gesetzt</span>}</dd>
          </div>
          <div className="px-5 py-3 flex justify-between gap-4">
            <dt className="text-muted-foreground">Passwort</dt>
            <dd>{cfg?.has_password ? "••••••" : <span className="text-muted-foreground italic">nicht gesetzt</span>}</dd>
          </div>
          <div className="px-5 py-3 flex justify-between gap-4">
            <dt className="text-muted-foreground">Absender</dt>
            <dd>{cfg?.from_email || <span className="text-muted-foreground italic">nicht gesetzt</span>}</dd>
          </div>
          {cfg?.configured && (
            <div className="px-5 py-3">
              <button onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm border border-border hover:bg-accent transition-colors disabled:opacity-50">
                <Send size={13} />
                {testMutation.isPending ? "Wird gesendet…" : "Test-Mail senden"}
              </button>
            </div>
          )}
        </dl>
      ) : (
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">SMTP-Host</label>
              <input value={host} onChange={e => setHost(e.target.value)}
                placeholder="smtp.ionos.de" className={inputCls} />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Port</label>
              <input value={port} onChange={e => setPort(e.target.value)}
                type="number" placeholder="587" className={inputCls} />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Benutzername</label>
            <input value={user} onChange={e => setUser(e.target.value)}
              type="email" placeholder="deine@ionos-adresse.de" className={inputCls} />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Passwort {cfg?.has_password && <span className="text-muted-foreground font-normal">(leer lassen = unverändert)</span>}
            </label>
            <PasswordField label="" value={password} onChange={setPassword}
              placeholder={cfg?.has_password ? "unverändert" : "Passwort eingeben"} />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Absender-Adresse</label>
            <input value={fromEmail} onChange={e => setFromEmail(e.target.value)}
              type="email" placeholder="vera@deinedomain.de (leer = Benutzername)" className={inputCls} />
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || !host || !user || (!password && !cfg?.has_password)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-opacity"
              style={{ backgroundColor: "rgb(var(--ctp-green))" }}>
              <Check size={14} /> {saveMutation.isPending ? "Speichern…" : "Speichern"}
            </button>
            <button onClick={() => setEditing(false)}
              className="px-4 py-2 rounded-lg text-sm border border-border hover:bg-accent transition-colors">
              Abbrechen
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function FerienprofileSection() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ["holiday-profiles"],
    queryFn: () => holidayProfilesApi.list().then(r => r.data),
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["holiday-profiles"] });

  return (
    <div className="bg-card rounded-xl border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays size={18} style={{ color: "rgb(var(--ctp-sapphire))" }} />
          <h2 className="font-semibold text-foreground">Ferienprofile</h2>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-border hover:bg-accent text-foreground transition-colors">
          <Plus size={13} /> Neues Profil
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        Konfiguriere Schulferien und bewegliche Ferientage für die automatische Generierung von Regelterminen.
      </p>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Lade…</p>
      ) : (profiles as any[]).length === 0 ? (
        <div className="text-center py-6 space-y-2">
          <p className="text-sm text-muted-foreground">Noch kein Ferienprofil angelegt</p>
          <button onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 text-sm px-4 py-2 rounded-lg text-white"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
            <Plus size={14} /> Erstes Profil erstellen
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {(profiles as any[]).map((p: any) => (
            <HolidayProfileCard key={p.id} profile={p} onRefresh={refresh} />
          ))}
        </div>
      )}

      {showCreate && <CreateProfileModal onClose={() => setShowCreate(false)} onDone={() => { setShowCreate(false); refresh(); }} />}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { user } = useAuthStore();
  const role = user?.role ?? "employee";
  const color = ROLE_COLORS[role] ?? "--ctp-blue";
  const isPrivileged = role === "admin" || role === "manager";

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");

  const changePwMutation = useMutation({
    mutationFn: () => authApi.changePassword(currentPw, newPw),
    onSuccess: () => {
      toast.success("Passwort erfolgreich geändert");
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || "Fehler beim Ändern des Passworts");
    },
  });

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw !== confirmPw) { toast.error("Neue Passwörter stimmen nicht überein"); return; }
    if (newPw.length < 8) { toast.error("Neues Passwort muss mindestens 8 Zeichen lang sein"); return; }
    changePwMutation.mutate();
  };

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Einstellungen</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Konto & Erscheinungsbild</p>
      </div>

      {/* Account info */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-4">
        <div className="flex items-center gap-2">
          <User size={18} style={{ color: `rgb(var(${color}))` }} />
          <h2 className="font-semibold text-foreground">Mein Konto</h2>
        </div>
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold shrink-0"
            style={{ backgroundColor: `rgb(var(${color}) / 0.15)`, color: `rgb(var(${color}))` }}>
            {user?.email?.charAt(0).toUpperCase() ?? "?"}
          </div>
          <div className="min-w-0">
            <p className="font-medium text-foreground truncate">{user?.email}</p>
            <span className="inline-block text-xs px-2 py-0.5 rounded-full font-medium mt-0.5"
              style={{ backgroundColor: `rgb(var(${color}) / 0.12)`, color: `rgb(var(${color}))` }}>
              {ROLE_LABELS[role] ?? role}
            </span>
          </div>
        </div>
      </div>

      {/* Theme */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Settings size={18} style={{ color: "rgb(var(--ctp-mauve))" }} />
          <h2 className="font-semibold text-foreground">Erscheinungsbild</h2>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-foreground">Farbschema</p>
            <p className="text-xs text-muted-foreground">Wähle zwischen hellem und dunklem Design</p>
          </div>
          <div className="rounded-lg border border-border overflow-hidden"
            style={{ backgroundColor: "rgb(var(--sidebar-bg))", color: "rgb(var(--sidebar-fg))" }}>
            <ThemeToggle />
          </div>
        </div>
      </div>

      {/* Password change */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-4">
        <div className="flex items-center gap-2">
          <KeyRound size={18} style={{ color: "rgb(var(--ctp-green))" }} />
          <h2 className="font-semibold text-foreground">Passwort ändern</h2>
        </div>
        <form onSubmit={handlePasswordSubmit} className="space-y-3">
          <PasswordField label="Aktuelles Passwort" value={currentPw} onChange={setCurrentPw} required />
          <PasswordField label="Neues Passwort" value={newPw} onChange={setNewPw} placeholder="Mind. 8 Zeichen" required />
          <PasswordField label="Neues Passwort bestätigen" value={confirmPw} onChange={setConfirmPw} required />
          {newPw && confirmPw && newPw !== confirmPw && (
            <p className="text-xs" style={{ color: "rgb(var(--ctp-red))" }}>Passwörter stimmen nicht überein</p>
          )}
          <div className="pt-1">
            <button type="submit"
              disabled={changePwMutation.isPending || !currentPw || !newPw || !confirmPw}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
              style={{ backgroundColor: "rgb(var(--ctp-green))" }}>
              {changePwMutation.isPending ? "Wird gespeichert…" : (<><ShieldCheck size={15} />Passwort ändern</>)}
            </button>
          </div>
        </form>
      </div>

      {/* Mein Profil (employee only) */}
      {role === "employee" && <MeinProfilSection />}

      {/* SMTP-Konfiguration (admin only) */}
      {role === "admin" && <SMTPSection />}

      {/* Ferienprofile (admin/manager only) */}
      {isPrivileged && <FerienprofileSection />}
    </div>
  );
}
