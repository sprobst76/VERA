"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  Check,
  X,
  Clock,
  Mail,
  MessageCircle,
  AlertCircle,
  Save,
  Loader2,
  Info,
  Smartphone,
} from "lucide-react";
import { notificationsApi, employeesApi } from "@/lib/api";
import { enablePushNotifications, disablePushNotifications } from "@/components/shared/PushManager";
import { useAuthStore } from "@/store/auth";
import toast from "react-hot-toast";
import { format, parseISO } from "date-fns";
import { de } from "date-fns/locale";

/* ── Typen ─────────────────────────────────────────────────────────────────── */
interface NotificationLog {
  id: string;
  employee_id: string | null;
  channel: string;
  event_type: string;
  subject: string | null;
  status: string;
  sent_at: string | null;
  error: string | null;
  created_at: string;
}

interface Preferences {
  telegram_chat_id: string | null;
  quiet_hours_start: string;
  quiet_hours_end: string;
  notification_prefs: {
    channels?: { email?: boolean; telegram?: boolean };
    events?: { shift_assigned?: boolean; shift_changed?: boolean; shift_reminder?: boolean; absence_approved?: boolean; absence_rejected?: boolean };
  };
}

interface Employee {
  id: string;
  first_name: string;
  last_name: string;
}

/* ── Hilfsfunktionen ───────────────────────────────────────────────────────── */
const CHANNEL_LABELS: Record<string, string> = {
  email:    "E-Mail",
  telegram: "Telegram",
  push:     "Web Push",
  all:      "Alle",
};

const EVENT_LABELS: Record<string, string> = {
  shift_assigned:   "Schicht-Zuweisung",
  shift_changed:    "Dienst geändert",
  shift_reminder:   "Dienst-Erinnerung",
  absence_approved: "Abwesenheit genehmigt",
  absence_rejected: "Abwesenheit abgelehnt",
};

const STATUS_STYLE: Record<string, { bg: string; fg: string; label: string }> = {
  sent:                 { bg: "rgb(var(--ctp-green) / 0.12)",  fg: "rgb(var(--ctp-green))",  label: "Gesendet" },
  failed:               { bg: "rgb(var(--ctp-red) / 0.12)",    fg: "rgb(var(--ctp-red))",    label: "Fehler"   },
  pending:              { bg: "rgb(var(--ctp-yellow) / 0.12)", fg: "rgb(var(--ctp-yellow))", label: "Ausstehend" },
  skipped_quiet_hours:  { bg: "rgb(var(--ctp-overlay0) / 0.2)", fg: "rgb(var(--ctp-subtext0))", label: "Stille Stunden" },
};

/* ── Haupt-Komponente ──────────────────────────────────────────────────────── */
export default function NotificationsPage() {
  const { user } = useAuthStore();
  const qc       = useQueryClient();
  const isAdmin  = user?.role !== "employee";

  const [tab, setTab]                   = useState<"log" | "settings">("log");
  const [filterChannel, setFilterChannel] = useState("");
  const [filterStatus, setFilterStatus]   = useState("");
  const [filterEmployee, setFilterEmployee] = useState("");

  // Web Push state
  const [pushSupported, setPushSupported] = useState(false);
  const [pushEnabled, setPushEnabled]     = useState(false);
  const [pushLoading, setPushLoading]     = useState(false);

  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
    setPushSupported(true);
    navigator.serviceWorker.ready.then((reg) =>
      reg.pushManager.getSubscription().then((sub) => setPushEnabled(!!sub))
    );
  }, []);

  // ── Daten laden ────────────────────────────────────────────────────────────
  const { data: employees = [] } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list(false).then((r) => r.data),
    enabled: isAdmin,
  });

  const logParams: Record<string, string> = {};
  if (filterChannel)  logParams.channel     = filterChannel;
  if (filterStatus)   logParams.status      = filterStatus;
  if (filterEmployee) logParams.employee_id = filterEmployee;

  const { data: logs = [], isLoading: logsLoading } = useQuery<NotificationLog[]>({
    queryKey: ["notification-logs", logParams],
    queryFn: () => notificationsApi.getLogs(logParams).then((r) => r.data),
  });

  const { data: prefs, isLoading: prefsLoading } = useQuery<Preferences>({
    queryKey: ["notification-prefs"],
    queryFn: () => notificationsApi.getPreferences().then((r) => r.data),
  });

  // ── Settings-State (lokal, bis "Speichern") ─────────────────────────────
  const [chatId, setChatId]                   = useState<string>("");
  const [quietStart, setQuietStart]           = useState<string>("21:00");
  const [quietEnd, setQuietEnd]               = useState<string>("07:00");
  const [emailOn, setEmailOn]                 = useState(true);
  const [telegramOn, setTelegramOn]           = useState(false);
  const [evtAssigned, setEvtAssigned]             = useState(true);
  const [evtChanged, setEvtChanged]               = useState(true);
  const [evtReminder, setEvtReminder]             = useState(true);
  const [evtAbsenceApproved, setEvtAbsenceApproved] = useState(true);
  const [evtAbsenceRejected, setEvtAbsenceRejected] = useState(true);
  const [prefsSynced, setPrefsSynced]             = useState(false);

  // Prefs in lokalen State übernehmen (einmalig)
  if (prefs && !prefsSynced) {
    setChatId(prefs.telegram_chat_id ?? "");
    setQuietStart(prefs.quiet_hours_start?.slice(0, 5) ?? "21:00");
    setQuietEnd(prefs.quiet_hours_end?.slice(0, 5) ?? "07:00");
    const ch = prefs.notification_prefs?.channels ?? {};
    const ev = prefs.notification_prefs?.events   ?? {};
    setEmailOn(ch.email    !== false);
    setTelegramOn(ch.telegram === true);
    setEvtAssigned(ev.shift_assigned !== false);
    setEvtChanged(ev.shift_changed   !== false);
    setEvtReminder(ev.shift_reminder !== false);
    setEvtAbsenceApproved(ev.absence_approved !== false);
    setEvtAbsenceRejected(ev.absence_rejected !== false);
    setPrefsSynced(true);
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      notificationsApi.updatePreferences({
        telegram_chat_id: chatId || null,
        quiet_hours_start: quietStart,
        quiet_hours_end:   quietEnd,
        notification_prefs: {
          channels: { email: emailOn, telegram: telegramOn },
          events:   { shift_assigned: evtAssigned, shift_changed: evtChanged, shift_reminder: evtReminder, absence_approved: evtAbsenceApproved, absence_rejected: evtAbsenceRejected },
        },
      }),
    onSuccess: () => {
      toast.success("Einstellungen gespeichert");
      qc.invalidateQueries({ queryKey: ["notification-prefs"] });
    },
    onError: () => toast.error("Speichern fehlgeschlagen"),
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Benachrichtigungen</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          E-Mail, Telegram und Browser-Push Benachrichtigungen
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {(["log", "settings"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-4 py-2 text-sm font-medium transition-colors"
            style={
              tab === t
                ? { color: "rgb(var(--ctp-blue))", borderBottom: "2px solid rgb(var(--ctp-blue))" }
                : { color: "rgb(var(--muted-foreground))" }
            }
          >
            {t === "log" ? "Verlauf" : "Einstellungen"}
          </button>
        ))}
      </div>

      {/* ── Tab: Verlauf ───────────────────────────────────────────────────── */}
      {tab === "log" && (
        <div className="space-y-4">
          {/* Filter */}
          <div className="bg-card rounded-xl border border-border p-4 flex flex-wrap gap-3 items-end">
            {isAdmin && (
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Mitarbeiter</label>
                <select
                  value={filterEmployee}
                  onChange={(e) => setFilterEmployee(e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-sm"
                >
                  <option value="">Alle</option>
                  {employees.map((e) => (
                    <option key={e.id} value={e.id}>{e.first_name} {e.last_name}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Kanal</label>
              <select
                value={filterChannel}
                onChange={(e) => setFilterChannel(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-sm"
              >
                <option value="">Alle</option>
                <option value="email">E-Mail</option>
                <option value="telegram">Telegram</option>
                <option value="push">Web Push</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Status</label>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-sm"
              >
                <option value="">Alle</option>
                <option value="sent">Gesendet</option>
                <option value="failed">Fehler</option>
                <option value="pending">Ausstehend</option>
                <option value="skipped_quiet_hours">Stille Stunden</option>
              </select>
            </div>
            {(filterChannel || filterStatus || filterEmployee) && (
              <button
                onClick={() => { setFilterChannel(""); setFilterStatus(""); setFilterEmployee(""); }}
                className="text-xs text-muted-foreground hover:text-foreground px-2 py-1.5"
              >
                Zurücksetzen
              </button>
            )}
          </div>

          {/* Tabelle */}
          <div className="bg-card rounded-xl border border-border overflow-hidden">
            {logsLoading ? (
              <div className="flex items-center justify-center h-32 text-muted-foreground text-sm gap-2">
                <Loader2 size={16} className="animate-spin" /> Wird geladen…
              </div>
            ) : logs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-36 gap-3">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
                  style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.12)" }}>
                  <Bell size={22} style={{ color: "rgb(var(--ctp-blue))" }} />
                </div>
                <div className="text-sm text-muted-foreground">Noch keine Benachrichtigungen gesendet</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Datum</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Kanal</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Event</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Betreff</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log, idx) => {
                      const s = STATUS_STYLE[log.status] ?? STATUS_STYLE.pending;
                      return (
                        <tr
                          key={log.id}
                          className="border-b border-border last:border-0"
                          style={idx % 2 === 1 ? { backgroundColor: "rgb(var(--ctp-surface0) / 0.3)" } : {}}
                        >
                          <td className="px-4 py-3 text-muted-foreground whitespace-nowrap text-xs">
                            {format(parseISO(log.created_at), "dd.MM.yy HH:mm", { locale: de })}
                          </td>
                          <td className="px-4 py-3">
                            <span className="inline-flex items-center gap-1 text-xs">
                              {log.channel === "telegram"
                                ? <MessageCircle size={12} />
                                : log.channel === "email"
                                ? <Mail size={12} />
                                : <Bell size={12} />}
                              {CHANNEL_LABELS[log.channel] ?? log.channel}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-muted-foreground">
                            {EVENT_LABELS[log.event_type] ?? log.event_type}
                          </td>
                          <td className="px-4 py-3 text-xs text-foreground max-w-xs truncate">
                            {log.subject ?? "–"}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                              style={{ backgroundColor: s.bg, color: s.fg }}
                              title={log.error ?? undefined}
                            >
                              {log.status === "sent"   ? <Check size={10} /> :
                               log.status === "failed" ? <X size={10} />     :
                               log.status === "skipped_quiet_hours" ? <Clock size={10} /> :
                               <AlertCircle size={10} />}
                              {s.label}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Tab: Einstellungen ─────────────────────────────────────────────── */}
      {tab === "settings" && (
        <div className="space-y-5 max-w-xl">
          {prefsLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 size={16} className="animate-spin" /> Wird geladen…
            </div>
          ) : (
            <>
              {/* Telegram Chat-ID */}
              <div className="bg-card rounded-xl border border-border p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <MessageCircle size={18} style={{ color: "rgb(var(--ctp-blue))" }} />
                  <span className="font-medium text-foreground">Telegram</span>
                </div>
                <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/40 rounded-lg px-3 py-2">
                  <Info size={13} className="shrink-0 mt-0.5" />
                  <span>
                    Schreibe <strong>/start</strong> an den Bot, dann tippe{" "}
                    <strong>@userinfobot</strong> in Telegram um deine Chat-ID zu erhalten.
                  </span>
                </div>
                <div>
                  <label className="block text-xs text-muted-foreground mb-1">Chat-ID</label>
                  <input
                    type="text"
                    value={chatId}
                    onChange={(e) => setChatId(e.target.value)}
                    placeholder="z.B. 123456789"
                    className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm"
                  />
                </div>
              </div>

              {/* Web Push */}
              <div className="bg-card rounded-xl border border-border p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <Smartphone size={18} style={{ color: "rgb(var(--ctp-mauve))" }} />
                  <span className="font-medium text-foreground">Browser-Push</span>
                </div>
                {!pushSupported ? (
                  <p className="text-xs text-muted-foreground">
                    Dein Browser unterstützt keine Push-Benachrichtigungen.
                  </p>
                ) : (
                  <>
                    <p className="text-xs text-muted-foreground">
                      Erhalte Benachrichtigungen direkt im Browser – auch wenn die Seite nicht geöffnet ist.
                    </p>
                    <div className="flex items-center justify-between">
                      <div className="text-sm text-foreground">
                        {pushEnabled ? (
                          <span style={{ color: "rgb(var(--ctp-green))" }}>
                            <Check size={14} className="inline mr-1" />Aktiviert
                          </span>
                        ) : (
                          <span className="text-muted-foreground">Nicht aktiviert</span>
                        )}
                      </div>
                      <button
                        onClick={async () => {
                          setPushLoading(true);
                          try {
                            if (pushEnabled) {
                              await disablePushNotifications();
                              setPushEnabled(false);
                            } else {
                              const sub = await enablePushNotifications();
                              setPushEnabled(!!sub);
                              if (!sub) toast.error("Push-Erlaubnis verweigert oder Fehler");
                            }
                          } finally {
                            setPushLoading(false);
                          }
                        }}
                        disabled={pushLoading}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-border hover:bg-muted disabled:opacity-50 transition-colors"
                        style={pushEnabled ? { color: "rgb(var(--ctp-red))" } : { color: "rgb(var(--ctp-mauve))" }}
                      >
                        {pushLoading
                          ? <Loader2 size={13} className="animate-spin" />
                          : <Smartphone size={13} />}
                        {pushEnabled ? "Deaktivieren" : "Aktivieren"}
                      </button>
                    </div>
                  </>
                )}
              </div>

              {/* Kanäle */}
              <div className="bg-card rounded-xl border border-border p-5 space-y-3">
                <span className="font-medium text-foreground">Kanäle</span>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={emailOn}
                      onChange={(e) => setEmailOn(e.target.checked)}
                      className="w-4 h-4 rounded"
                    />
                    <Mail size={15} className="text-muted-foreground" />
                    <span className="text-sm text-foreground">E-Mail Benachrichtigungen</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={telegramOn}
                      onChange={(e) => setTelegramOn(e.target.checked)}
                      className="w-4 h-4 rounded"
                    />
                    <MessageCircle size={15} className="text-muted-foreground" />
                    <span className="text-sm text-foreground">Telegram Benachrichtigungen</span>
                  </label>
                </div>
              </div>

              {/* Events */}
              <div className="bg-card rounded-xl border border-border p-5 space-y-3">
                <span className="font-medium text-foreground">Ereignisse</span>
                <div className="space-y-2">
                  {[
                    { label: "Neue Schicht-Zuweisung", value: evtAssigned, set: setEvtAssigned },
                    { label: "Dienst geändert (Zeit/Ort)", value: evtChanged, set: setEvtChanged },
                    { label: "Erinnerung vor dem Dienst", value: evtReminder, set: setEvtReminder },
                    { label: "Abwesenheit genehmigt", value: evtAbsenceApproved, set: setEvtAbsenceApproved },
                    { label: "Abwesenheit abgelehnt", value: evtAbsenceRejected, set: setEvtAbsenceRejected },
                  ].map(({ label, value, set }) => (
                    <label key={label} className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={value}
                        onChange={(e) => set(e.target.checked)}
                        className="w-4 h-4 rounded"
                      />
                      <span className="text-sm text-foreground">{label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Quiet Hours */}
              <div className="bg-card rounded-xl border border-border p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <Clock size={17} className="text-muted-foreground" />
                  <span className="font-medium text-foreground">Stille Stunden</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  In diesem Zeitraum werden keine Benachrichtigungen gesendet.
                </p>
                <div className="flex gap-4 items-center">
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Von</label>
                    <input
                      type="time"
                      value={quietStart}
                      onChange={(e) => setQuietStart(e.target.value)}
                      className="px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">Bis</label>
                    <input
                      type="time"
                      value={quietEnd}
                      onChange={(e) => setQuietEnd(e.target.value)}
                      className="px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm"
                    />
                  </div>
                </div>
              </div>

              {/* Speichern */}
              <button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
                className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
              >
                {saveMutation.isPending
                  ? <Loader2 size={14} className="animate-spin" />
                  : <Save size={14} />}
                Einstellungen speichern
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
