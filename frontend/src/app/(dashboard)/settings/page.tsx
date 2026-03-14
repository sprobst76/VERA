"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi, holidayProfilesApi, employeesApi, adminSettingsApi, apiKeysApi, webhooksApi, shiftTypesApi, usersApi, calendarDataApi, contractTypesApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import toast from "react-hot-toast";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { Settings, KeyRound, User, ShieldCheck, Eye, EyeOff, CalendarDays, Plus, Trash2, ChevronDown, ChevronUp, Check, Phone, Mail, Send, Server, Pencil, Copy, AlertTriangle, Webhook, Play, Layers, Bell, BellOff, Users, UserPlus, Lock, Power, Shield, Link, RefreshCw, ExternalLink } from "lucide-react";
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

// ── Kalenderfreigabe Section ──────────────────────────────────────────────────

function ICalLinkRow({ label, url, accent }: { label: string; url: string; accent?: boolean }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={`rounded-xl border p-3 space-y-2 ${accent ? "border-blue-500/30 bg-blue-500/5" : "border-border"}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-foreground">{label}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={copy}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg hover:bg-muted text-muted-foreground transition-colors"
            title="URL kopieren"
          >
            {copied ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
            {copied ? "Kopiert!" : "Kopieren"}
          </button>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1 rounded-lg hover:bg-muted text-muted-foreground"
            title="In neuem Tab öffnen"
          >
            <ExternalLink size={12} />
          </a>
        </div>
      </div>
      <div className="font-mono text-xs text-muted-foreground break-all bg-muted/50 rounded-lg px-2.5 py-1.5 select-all">
        {url}
      </div>
    </div>
  );
}

function KalenderfreigabeSection() {
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const isPrivileged = user?.role === "admin" || user?.role === "manager";
  const [showConfirm, setShowConfirm] = useState(false);

  const { data: links, isLoading } = useQuery<any>({
    queryKey: ["ical-links"],
    queryFn: () => calendarDataApi.icalLinks().then(r => r.data),
  });

  const regenerateMut = useMutation({
    mutationFn: () => calendarDataApi.regenerateToken(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ical-links"] });
      setShowConfirm(false);
      toast.success("Neuer Kalender-Link generiert – der alte Link ist ungültig");
    },
    onError: () => toast.error("Fehler beim Generieren"),
  });

  return (
    <div className="bg-card rounded-2xl border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays size={18} className="text-muted-foreground" />
          <h2 className="font-semibold text-foreground">Kalenderfreigabe</h2>
        </div>
      </div>

      <p className="text-xs text-muted-foreground leading-relaxed">
        Abonniere deinen Dienstkalender in Google Calendar, Apple Kalender oder Outlook.
        Der Link funktioniert ohne Login — halte ihn geheim.
        Erinnerungen werden automatisch eingebaut, sofern der Dienst einem Typ mit aktivierter Erinnerung zugewiesen ist.
      </p>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Lade…</p>
      ) : links ? (
        <div className="space-y-3">
          <ICalLinkRow
            label={isPrivileged ? "Dein Kalender (alle Dienste im Betrieb)" : "Dein persönlicher Kalender"}
            url={links.own_url}
            accent
          />

          {isPrivileged && links.employee_links?.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground pt-1">
                Mitarbeiter-Kalender
              </p>
              {links.employee_links.map((el: any) => (
                <ICalLinkRow key={el.id} label={el.name} url={el.url} />
              ))}
            </div>
          )}
        </div>
      ) : null}

      <div className="pt-1 border-t border-border">
        {showConfirm ? (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground flex items-start gap-2">
              <AlertTriangle size={13} className="shrink-0 mt-0.5" style={{ color: "rgb(var(--ctp-peach))" }} />
              Der bestehende Link wird ungültig. Alle Kalender-Abonnements müssen neu eingerichtet werden.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => regenerateMut.mutate()}
                disabled={regenerateMut.isPending}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium text-white disabled:opacity-50"
                style={{ backgroundColor: "rgb(var(--ctp-peach))" }}
              >
                <RefreshCw size={12} /> {regenerateMut.isPending ? "Generiere…" : "Ja, neu generieren"}
              </button>
              <button
                onClick={() => setShowConfirm(false)}
                className="text-xs px-3 py-1.5 rounded-lg border border-border text-muted-foreground hover:bg-muted"
              >
                Abbrechen
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowConfirm(true)}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw size={13} /> Link neu generieren (invalidiert bisherigen Link)
          </button>
        )}
      </div>

      {/* Anleitung */}
      <details className="group">
        <summary className="text-xs text-muted-foreground cursor-pointer flex items-center gap-1.5 hover:text-foreground transition-colors select-none">
          <ChevronDown size={13} className="group-open:rotate-180 transition-transform" />
          Anleitung: Kalender abonnieren
        </summary>
        <div className="mt-2 text-xs text-muted-foreground space-y-1.5 pl-4 border-l border-border">
          <p><strong className="text-foreground">Google Calendar:</strong> Einstellungen → Weitere Kalender → Per URL hinzufügen → URL einfügen</p>
          <p><strong className="text-foreground">Apple Kalender:</strong> Ablage → Neues Kalenderabonnement → URL einfügen</p>
          <p><strong className="text-foreground">Outlook:</strong> Kalender hinzufügen → Aus dem Internet abonnieren → URL einfügen</p>
        </div>
      </details>
    </div>
  );
}

// ── Ferienprofile Section ─────────────────────────────────────────────────────

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

// ── API Keys Section (Admin only) ─────────────────────────────────────────────

const ALL_SCOPES = ["read", "write", "admin"] as const;
type ScopeValue = typeof ALL_SCOPES[number];

const SCOPE_LABELS: Record<ScopeValue, string> = {
  read: "Lesen",
  write: "Schreiben",
  admin: "Admin",
};

const SCOPE_COLORS: Record<ScopeValue, string> = {
  read:  "--ctp-blue",
  write: "--ctp-peach",
  admin: "--ctp-red",
};

interface ApiKeyItem {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
  last_used_at: string | null;
}

function CreateApiKeyModal({ onClose, onCreated }: { onClose: () => void; onCreated: (key: string) => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["read"]);

  const toggleScope = (scope: string) => {
    setScopes(prev =>
      prev.includes(scope) ? prev.filter(s => s !== scope) : [...prev, scope]
    );
  };

  const mut = useMutation({
    mutationFn: () => apiKeysApi.create({ name, scopes }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["api-keys"] });
      onCreated(res.data.key);
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || "Fehler beim Erstellen"),
  });

  const inputCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="font-semibold text-foreground">Neuen API-Key erstellen</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-accent text-muted-foreground">✕</button>
        </div>
        <div className="px-5 pb-5 space-y-4">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Name / Verwendungszweck</label>
            <input
              className={inputCls}
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="z.B. n8n Automatisierung"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-2">Berechtigungen</label>
            <div className="flex gap-2 flex-wrap">
              {ALL_SCOPES.map(scope => (
                <label key={scope} className="flex items-center gap-1.5 cursor-pointer text-sm select-none">
                  <input
                    type="checkbox"
                    checked={scopes.includes(scope)}
                    onChange={() => toggleScope(scope)}
                    className="rounded"
                  />
                  <span style={{ color: `rgb(var(${SCOPE_COLORS[scope]}))` }}>{SCOPE_LABELS[scope]}</span>
                </label>
              ))}
            </div>
          </div>
          <button
            onClick={() => mut.mutate()}
            disabled={!name || scopes.length === 0 || mut.isPending}
            className="w-full py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-opacity"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
            {mut.isPending ? "Wird erstellt…" : "API-Key erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function NewKeyAlert({ rawKey, onDismiss }: { rawKey: string; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false);

  const copyKey = () => {
    navigator.clipboard.writeText(rawKey).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="rounded-lg border p-4 space-y-3"
      style={{ borderColor: "rgb(var(--ctp-yellow) / 0.5)", backgroundColor: "rgb(var(--ctp-yellow) / 0.08)" }}>
      <div className="flex items-start gap-2">
        <AlertTriangle size={16} className="shrink-0 mt-0.5" style={{ color: "rgb(var(--ctp-yellow))" }} />
        <div>
          <p className="text-sm font-semibold text-foreground">Key nur einmal anzeigbar!</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Dieser Key wird nicht gespeichert und kann nicht wiederhergestellt werden. Kopiere ihn jetzt.
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <code className="flex-1 text-xs font-mono px-3 py-2 rounded-lg bg-background border border-border text-foreground break-all">
          {rawKey}
        </code>
        <button
          onClick={copyKey}
          className="shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm border border-border hover:bg-accent transition-colors"
          title="In Zwischenablage kopieren">
          {copied ? <Check size={14} style={{ color: "rgb(var(--ctp-green))" }} /> : <Copy size={14} />}
          {copied ? "Kopiert" : "Kopieren"}
        </button>
      </div>
      <button
        onClick={onDismiss}
        className="text-xs text-muted-foreground hover:text-foreground underline transition-colors">
        Ich habe den Key gespeichert – ausblenden
      </button>
    </div>
  );
}

// ── Benutzerverwaltung Section ────────────────────────────────────────────────

const ROLE_BADGE: Record<string, { label: string; cssVar: string }> = {
  admin:    { label: "Administrator", cssVar: "--ctp-red" },
  manager:  { label: "Verwalter",     cssVar: "--ctp-peach" },
  employee: { label: "Mitarbeiter",   cssVar: "--ctp-blue" },
};

interface UserEntry {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  has_employee: boolean;
}

function CreateUserModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ email: "", password: "", role: "admin" });
  const [visible, setVisible] = useState(false);

  const mut = useMutation({
    mutationFn: () => usersApi.create(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("Benutzer angelegt");
      onClose();
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? "Fehler beim Anlegen");
    },
  });

  const valid = form.email.includes("@") && form.password.length >= 8;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-card rounded-2xl border border-border w-full max-w-sm p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-foreground flex items-center gap-2">
            <UserPlus size={16} /> Neuer Benutzer
          </h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground">
            <Plus size={16} className="rotate-45" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Rolle</label>
            <div className="flex gap-2">
              {(["admin", "manager", "employee"] as const).map(r => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setForm(f => ({ ...f, role: r }))}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors ${form.role === r ? "border-blue-500 text-white" : "border-border text-muted-foreground hover:bg-muted"}`}
                  style={form.role === r ? { backgroundColor: `rgb(var(${ROLE_BADGE[r].cssVar}))` } : {}}
                >
                  {ROLE_BADGE[r].label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">E-Mail</label>
            <input
              type="email"
              value={form.email}
              onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
              placeholder="name@example.com"
              className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Passwort (min. 8 Zeichen)</label>
            <div className="relative">
              <input
                type={visible ? "text" : "password"}
                value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                placeholder="••••••••"
                className="w-full border border-border rounded-lg px-3 py-2 pr-10 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button type="button" onClick={() => setVisible(v => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground" tabIndex={-1}>
                {visible ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {form.role === "admin" && (
            <p className="text-xs rounded-lg px-3 py-2 flex items-start gap-2" style={{ backgroundColor: "rgb(var(--ctp-red) / 0.10)", color: "rgb(var(--ctp-red))" }}>
              <Shield size={13} className="mt-0.5 shrink-0" />
              Administratoren haben vollen Zugriff auf alle Daten und Einstellungen.
            </p>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => mut.mutate()}
            disabled={!valid || mut.isPending}
            className="flex-1 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
          >
            {mut.isPending ? "Anlegen…" : "Benutzer anlegen"}
          </button>
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-sm border border-border text-muted-foreground hover:bg-muted">
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}

function EditUserModal({ user, currentUserId, onClose }: { user: UserEntry; currentUserId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [role, setRole] = useState(user.role);
  const [newPw, setNewPw] = useState("");
  const [visible, setVisible] = useState(false);
  const isSelf = user.id === currentUserId;

  const updateMut = useMutation({
    mutationFn: (data: { role?: string; is_active?: boolean; password?: string }) =>
      usersApi.update(user.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("Gespeichert");
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail ?? "Fehler"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-card rounded-2xl border border-border w-full max-w-sm p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-foreground">{user.email}</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground">
            <Plus size={16} className="rotate-45" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Rolle */}
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-2">Rolle</label>
            {isSelf ? (
              <p className="text-xs text-muted-foreground italic">Eigene Rolle kann nicht geändert werden.</p>
            ) : (
              <div className="flex gap-2">
                {(["admin", "manager", "employee"] as const).map(r => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRole(r)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors ${role === r ? "border-blue-500 text-white" : "border-border text-muted-foreground hover:bg-muted"}`}
                    style={role === r ? { backgroundColor: `rgb(var(${ROLE_BADGE[r].cssVar}))` } : {}}
                  >
                    {ROLE_BADGE[r].label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Passwort zurücksetzen */}
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1 flex items-center gap-1">
              <Lock size={11} /> Neues Passwort (optional)
            </label>
            <div className="relative">
              <input
                type={visible ? "text" : "password"}
                value={newPw}
                onChange={e => setNewPw(e.target.value)}
                placeholder="Leer lassen = unverändert"
                className="w-full border border-border rounded-lg px-3 py-2 pr-10 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button type="button" onClick={() => setVisible(v => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground" tabIndex={-1}>
                {visible ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {/* Status */}
          {!isSelf && (
            <div className="flex items-center justify-between rounded-xl border border-border px-4 py-3">
              <span className="text-sm text-foreground flex items-center gap-1.5">
                <Power size={14} /> Konto aktiv
              </span>
              <button
                type="button"
                onClick={() => updateMut.mutate({ is_active: !user.is_active })}
                className={`relative w-10 h-5 rounded-full transition-colors ${user.is_active ? "bg-green-500" : "bg-muted-foreground/30"}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${user.is_active ? "translate-x-5" : ""}`} />
              </button>
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => {
              const data: any = {};
              if (!isSelf && role !== user.role) data.role = role;
              if (newPw.length >= 8) data.password = newPw;
              if (Object.keys(data).length > 0) updateMut.mutate(data, { onSuccess: onClose });
              else onClose();
            }}
            disabled={updateMut.isPending}
            className="flex-1 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
          >
            {updateMut.isPending ? "Speichern…" : "Speichern"}
          </button>
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-sm border border-border text-muted-foreground hover:bg-muted">
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}

function BenutzerSection() {
  const { user: currentUser } = useAuthStore();
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState<UserEntry | null>(null);

  const { data: users = [], isLoading } = useQuery<UserEntry[]>({
    queryKey: ["users"],
    queryFn: () => usersApi.list().then(r => r.data),
  });

  return (
    <div className="bg-card rounded-2xl border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={18} className="text-muted-foreground" />
          <h2 className="font-semibold text-foreground">Benutzerverwaltung</h2>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium text-white"
          style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
        >
          <UserPlus size={13} /> Neu
        </button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Lade…</p>
      ) : (
        <div className="space-y-2">
          {users.map(u => {
            const badge = ROLE_BADGE[u.role] ?? { label: u.role, cssVar: "--ctp-overlay1" };
            const isSelf = u.id === currentUser?.id;
            return (
              <div
                key={u.id}
                className={`flex items-center gap-3 p-3 rounded-xl border transition-colors ${u.is_active ? "border-border hover:bg-muted/30" : "border-dashed border-border opacity-50"}`}
              >
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold text-white shrink-0"
                  style={{ backgroundColor: `rgb(var(${badge.cssVar}))` }}>
                  {u.email[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-foreground truncate">{u.email}</span>
                    {isSelf && <span className="text-xs text-muted-foreground">(du)</span>}
                    {!u.is_active && <span className="text-xs text-muted-foreground">· deaktiviert</span>}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs font-medium px-1.5 py-0.5 rounded-full"
                      style={{ backgroundColor: `rgb(var(${badge.cssVar}) / 0.15)`, color: `rgb(var(${badge.cssVar}))` }}>
                      {badge.label}
                    </span>
                    {u.has_employee && (
                      <span className="text-xs text-muted-foreground">· Mitarbeiter-Profil</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => setEditUser(u)}
                  className="p-2 rounded-lg hover:bg-muted text-muted-foreground shrink-0"
                  title="Bearbeiten"
                >
                  <Pencil size={14} />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {showCreate && <CreateUserModal onClose={() => setShowCreate(false)} />}
      {editUser && (
        <EditUserModal
          user={editUser}
          currentUserId={currentUser?.id ?? ""}
          onClose={() => setEditUser(null)}
        />
      )}
    </div>
  );
}

// ── API Keys Section ──────────────────────────────────────────────────────────

function ApiKeysSection() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newRawKey, setNewRawKey] = useState<string | null>(null);

  const { data: keys = [], isLoading } = useQuery<ApiKeyItem[]>({
    queryKey: ["api-keys"],
    queryFn: () => apiKeysApi.list().then(r => r.data),
  });

  const revokeMut = useMutation({
    mutationFn: (id: string) => apiKeysApi.revoke(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["api-keys"] });
      toast.success("API-Key widerrufen");
    },
    onError: () => toast.error("Fehler beim Widerrufen"),
  });

  const handleCreated = (rawKey: string) => {
    setShowCreate(false);
    setNewRawKey(rawKey);
  };

  return (
    <div className="bg-card rounded-xl border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <KeyRound size={18} style={{ color: "rgb(var(--ctp-mauve))" }} />
          <h2 className="font-semibold text-foreground">API-Keys</h2>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-border hover:bg-accent text-foreground transition-colors">
          <Plus size={13} /> Neuer Key
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        Erstelle API-Keys für externe Clients wie n8n oder Zapier. Keys werden gehasht gespeichert – der Klartext ist nur einmalig beim Erstellen sichtbar.
      </p>

      {newRawKey && (
        <NewKeyAlert rawKey={newRawKey} onDismiss={() => setNewRawKey(null)} />
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Lade…</p>
      ) : keys.length === 0 ? (
        <div className="text-center py-6 space-y-2">
          <p className="text-sm text-muted-foreground">Noch kein API-Key vorhanden</p>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 text-sm px-4 py-2 rounded-lg text-white"
            style={{ backgroundColor: "rgb(var(--ctp-mauve))" }}>
            <Plus size={14} /> Ersten Key erstellen
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map((k) => (
            <div key={k.id} className="flex items-start gap-3 px-4 py-3 rounded-lg border border-border bg-background">
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm text-foreground">{k.name}</span>
                  {k.scopes.map(scope => (
                    <span key={scope}
                      className="text-xs px-1.5 py-0.5 rounded font-medium"
                      style={{
                        backgroundColor: `rgb(var(${SCOPE_COLORS[scope as ScopeValue] ?? "--ctp-blue"}) / 0.12)`,
                        color: `rgb(var(${SCOPE_COLORS[scope as ScopeValue] ?? "--ctp-blue"}))`,
                      }}>
                      {SCOPE_LABELS[scope as ScopeValue] ?? scope}
                    </span>
                  ))}
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  <code className="text-xs font-mono text-muted-foreground">{k.key_prefix}</code>
                  <span className="text-xs text-muted-foreground">
                    Erstellt {format(new Date(k.created_at), "d. MMM yyyy", { locale: de })}
                  </span>
                  {k.last_used_at && (
                    <span className="text-xs text-muted-foreground">
                      Zuletzt genutzt {format(new Date(k.last_used_at), "d. MMM yyyy", { locale: de })}
                    </span>
                  )}
                  {k.expires_at && (
                    <span className="text-xs text-muted-foreground">
                      Ablauf {format(new Date(k.expires_at), "d. MMM yyyy", { locale: de })}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => { if (confirm(`API-Key "${k.name}" wirklich widerrufen?`)) revokeMut.mutate(k.id); }}
                disabled={revokeMut.isPending}
                className="shrink-0 p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors disabled:opacity-50"
                title="Key widerrufen">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateApiKeyModal
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}

// ── Webhooks ──────────────────────────────────────────────────────────────────

const WEBHOOK_EVENT_LABELS: Record<string, string> = {
  "shift.created":       "Dienst erstellt",
  "shift.updated":       "Dienst geändert",
  "shift.cancelled":     "Dienst storniert",
  "absence.approved":    "Abwesenheit genehmigt",
  "payroll.created":     "Abrechnung erstellt",
  "compliance.violation":"Compliance-Verstoß",
  "care_absence.created":"Betreuten-Abwesenheit erstellt",
};

function WebhookModal({ webhook, onClose, onSaved }: {
  webhook?: any;
  onClose: () => void;
  onSaved: () => void;
}) {
  const qc = useQueryClient();
  const isEdit = !!webhook;
  const allEvents = Object.keys(WEBHOOK_EVENT_LABELS);

  const [name, setName] = useState(webhook?.name ?? "");
  const [url, setUrl] = useState(webhook?.url ?? "");
  const [secret, setSecret] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>(webhook?.events ?? []);

  const saveMut = useMutation({
    mutationFn: () => isEdit
      ? webhooksApi.update(webhook.id, { name, url, events: selectedEvents, ...(secret ? { secret } : {}) })
      : webhooksApi.create({ name, url, events: selectedEvents, secret: secret || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["webhooks"] });
      toast.success(isEdit ? "Webhook gespeichert" : "Webhook erstellt");
      onSaved();
    },
    onError: () => toast.error("Fehler beim Speichern"),
  });

  const toggleEvent = (e: string) =>
    setSelectedEvents(prev => prev.includes(e) ? prev.filter(x => x !== e) : [...prev, e]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ backgroundColor: "rgba(0,0,0,0.5)" }}>
      <div className="bg-card rounded-2xl border border-border shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="font-semibold text-foreground">{isEdit ? "Webhook bearbeiten" : "Webhook erstellen"}</h2>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-accent text-muted-foreground"><Trash2 size={14} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Name</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="z.B. n8n Abrechnung"
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">URL</label>
            <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://..."
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Secret (optional, für HMAC-Signatur)</label>
            <input value={secret} onChange={e => setSecret(e.target.value)} placeholder={isEdit ? "Leer lassen = unverändert" : "Geheimschlüssel…"}
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-2">Events</label>
            <div className="space-y-1.5">
              {allEvents.map(evt => (
                <label key={evt} className="flex items-center gap-2 cursor-pointer select-none">
                  <input type="checkbox" checked={selectedEvents.includes(evt)} onChange={() => toggleEvent(evt)}
                    className="rounded" />
                  <span className="text-sm text-foreground">{WEBHOOK_EVENT_LABELS[evt]}</span>
                  <span className="text-xs text-muted-foreground font-mono ml-auto">{evt}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-border">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-border hover:bg-accent">Abbrechen</button>
          <button onClick={() => saveMut.mutate()} disabled={saveMut.isPending || !name || !url || selectedEvents.length === 0}
            className="px-4 py-2 text-sm rounded-lg text-white font-medium disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
            {saveMut.isPending ? "Speichert…" : (isEdit ? "Speichern" : "Erstellen")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Diensttypen Section ───────────────────────────────────────────────────────

interface ShiftType {
  id: string;
  name: string;
  color: string;
  description: string | null;
  reminder_enabled: boolean;
  reminder_minutes_before: number;
  is_active: boolean;
}

function ShiftTypeModal({ existing, onClose }: { existing?: ShiftType; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: existing?.name ?? "",
    color: existing?.color ?? "#4A90D9",
    description: existing?.description ?? "",
    reminder_enabled: existing?.reminder_enabled ?? false,
    reminder_minutes_before: existing?.reminder_minutes_before ?? 60,
  });

  const mut = useMutation({
    mutationFn: () =>
      existing
        ? shiftTypesApi.update(existing.id, {
            ...form,
            description: form.description || undefined,
          })
        : shiftTypesApi.create({
            ...form,
            description: form.description || undefined,
          }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shift-types"] });
      toast.success(existing ? "Diensttyp aktualisiert" : "Diensttyp angelegt");
      onClose();
    },
    onError: () => toast.error("Fehler beim Speichern"),
  });

  const PRESET_COLORS = [
    "#4A90D9", "#E74C3C", "#2ECC71", "#F39C12", "#9B59B6",
    "#1ABC9C", "#E67E22", "#34495E", "#E91E63", "#00BCD4",
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-card rounded-2xl border border-border w-full max-w-sm p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-foreground">
            {existing ? "Diensttyp bearbeiten" : "Neuer Diensttyp"}
          </h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground">
            <Plus size={16} className="rotate-45" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Name</label>
            <input
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="z.B. Nachtdienst"
              className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Farbe</label>
            <div className="flex items-center gap-2 flex-wrap">
              {PRESET_COLORS.map(c => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setForm(f => ({ ...f, color: c }))}
                  className="w-7 h-7 rounded-full border-2 transition-transform hover:scale-110"
                  style={{
                    backgroundColor: c,
                    borderColor: form.color === c ? "rgb(var(--ctp-blue))" : "transparent",
                  }}
                />
              ))}
              <input
                type="color"
                value={form.color}
                onChange={e => setForm(f => ({ ...f, color: e.target.value }))}
                className="w-7 h-7 rounded-full cursor-pointer border border-border bg-transparent"
                title="Eigene Farbe"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Beschreibung (optional)</label>
            <input
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="z.B. Betreuung von 22–6 Uhr"
              className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="rounded-xl border border-border p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground flex items-center gap-1.5">
                <Bell size={14} /> Erinnerung
              </span>
              <button
                type="button"
                onClick={() => setForm(f => ({ ...f, reminder_enabled: !f.reminder_enabled }))}
                className={`relative w-10 h-5 rounded-full transition-colors ${form.reminder_enabled ? "bg-blue-500" : "bg-muted-foreground/30"}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.reminder_enabled ? "translate-x-5" : ""}`} />
              </button>
            </div>
            {form.reminder_enabled && (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={5}
                  max={1440}
                  step={5}
                  value={form.reminder_minutes_before}
                  onChange={e => setForm(f => ({ ...f, reminder_minutes_before: parseInt(e.target.value) || 60 }))}
                  className="w-20 border border-border rounded-lg px-2 py-1 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <span className="text-xs text-muted-foreground">Minuten vor Dienstbeginn</span>
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-2 pt-1">
          <button
            onClick={() => mut.mutate()}
            disabled={!form.name || mut.isPending}
            className="flex-1 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
          >
            {mut.isPending ? "Speichern…" : "Speichern"}
          </button>
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-sm border border-border text-muted-foreground hover:bg-muted">
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}

function ShiftTypesSection() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<null | "create" | ShiftType>(null);

  const { data: shiftTypes = [] } = useQuery<ShiftType[]>({
    queryKey: ["shift-types"],
    queryFn: () => shiftTypesApi.list().then(r => r.data),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => shiftTypesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shift-types"] });
      toast.success("Diensttyp deaktiviert");
    },
    onError: () => toast.error("Fehler beim Löschen"),
  });

  return (
    <div className="bg-card rounded-2xl border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers size={18} className="text-muted-foreground" />
          <h2 className="font-semibold text-foreground">Diensttypen</h2>
        </div>
        <button
          onClick={() => setModal("create")}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium text-white"
          style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
        >
          <Plus size={13} /> Neu
        </button>
      </div>

      {shiftTypes.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-4">
          Noch keine Diensttypen angelegt.
        </p>
      ) : (
        <div className="space-y-2">
          {shiftTypes.map(st => (
            <div key={st.id} className="flex items-center gap-3 p-3 rounded-xl border border-border hover:bg-muted/30 transition-colors">
              <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: st.color }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{st.name}</span>
                  {st.reminder_enabled ? (
                    <span title={`Erinnerung ${st.reminder_minutes_before} Min. vorher`}>
                      <Bell size={12} className="text-muted-foreground" />
                    </span>
                  ) : (
                    <span title="Keine Erinnerung">
                      <BellOff size={12} className="text-muted-foreground/40" />
                    </span>
                  )}
                </div>
                {st.description && (
                  <p className="text-xs text-muted-foreground truncate">{st.description}</p>
                )}
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setModal(st)}
                  className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground"
                >
                  <Pencil size={13} />
                </button>
                <button
                  onClick={() => {
                    if (confirm(`Diensttyp "${st.name}" deaktivieren?`)) deleteMut.mutate(st.id);
                  }}
                  className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <ShiftTypeModal
          existing={modal === "create" ? undefined : modal}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}

// ── Vertragstypen Section ─────────────────────────────────────────────────────

interface ContractTypeItem {
  id: string;
  name: string;
  description?: string;
  contract_category: string;
  hourly_rate: number;
  monthly_hours_limit?: number;
  annual_salary_limit?: number;
  annual_hours_target?: number;
  weekly_hours?: number;
  is_active: boolean;
  employee_count: number;
}

const CONTRACT_CATEGORY_LABELS: Record<string, string> = {
  minijob: "Minijob",
  part_time: "Teilzeit",
  full_time: "Vollzeit",
};

function ContractTypeModal({
  existing, onClose,
}: {
  existing?: ContractTypeItem;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name,         setName]         = useState(existing?.name ?? "");
  const [desc,         setDesc]         = useState(existing?.description ?? "");
  const [category,     setCategory]     = useState(existing?.contract_category ?? "minijob");
  const [rate,         setRate]         = useState(String(existing?.hourly_rate ?? ""));
  const [monthlyLim,   setMonthlyLim]   = useState(String(existing?.monthly_hours_limit ?? ""));
  const [annualSal,    setAnnualSal]    = useState(String(existing?.annual_salary_limit ?? "6672"));
  const [weeklyH,      setWeeklyH]      = useState(String(existing?.weekly_hours ?? ""));
  const [annualH,      setAnnualH]      = useState(String(existing?.annual_hours_target ?? ""));
  const [applyFrom,    setApplyFrom]    = useState("");
  const [note,         setNote]         = useState("");

  const isEdit = !!existing;

  const mut = useMutation({
    mutationFn: () => {
      const payload = {
        name, description: desc || undefined,
        contract_category: category,
        hourly_rate: parseFloat(rate),
        monthly_hours_limit: monthlyLim ? parseFloat(monthlyLim) : undefined,
        annual_salary_limit: annualSal ? parseFloat(annualSal) : undefined,
        annual_hours_target: annualH ? parseFloat(annualH) : undefined,
        weekly_hours: weeklyH ? parseFloat(weeklyH) : undefined,
      };
      if (isEdit) {
        return contractTypesApi.update(existing.id, {
          ...payload,
          apply_from: applyFrom || undefined,
          note: note || undefined,
        });
      }
      return contractTypesApi.create(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contract-types"] });
      toast.success(isEdit ? "Vertragstyp aktualisiert" : "Vertragstyp angelegt");
      onClose();
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail ?? "Fehler"),
  });

  const iCls = "w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring";
  const lCls = "block text-xs font-medium text-muted-foreground mb-1";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-xl border border-border w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 className="font-semibold text-foreground">{isEdit ? "Vertragstyp bearbeiten" : "Neuer Vertragstyp"}</h2>
          <button onClick={onClose} className="p-2 rounded hover:bg-accent text-muted-foreground"><Trash2 size={14} /></button>
        </div>
        <div className="px-5 pb-5 space-y-3">
          <div><label className={lCls}>Name</label>
            <input className={iCls} value={name} onChange={e => setName(e.target.value)} placeholder="z.B. Minijob Standard" />
          </div>
          <div><label className={lCls}>Beschreibung (optional)</label>
            <input className={iCls} value={desc} onChange={e => setDesc(e.target.value)} />
          </div>
          <div>
            <label className={lCls}>Vertragsart</label>
            <select className={iCls} value={category} onChange={e => setCategory(e.target.value)}>
              <option value="minijob">Minijob</option>
              <option value="part_time">Teilzeit</option>
              <option value="full_time">Vollzeit</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={lCls}>Stundenlohn (€)</label>
              <input type="number" step="0.01" className={iCls} value={rate} onChange={e => setRate(e.target.value)} />
            </div>
            <div><label className={lCls}>Wochenst. (optional)</label>
              <input type="number" step="0.5" className={iCls} value={weeklyH} onChange={e => setWeeklyH(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={lCls}>Monatsl. Std.-Limit (opt.)</label>
              <input type="number" step="0.5" className={iCls} value={monthlyLim} onChange={e => setMonthlyLim(e.target.value)} />
            </div>
            <div><label className={lCls}>Jahresgehaltslimit € (opt.)</label>
              <input type="number" step="1" className={iCls} value={annualSal} onChange={e => setAnnualSal(e.target.value)} />
            </div>
          </div>
          <div><label className={lCls}>Jahressoll Std. (optional)</label>
            <input type="number" step="1" className={iCls} value={annualH} onChange={e => setAnnualH(e.target.value)} />
          </div>
          {isEdit && (
            <>
              <hr className="border-border" />
              <p className="text-xs text-muted-foreground">
                Lohnparameter-Änderungen werden als neue Vertragsperiode für alle {existing.employee_count} zugewiesenen Mitarbeiter angelegt, wenn „Gültig ab" gesetzt ist.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div><label className={lCls}>Gültig ab (leer = nur Typ)</label>
                  <input type="date" className={iCls} value={applyFrom} onChange={e => setApplyFrom(e.target.value)} />
                </div>
                <div><label className={lCls}>Notiz für Vertragshistorie</label>
                  <input className={iCls} value={note} onChange={e => setNote(e.target.value)} placeholder="optional" />
                </div>
              </div>
            </>
          )}
          <button onClick={() => mut.mutate()} disabled={mut.isPending || !name || !rate}
            className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
            {mut.isPending ? "Wird gespeichert…" : isEdit ? "Änderungen speichern" : "Vertragstyp anlegen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function VertragstypenSection() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<null | "create" | ContractTypeItem>(null);

  const { data: contractTypes = [] } = useQuery<ContractTypeItem[]>({
    queryKey: ["contract-types"],
    queryFn: () => contractTypesApi.list().then(r => r.data),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => contractTypesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["contract-types"] });
      toast.success("Vertragstyp deaktiviert");
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail ?? "Fehler beim Löschen"),
  });

  const activeTypes = contractTypes.filter((ct: ContractTypeItem) => ct.is_active);

  return (
    <div className="bg-card rounded-2xl border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={18} className="text-muted-foreground" />
          <h2 className="font-semibold text-foreground">Vertragstypen</h2>
        </div>
        <button onClick={() => setModal("create")}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium text-white"
          style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
          <Plus size={13} /> Neu
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        Vertragstypen bündeln Lohnparameter für Gruppen. Bei Änderung eines Typs werden alle
        zugewiesenen Mitarbeiter automatisch mit neuem Vertragseintrag aktualisiert.
      </p>

      {activeTypes.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-4">
          Noch keine Vertragstypen angelegt.
        </p>
      ) : (
        <div className="space-y-2">
          {activeTypes.map((ct: ContractTypeItem) => (
            <div key={ct.id} className="flex items-center gap-3 p-3 rounded-xl border border-border hover:bg-muted/30 transition-colors">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-foreground">{ct.name}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded-full"
                    style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.12)", color: "rgb(var(--ctp-blue))" }}>
                    {CONTRACT_CATEGORY_LABELS[ct.contract_category] ?? ct.contract_category}
                  </span>
                  <span className="text-xs text-muted-foreground">{ct.hourly_rate.toFixed(2)} €/h</span>
                  {ct.employee_count > 0 && (
                    <span className="text-xs text-muted-foreground">{ct.employee_count} MA</span>
                  )}
                </div>
                {ct.description && (
                  <p className="text-xs text-muted-foreground truncate mt-0.5">{ct.description}</p>
                )}
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => setModal(ct)}
                  className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground">
                  <Pencil size={13} />
                </button>
                <button onClick={() => {
                  if (ct.employee_count > 0) {
                    toast.error(`${ct.employee_count} Mitarbeiter zugewiesen – erst entfernen`);
                  } else if (confirm(`Vertragstyp "${ct.name}" deaktivieren?`)) {
                    deleteMut.mutate(ct.id);
                  }
                }}
                  className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <ContractTypeModal
          existing={modal === "create" ? undefined : modal}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}

// ── Webhooks Section ──────────────────────────────────────────────────────────

function WebhooksSection() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<"create" | { webhook: any } | null>(null);

  const { data: webhooks = [] } = useQuery<any[]>({
    queryKey: ["webhooks"],
    queryFn: () => webhooksApi.list().then(r => r.data),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => webhooksApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["webhooks"] }); toast.success("Webhook gelöscht"); },
    onError: () => toast.error("Fehler beim Löschen"),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      webhooksApi.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["webhooks"] }),
  });

  const testMut = useMutation({
    mutationFn: (id: string) => webhooksApi.test(id),
    onSuccess: (r) => {
      if (r.data.success) toast.success("Test-Ping erfolgreich");
      else toast.error(`Test fehlgeschlagen: ${r.data.message}`);
    },
    onError: () => toast.error("Test fehlgeschlagen"),
  });

  return (
    <div className="bg-card rounded-xl border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Webhook size={18} style={{ color: "rgb(var(--ctp-teal))" }} />
          <h2 className="font-semibold text-foreground">Webhooks</h2>
        </div>
        <button onClick={() => setModal("create")}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white"
          style={{ backgroundColor: "rgb(var(--ctp-teal))" }}>
          <Plus size={13} /> Webhook hinzufügen
        </button>
      </div>

      <p className="text-xs text-muted-foreground">
        Empfange VERA-Events in n8n, Make oder eigenen Endpoints (HTTP POST JSON).
        Mit einem Secret wird jede Anfrage mit <code className="font-mono bg-accent px-1 rounded">X-VERA-Signature: sha256=…</code> signiert.
      </p>

      {webhooks.length === 0 ? (
        <p className="text-sm text-muted-foreground">Noch keine Webhooks konfiguriert.</p>
      ) : (
        <div className="space-y-2">
          {webhooks.map((wh: any) => (
            <div key={wh.id} className="border border-border rounded-lg p-3 space-y-2">
              <div className="flex items-center gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-foreground">{wh.name}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${wh.is_active ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground"}`}>
                      {wh.is_active ? "Aktiv" : "Pausiert"}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground truncate font-mono">{wh.url}</p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={() => testMut.mutate(wh.id)} disabled={testMut.isPending} title="Test senden"
                    className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground">
                    <Play size={13} />
                  </button>
                  <button onClick={() => setModal({ webhook: wh })} title="Bearbeiten"
                    className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground">
                    <Pencil size={13} />
                  </button>
                  <button onClick={() => toggleMut.mutate({ id: wh.id, is_active: !wh.is_active })}
                    title={wh.is_active ? "Pausieren" : "Aktivieren"}
                    className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground">
                    {wh.is_active ? <EyeOff size={13} /> : <Eye size={13} />}
                  </button>
                  <button onClick={() => { if (confirm(`Webhook "${wh.name}" löschen?`)) deleteMut.mutate(wh.id); }}
                    className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {wh.events.map((evt: string) => (
                  <span key={evt} className="text-xs px-1.5 py-0.5 rounded font-mono bg-accent text-muted-foreground">
                    {evt}
                  </span>
                ))}
              </div>
              {wh.last_triggered && (
                <p className="text-xs text-muted-foreground">
                  Zuletzt ausgelöst: {new Date(wh.last_triggered).toLocaleString("de-DE")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {modal === "create" && (
        <WebhookModal onClose={() => setModal(null)} onSaved={() => setModal(null)} />
      )}
      {modal && typeof modal === "object" && (
        <WebhookModal webhook={modal.webhook} onClose={() => setModal(null)} onSaved={() => setModal(null)} />
      )}
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

      {/* Kalenderfreigabe (alle) */}
      <KalenderfreigabeSection />

      {/* SMTP-Konfiguration (admin only) */}
      {role === "admin" && <SMTPSection />}

      {/* Benutzerverwaltung (admin only) */}
      {role === "admin" && <BenutzerSection />}

      {/* API-Keys (admin only) */}
      {role === "admin" && <ApiKeysSection />}

      {/* Diensttypen (admin/manager) */}
      {isPrivileged && <ShiftTypesSection />}

      {/* Vertragstypen (admin/manager) */}
      {isPrivileged && <VertragstypenSection />}

      {/* Webhooks (admin only) */}
      {role === "admin" && <WebhooksSection />}

      {/* Ferienprofile (admin/manager only) */}
      {isPrivileged && <FerienprofileSection />}
    </div>
  );
}
