"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { feedbackApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import {
  HelpCircle, MessageSquarePlus, Bug, Lightbulb, CircleHelp,
  ChevronDown, Loader2, Check,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { de } from "date-fns/locale";
import toast from "react-hot-toast";

interface HelpItem {
  question: string;
  why: string;
  how: string[];
}

interface FeedbackEntry {
  id: string;
  created_by_user_id: string;
  reporter_name: string;
  category: string;
  title: string;
  description: string;
  status: string;
  admin_note: string | null;
  created_at: string;
}

const EMPLOYEE_HELP: HelpItem[] = [
  {
    question: "Wie nehme ich einen offenen Dienst an?",
    why: "Offene Dienste sind unbesetzt – wer zuerst annimmt, bekommt den Dienst fest zugewiesen.",
    how: ["Gehe zu „Dienste“.", "Offene Dienste sind mit „Offen“ markiert.", "Klicke auf das Annehmen-Symbol (grünes Häkchen-Icon)."],
  },
  {
    question: "Wie quittiere ich einen zugewiesenen Dienst?",
    why: "Damit weiß der Admin, dass du den Dienst gesehen hast und kommst – wichtig für die Planungssicherheit.",
    how: ["Öffne „Dienste“.", "Bei deinen eigenen Diensten siehst du einen Daumen-hoch-Button.", "Ein Klick genügt – der Dienst zeigt danach „Quittiert“ an."],
  },
  {
    question: "Ich kann einen zugewiesenen Dienst nicht wahrnehmen – was jetzt?",
    why: "Statt den Admin einzeln anzuschreiben, kannst du den Dienst direkt zur Übernahme durch Kolleg:innen freigeben.",
    how: ["Klicke bei deinem Dienst auf das Tausch-Symbol (Pfeile).", "Optional eine kurze Notiz eintragen (z. B. „Zahnarzttermin“).", "Sobald jemand übernimmt, wirst du benachrichtigt. Ohne Übernahme läuft das Angebot automatisch ab und der Dienst bleibt bei dir."],
  },
  {
    question: "Wie beantrage ich Urlaub oder melde ich mich krank?",
    why: "Damit deine Abwesenheit im Dienstplan berücksichtigt wird und betroffene Dienste storniert werden.",
    how: ["Gehe zu „Abwesenheiten“.", "„Abwesenheit eintragen“ → Art, Zeitraum auswählen.", "Der Antrag geht an den Admin zur Genehmigung."],
  },
  {
    question: "Wo sehe ich meine Abrechnung?",
    why: "So kannst du deinen Lohn und deine Zuschläge nachvollziehen, sobald die Abrechnung erstellt ist.",
    how: ["Gehe zu „Abrechnung“.", "Dort siehst du Stunden, Zuschläge und (bei Minijob) deinen Grenzverbrauch.", "Sobald genehmigt, kannst du den Lohnzettel als PDF herunterladen."],
  },
  {
    question: "Wie bekomme ich Erinnerungen per Telegram?",
    why: "Damit du rechtzeitig vor Dienstbeginn erinnert wirst, auch ohne die App offen zu haben.",
    how: ["Schreibe in Telegram „/start“ an @userinfobot, um deine Chat-ID zu bekommen.", "Trage sie unter „Benachrichtigungen“ ein und aktiviere den Telegram-Kanal."],
  },
];

const ADMIN_HELP: HelpItem[] = [
  {
    question: "Wie plane ich neue Dienste?",
    why: "Grundlage für Dienstplan, Benachrichtigungen und später die Abrechnung.",
    how: ["Gehe zu „Dienste“ → „Neuer Dienst“.", "Für wiederkehrende Muster stattdessen „Regeltermine“ nutzen."],
  },
  {
    question: "Wie genehmige ich Abwesenheiten?",
    why: "Erst nach Genehmigung werden betroffene Dienste automatisch storniert.",
    how: ["Gehe zu „Abwesenheiten“.", "Offene Anträge zeigen einen Genehmigen/Ablehnen-Button."],
  },
  {
    question: "Wie gehe ich mit Tauschangeboten um, die meine Genehmigung brauchen?",
    why: "Bei bereits bestätigten Diensten entscheidest du, ob der Tausch übernommen wird – z. B. wegen Lohnzuschlägen.",
    how: ["In „Dienste“ → Abschnitt „Tauschbörse“ erscheinen wartende Fälle mit einem orangen Hinweis.", "Genehmigen oder mit Begründung ablehnen."],
  },
  {
    question: "Wie berechne und genehmige ich die Lohnabrechnung?",
    why: "Erst nach Genehmigung können Mitarbeiter ihren Lohnzettel herunterladen.",
    how: ["Gehe zu „Abrechnung“ → Monat wählen → „Alle berechnen“.", "Einzelne Einträge prüfen und auf „Genehmigt“ setzen."],
  },
  {
    question: "Wo sehe ich Compliance-Verstöße (Ruhezeit, Minijob-Grenze)?",
    why: "Damit Verstöße gegen ArbZG oder die Minijob-Grenze frühzeitig auffallen.",
    how: ["Gehe zu „Compliance“ für eine Übersicht aller aktiven Verstöße/Warnungen."],
  },
];

const CATEGORY_LABELS: Record<string, string> = { bug: "Fehler", wish: "Wunsch", question: "Frage" };
const CATEGORY_ICONS: Record<string, typeof Bug> = { bug: Bug, wish: Lightbulb, question: CircleHelp };
const STATUS_LABELS: Record<string, string> = {
  open: "Offen", in_progress: "In Bearbeitung", resolved: "Erledigt", declined: "Abgelehnt",
};
const STATUS_STYLE: Record<string, React.CSSProperties> = {
  open:         { color: "rgb(var(--ctp-blue))",  backgroundColor: "rgb(var(--ctp-blue) / 0.12)" },
  in_progress:  { color: "rgb(var(--ctp-peach))", backgroundColor: "rgb(var(--ctp-peach) / 0.12)" },
  resolved:     { color: "rgb(var(--ctp-green))", backgroundColor: "rgb(var(--ctp-green) / 0.12)" },
  declined:     { color: "rgb(var(--ctp-red))",   backgroundColor: "rgb(var(--ctp-red) / 0.12)" },
};

function HelpCard({ item }: { item: HelpItem }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-card rounded-xl border border-border overflow-hidden">
      <button onClick={() => setOpen((v) => !v)} className="w-full flex items-center justify-between p-4 text-left hover:bg-muted/40 transition-colors">
        <span className="font-medium text-foreground text-sm">{item.question}</span>
        <ChevronDown size={16} className={`text-muted-foreground shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 text-sm">
          <div className="flex items-start gap-2 rounded-lg p-3" style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.08)" }}>
            <span className="font-medium shrink-0" style={{ color: "rgb(var(--ctp-blue))" }}>Warum wichtig:</span>
            <span className="text-muted-foreground">{item.why}</span>
          </div>
          <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
            {item.how.map((step, i) => <li key={i}>{step}</li>)}
          </ol>
        </div>
      )}
    </div>
  );
}

function FeedbackTab({ isPrivileged }: { isPrivileged: boolean }) {
  const qc = useQueryClient();
  const [category, setCategory] = useState("bug");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [editing, setEditing] = useState<Record<string, { status: string; admin_note: string }>>({});

  const { data: entries = [], isLoading } = useQuery<FeedbackEntry[]>({
    queryKey: ["feedback"],
    queryFn: () => feedbackApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: () => feedbackApi.create({ category, title, description }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feedback"] });
      toast.success("Danke für deine Rückmeldung!");
      setTitle(""); setDescription("");
    },
    onError: () => toast.error("Konnte nicht gesendet werden"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { status?: string; admin_note?: string } }) =>
      feedbackApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["feedback"] }); toast.success("Aktualisiert"); },
    onError: () => toast.error("Aktualisierung fehlgeschlagen"),
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="bg-card rounded-xl border border-border p-5 space-y-3">
        <div className="flex items-center gap-2">
          <MessageSquarePlus size={18} style={{ color: "rgb(var(--ctp-mauve))" }} />
          <span className="font-semibold text-foreground">Neue Rückmeldung</span>
        </div>
        <div className="flex gap-2">
          {(["bug", "wish", "question"] as const).map((c) => {
            const Icon = CATEGORY_ICONS[c];
            return (
              <button key={c} onClick={() => setCategory(c)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                  category === c ? "border-transparent bg-primary text-primary-foreground" : "border-border text-muted-foreground hover:bg-muted"
                }`}>
                <Icon size={13} /> {CATEGORY_LABELS[c]}
              </button>
            );
          })}
        </div>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Kurzer Titel"
          className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm" />
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4}
          placeholder="Was ist passiert, oder was wünschst du dir?"
          className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-sm" />
        <button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending || !title.trim() || !description.trim()}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {createMutation.isPending && <Loader2 size={14} className="animate-spin" />}
          Absenden
        </button>
      </div>

      <div className="space-y-3">
        <h2 className="font-semibold text-foreground text-sm">
          {isPrivileged ? "Alle Rückmeldungen" : "Meine Rückmeldungen"}
        </h2>
        {isLoading ? (
          <div className="text-sm text-muted-foreground">Lade…</div>
        ) : entries.length === 0 ? (
          <div className="text-sm text-muted-foreground">Noch keine Rückmeldungen.</div>
        ) : (
          entries.map((fb) => {
            const Icon = CATEGORY_ICONS[fb.category] ?? CircleHelp;
            const edit = editing[fb.id];
            return (
              <div key={fb.id} className="bg-card rounded-xl border border-border p-4 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Icon size={14} className="text-muted-foreground shrink-0" />
                    <span className="font-medium text-foreground text-sm">{fb.title}</span>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium shrink-0" style={STATUS_STYLE[fb.status]}>
                    {STATUS_LABELS[fb.status] ?? fb.status}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">{fb.description}</p>
                <div className="text-xs text-muted-foreground">
                  {fb.reporter_name} · {format(parseISO(fb.created_at), "d.M.yyyy HH:mm", { locale: de })}
                </div>
                {fb.admin_note && !edit && (
                  <div className="text-xs text-muted-foreground bg-muted/40 rounded-lg p-2">
                    Antwort: {fb.admin_note}
                  </div>
                )}
                {isPrivileged && !edit && (
                  <button
                    onClick={() => setEditing((e) => ({ ...e, [fb.id]: { status: fb.status, admin_note: fb.admin_note ?? "" } }))}
                    className="text-xs font-medium hover:underline"
                    style={{ color: "rgb(var(--ctp-blue))" }}
                  >
                    Bearbeiten
                  </button>
                )}
                {isPrivileged && edit && (
                  <div className="space-y-2 pt-1">
                    <select value={edit.status} onChange={(e) => setEditing((s) => ({ ...s, [fb.id]: { ...edit, status: e.target.value } }))}
                      className="w-full px-2 py-1.5 rounded-lg border border-border bg-background text-foreground text-xs">
                      {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                    <textarea value={edit.admin_note} onChange={(e) => setEditing((s) => ({ ...s, [fb.id]: { ...edit, admin_note: e.target.value } }))}
                      rows={2} placeholder="Antwort/Notiz (optional)"
                      className="w-full px-2 py-1.5 rounded-lg border border-border bg-background text-foreground text-xs" />
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          updateMutation.mutate({ id: fb.id, data: { status: edit.status, admin_note: edit.admin_note || undefined } });
                          setEditing((e) => { const n = { ...e }; delete n[fb.id]; return n; });
                        }}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary text-primary-foreground"
                      >
                        <Check size={12} /> Speichern
                      </button>
                      <button
                        onClick={() => setEditing((e) => { const n = { ...e }; delete n[fb.id]; return n; })}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border text-muted-foreground hover:bg-muted"
                      >
                        Abbrechen
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default function HelpPage() {
  const { user } = useAuthStore();
  const [tab, setTab] = useState<"hilfe" | "feedback">("hilfe");
  const isPrivileged = user?.role === "admin" || user?.role === "manager";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <HelpCircle size={24} style={{ color: "rgb(var(--ctp-blue))" }} /> Hilfe
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">Anleitungen und ein Kanal für Rückmeldungen</p>
      </div>

      <div className="flex gap-1 border-b border-border">
        {(["hilfe", "feedback"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className="px-4 py-2 text-sm font-medium transition-colors"
            style={tab === t ? { color: "rgb(var(--ctp-blue))", borderBottom: "2px solid rgb(var(--ctp-blue))" } : { color: "rgb(var(--muted-foreground))" }}>
            {t === "hilfe" ? "Anleitungen" : "Rückmeldungen"}
          </button>
        ))}
      </div>

      {tab === "hilfe" && (
        <div className="space-y-6 max-w-2xl">
          <div className="space-y-3">
            <h2 className="font-semibold text-foreground text-sm">Für alle</h2>
            {EMPLOYEE_HELP.map((item) => <HelpCard key={item.question} item={item} />)}
          </div>
          {isPrivileged && (
            <div className="space-y-3">
              <h2 className="font-semibold text-foreground text-sm">Für Admin/Verwalter</h2>
              {ADMIN_HELP.map((item) => <HelpCard key={item.question} item={item} />)}
            </div>
          )}
        </div>
      )}

      {tab === "feedback" && <FeedbackTab isPrivileged={isPrivileged} />}
    </div>
  );
}
