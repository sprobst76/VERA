"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { employeesApi, shiftsApi } from "@/lib/api";
import { formatDate, SHIFT_STATUS_LABELS } from "@/lib/utils";
import { Users, Clock, CalendarCheck, AlertTriangle, HandshakeIcon, CalendarDays, Copy, Check as CheckIcon } from "lucide-react";
import { useState } from "react";
import { format, startOfMonth, endOfMonth, parseISO } from "date-fns";
import { de } from "date-fns/locale";
import { useAuthStore } from "@/store/auth";
import toast from "react-hot-toast";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://192.168.0.144:31367";

/* ── iCal-Abo-Sektion ────────────────────────────────────────────── */
function ICalSection({ user, isPrivileged }: { user: any; isPrivileged: boolean }) {
  const [copied, setCopied] = useState(false);

  // Employee gets their employee ical_token from /employees/me
  // Admin/Manager get their user ical_token from /auth/me (already in user store)
  const { data: ownProfile } = useQuery({
    queryKey: ["employees", "me"],
    queryFn: () => import("@/lib/api").then(m => m.employeesApi.me().then(r => r.data)),
    enabled: !isPrivileged,
    retry: false,
  });

  const token = isPrivileged
    ? user?.ical_token
    : (ownProfile as any)?.ical_token;

  if (!token) return null;

  const icalUrl = `${API_URL}/calendar/${token}.ics`;

  function copyUrl() {
    navigator.clipboard.writeText(icalUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="bg-card rounded-xl border border-border p-4">
      <div className="flex items-center gap-2 mb-3">
        <CalendarDays size={18} style={{ color: "rgb(var(--ctp-teal))" }} />
        <h2 className="font-semibold text-foreground">Kalender-Abo</h2>
      </div>
      <p className="text-xs text-muted-foreground mb-3">
        {isPrivileged
          ? "Abonniere diesen Feed in Google Calendar, Apple Calendar oder Outlook – du siehst dann alle Dienste aller Mitarbeiter."
          : "Abonniere diesen Feed in Google Calendar, Apple Calendar oder Outlook – du siehst dann deine eigenen Dienste."}
      </p>

      {/* URL box */}
      <div className="flex gap-2">
        <div className="flex-1 bg-muted rounded-lg px-3 py-2 text-xs font-mono text-muted-foreground truncate select-all">
          {icalUrl}
        </div>
        <button
          onClick={copyUrl}
          className="shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          style={copied
            ? { backgroundColor: "rgb(var(--ctp-green) / 0.15)", color: "rgb(var(--ctp-green))" }
            : { backgroundColor: "rgb(var(--ctp-teal) / 0.12)", color: "rgb(var(--ctp-teal))" }
          }
        >
          {copied ? <CheckIcon size={13} /> : <Copy size={13} />}
          {copied ? "Kopiert!" : "Kopieren"}
        </button>
      </div>

      {/* Anleitung */}
      <details className="mt-3">
        <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground select-none">
          Anleitung: In Google Calendar einbinden ▸
        </summary>
        <ol className="mt-2 space-y-1 text-xs text-muted-foreground list-decimal list-inside">
          <li>Google Calendar öffnen → links auf <strong>„+"</strong> neben „Andere Kalender"</li>
          <li><strong>„Per URL"</strong> auswählen</li>
          <li>Obige URL einfügen → <strong>„Kalender hinzufügen"</strong></li>
          <li>Google aktualisiert den Kalender automatisch (ca. alle 24h)</li>
        </ol>
        <p className="mt-1.5 text-xs text-muted-foreground">
          <strong>Apple Calendar:</strong> Ablage → Neues Kalenderabonnement → URL einfügen<br />
          <strong>Outlook:</strong> Kalender hinzufügen → Aus Internet abonnieren → URL einfügen
        </p>
      </details>
    </div>
  );
}

const STAT_COLORS: Record<string, string> = {
  blue:  "--ctp-blue",
  green: "--ctp-green",
  mauve: "--ctp-mauve",
  peach: "--ctp-peach",
};

export default function DashboardPage() {
  const { user } = useAuthStore();
  const isPrivileged = user?.role === "admin" || user?.role === "manager";
  const qc = useQueryClient();
  const today = new Date();
  const monthStart = format(startOfMonth(today), "yyyy-MM-dd");
  const monthEnd = format(endOfMonth(today), "yyyy-MM-dd");

  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list().then((r) => r.data),
  });

  const { data: shifts } = useQuery({
    queryKey: ["shifts", monthStart, monthEnd],
    queryFn: () =>
      shiftsApi.list({ from_date: monthStart, to_date: monthEnd }).then((r) => r.data),
  });

  // Open shifts in next 30 days (for claim functionality)
  const nextMonth = format(new Date(today.getTime() + 30 * 86400000), "yyyy-MM-dd");
  const { data: openShifts = [] } = useQuery({
    queryKey: ["shifts-open", format(today, "yyyy-MM-dd"), nextMonth],
    queryFn: () =>
      shiftsApi.list({ from_date: format(today, "yyyy-MM-dd"), to_date: nextMonth }).then(r =>
        (r.data as any[]).filter((s: any) => !s.employee_id && s.status === "planned")
      ),
    enabled: !isPrivileged,
  });

  const claimMutation = useMutation({
    mutationFn: (id: string) => shiftsApi.claim(id),
    onSuccess: () => {
      toast.success("Dienst angenommen!");
      qc.invalidateQueries({ queryKey: ["shifts"] });
      qc.invalidateQueries({ queryKey: ["shifts-open"] });
    },
    onError: () => toast.error("Fehler beim Annehmen"),
  });

  const { data: todayShifts } = useQuery({
    queryKey: ["shifts-today"],
    queryFn: () =>
      shiftsApi
        .list({ from_date: format(today, "yyyy-MM-dd"), to_date: format(today, "yyyy-MM-dd") })
        .then((r) => r.data),
  });

  const stats = [
    {
      label: "Aktive Mitarbeiter",
      value: employees?.length ?? "–",
      icon: Users,
      ctpVar: "blue",
    },
    {
      label: "Dienste heute",
      value: todayShifts?.length ?? "–",
      icon: Clock,
      ctpVar: "green",
    },
    {
      label: "Dienste diesen Monat",
      value: shifts?.length ?? "–",
      icon: CalendarCheck,
      ctpVar: "mauve",
    },
    {
      label: "Offene Dienste",
      value: shifts?.filter((s: { employee_id: string | null }) => !s.employee_id).length ?? "–",
      icon: AlertTriangle,
      ctpVar: "peach",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Übersicht</h1>
        <p className="text-muted-foreground">{formatDate(today, "EEEE, dd. MMMM yyyy")}</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(({ label, value, icon: Icon, ctpVar }) => (
          <div key={label} className="bg-card rounded-xl p-4 shadow-sm border border-border">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center mb-3"
              style={{
                color: `rgb(var(${STAT_COLORS[ctpVar]}))`,
                backgroundColor: `rgb(var(${STAT_COLORS[ctpVar]}) / 0.15)`,
              }}
            >
              <Icon size={20} />
            </div>
            <div className="text-2xl font-bold text-foreground">{value}</div>
            <div className="text-sm text-muted-foreground mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Today's Shifts */}
      <div className="bg-card rounded-xl shadow-sm border border-border p-4">
        <h2 className="font-semibold mb-3 text-foreground">Dienste heute</h2>
        {todayShifts?.length === 0 ? (
          <p className="text-muted-foreground text-sm">Keine Dienste heute</p>
        ) : (
          <div className="space-y-2">
            {todayShifts?.map((shift: {
              id: string;
              start_time: string;
              end_time: string;
              location: string | null;
              status: string;
              employee_id: string | null;
            }) => (
              <div key={shift.id} className="flex items-center justify-between p-3 bg-accent/50 rounded-lg">
                <div>
                  <div className="font-medium text-sm text-foreground">
                    {shift.start_time?.substring(0, 5)} – {shift.end_time?.substring(0, 5)}
                  </div>
                  <div className="text-xs text-muted-foreground">{shift.location || "Kein Ort"}</div>
                </div>
                <span className="text-xs px-2 py-1 rounded-full font-medium"
                  style={shift.employee_id
                    ? { color: "rgb(var(--ctp-green))", backgroundColor: "rgb(var(--ctp-green) / 0.15)" }
                    : { color: "rgb(var(--ctp-red))",   backgroundColor: "rgb(var(--ctp-red) / 0.15)" }}>
                  {shift.employee_id ? SHIFT_STATUS_LABELS[shift.status] : "Offen"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Open shifts – shown to non-privileged users only */}
      <ICalSection user={user} isPrivileged={isPrivileged} />

      {!isPrivileged && (openShifts as any[]).length > 0 && (
        <div className="bg-card rounded-xl shadow-sm border border-border p-4">
          <div className="flex items-center gap-2 mb-3">
            <HandshakeIcon size={18} style={{ color: "rgb(var(--ctp-peach))" }} />
            <h2 className="font-semibold text-foreground">Offene Dienste</h2>
            <span className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{ color: "rgb(var(--ctp-peach))", backgroundColor: "rgb(var(--ctp-peach) / 0.12)" }}>
              {(openShifts as any[]).length} verfügbar
            </span>
          </div>
          <p className="text-xs text-muted-foreground mb-3">
            Du kannst offene Dienste direkt annehmen. Der Dienst wird dir dann zugewiesen.
          </p>
          <div className="space-y-2">
            {(openShifts as any[]).slice(0, 5).map((shift: any) => (
              <div key={shift.id} className="flex items-center justify-between p-3 bg-accent/50 rounded-lg gap-3">
                <div className="min-w-0">
                  <div className="font-medium text-sm text-foreground">
                    {format(parseISO(shift.date), "EEE, d. MMM", { locale: de })}
                    {" · "}
                    {shift.start_time?.slice(0,5)} – {shift.end_time?.slice(0,5)} Uhr
                  </div>
                  {shift.location && (
                    <div className="text-xs text-muted-foreground truncate">{shift.location}</div>
                  )}
                </div>
                <button
                  onClick={() => claimMutation.mutate(shift.id)}
                  disabled={claimMutation.isPending}
                  className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                  style={{ backgroundColor: "rgb(var(--ctp-green))", color: "white" }}
                >
                  Annehmen
                </button>
              </div>
            ))}
            {(openShifts as any[]).length > 5 && (
              <p className="text-xs text-center text-muted-foreground pt-1">
                + {(openShifts as any[]).length - 5} weitere auf der Dienste-Seite
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
