"use client";

import { useState, useCallback, useMemo } from "react";
import { useSwipe } from "@/hooks/useSwipe";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar, dateFnsLocalizer, View } from "react-big-calendar";
import withDragAndDrop from "react-big-calendar/lib/addons/dragAndDrop";
import { format, parse, startOfWeek, endOfWeek, getDay, startOfMonth, endOfMonth, addMonths, subMonths, parseISO } from "date-fns";
import { de } from "date-fns/locale";
import { shiftsApi, templatesApi, employeesApi, calendarDataApi, recurringShiftsApi, shiftTypesApi } from "@/lib/api";
import { buildAllRecurringEvents } from "@/lib/recurringEventUtils";
import { ChevronLeft, ChevronRight, AlertCircle, Plus, Check, Trash2 } from "lucide-react";
import { useAuthStore } from "@/store/auth";
import { CreateShiftModal } from "@/components/shared/CreateShiftModal";
import toast from "react-hot-toast";
import "react-big-calendar/lib/css/react-big-calendar.css";
import "react-big-calendar/lib/addons/dragAndDrop/styles.css";

const DnDCalendar = withDragAndDrop(Calendar as any);

// Farbpalette für MA ohne Template/ShiftType (Catppuccin-Farben)
const EMPLOYEE_COLORS = [
  "#89b4fa", // blue
  "#a6e3a1", // green
  "#fab387", // peach
  "#cba6f7", // mauve
  "#94e2d5", // teal
  "#f9e2af", // yellow
  "#89dceb", // sky
  "#f38ba8", // red
  "#b4befe", // lavender
  "#a6adc8", // subtext1
];

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 1 }),
  getDay,
  locales: { de },
});

const VIEWS: { key: View; label: string }[] = [
  { key: "month", label: "Monat" },
  { key: "week",  label: "Woche" },
  { key: "day",   label: "Tag" },
];

export default function CalendarPage() {
  const { user } = useAuthStore();
  const isPrivileged = user?.role === "admin" || user?.role === "manager";
  const qc = useQueryClient();

  const [view, setView] = useState<View>("week");
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedShift, setSelectedShift] = useState<any>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createDate, setCreateDate] = useState("");
  const [dragging, setDragging] = useState(false);
  const [selectedRecurring, setSelectedRecurring] = useState<any>(null);

  const rangeStart = format(
    view === "month" ? startOfWeek(startOfMonth(currentDate), { weekStartsOn: 1 })
    : view === "week"  ? startOfWeek(currentDate, { weekStartsOn: 1 })
    : currentDate,
    "yyyy-MM-dd"
  );
  const rangeEnd = format(
    view === "month" ? endOfWeek(endOfMonth(currentDate), { weekStartsOn: 1 })
    : view === "week"  ? endOfWeek(currentDate, { weekStartsOn: 1 })
    : currentDate,
    "yyyy-MM-dd"
  );

  const { data: shifts = [] } = useQuery({
    queryKey: ["shifts", rangeStart, rangeEnd],
    queryFn: () => shiftsApi.list({ from_date: rangeStart, to_date: rangeEnd }).then(r => r.data),
  });

  const { data: templates = [] } = useQuery({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then(r => r.data),
  });

  const { data: employees = [] } = useQuery({
    queryKey: ["employees"],
    queryFn: () => employeesApi.list().then(r => r.data),
  });

  const { data: vacationData } = useQuery({
    queryKey: ["vacation-data", rangeStart, rangeEnd],
    queryFn: () => calendarDataApi.vacationData(rangeStart, rangeEnd).then(r => r.data),
    staleTime: 5 * 60 * 1000,
  });

  const { data: recurringShifts = [] } = useQuery({
    queryKey: ["recurring-shifts"],
    queryFn: () => recurringShiftsApi.list().then(r => r.data),
    enabled: isPrivileged,
  });

  const { data: shiftTypes = [] } = useQuery({
    queryKey: ["shift-types"],
    queryFn: () => shiftTypesApi.list().then(r => r.data),
  });

  // Lookup-Maps
  const templateMap  = useMemo(() =>
    Object.fromEntries(templates.map((t: any) => [t.id, t])), [templates]);
  const employeeMap  = useMemo(() =>
    Object.fromEntries(employees.map((e: any) => [e.id, e])), [employees]);
  const shiftTypeMap = useMemo(() =>
    Object.fromEntries((shiftTypes as any[]).map((st: any) => [st.id, st])), [shiftTypes]);

  // Mitarbeiterspezifische Farben als Fallback wenn kein Template/ShiftType
  const employeeColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    (employees as any[]).forEach((e: any, i: number) => {
      map[e.id] = EMPLOYEE_COLORS[i % EMPLOYEE_COLORS.length];
    });
    return map;
  }, [employees]);

  // ── Confirm / Delete mutations ────────────────────────────────────────────────
  const confirmMutation = useMutation({
    mutationFn: (id: string) => shiftsApi.confirm(id, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shifts"] });
      setSelectedShift(null);
      toast.success("Dienst bestätigt");
    },
    onError: () => toast.error("Fehler beim Bestätigen"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => shiftsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shifts"] });
      setSelectedShift(null);
      toast.success("Dienst gelöscht");
    },
    onError: () => toast.error("Fehler beim Löschen"),
  });

  // ── Drag & Drop mutation ─────────────────────────────────────────────────────
  const moveMutation = useMutation({
    mutationFn: ({ id, date, start_time, end_time }: {
      id: string; date: string; start_time: string; end_time: string;
    }) => shiftsApi.update(id, { date, start_time, end_time }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shifts"] });
      toast.success("Dienst verschoben");
    },
    onError: () => {
      qc.invalidateQueries({ queryKey: ["shifts"] });
      toast.error("Verschieben fehlgeschlagen – Compliance-Prüfung?");
    },
  });

  const handleEventDrop = useCallback(({ event, start, end }: any) => {
    const shift = event.resource?.shift;
    if (!shift || !isPrivileged) return;

    // Don't move holiday/vacation labels
    const t = event.resource?.type;
    if (t === "vacation_label" || t === "holiday_label") return;

    const newDate   = format(start, "yyyy-MM-dd");
    const newStart  = format(start, "HH:mm:ss");
    const newEnd    = format(end,   "HH:mm:ss");

    // No change?
    if (newDate === shift.date && newStart === shift.start_time.slice(0, 8)) return;

    moveMutation.mutate({ id: shift.id, date: newDate, start_time: newStart, end_time: newEnd });
  }, [isPrivileged, moveMutation]);

  const handleEventResize = useCallback(({ event, start, end }: any) => {
    const shift = event.resource?.shift;
    if (!shift || !isPrivileged) return;

    const newDate  = format(start, "yyyy-MM-dd");
    const newStart = format(start, "HH:mm:ss");
    const newEnd   = format(end,   "HH:mm:ss");

    moveMutation.mutate({ id: shift.id, date: newDate, start_time: newStart, end_time: newEnd });
  }, [isPrivileged, moveMutation]);

  // Shifts → Calendar Events
  // Overnight-Dienste (z.B. 21:30–06:00) werden in zwei Events gesplittet:
  // Teil 1: Start → Mitternacht, Teil 2: Mitternacht → Ende (nächster Tag)
  const events = useMemo(() => (shifts as any[]).flatMap((s: any) => {
    const tpl       = templateMap[s.template_id];
    const emp       = employeeMap[s.employee_id];
    const shiftType = shiftTypeMap[s.shift_type_id];
    const empName   = emp ? `${emp.first_name} ${emp.last_name[0]}.` : "Offen";
    const typeLabel = shiftType ? ` [${shiftType.name}]` : "";
    const baseTitle = tpl
      ? `${tpl.name}${typeLabel} – ${empName}`
      : s.notes
      ? `${s.notes} – ${empName}`
      : empName;
    const prefix = s.status === "completed" ? "✓ " : s.status === "confirmed" ? "• " : "";
    const resource = { shift: s, template: tpl, employee: emp, shiftType };

    const startDt = new Date(`${s.date}T${s.start_time}`);
    const rawEnd  = new Date(`${s.date}T${s.end_time}`);

    if (rawEnd <= startDt) {
      // Overnight: an Mitternacht splitten
      const midnight = new Date(startDt);
      midnight.setDate(midnight.getDate() + 1);
      midnight.setHours(0, 0, 0, 0);
      const nextDayEnd = new Date(rawEnd.getTime() + 86400000);
      return [
        { id: `${s.id}-p1`, title: prefix + baseTitle,   start: startDt,  end: midnight,    resource },
        { id: `${s.id}-p2`, title: `↳ ${baseTitle}`,     start: midnight,  end: nextDayEnd,  resource },
      ];
    }

    return [{ id: s.id, title: prefix + baseTitle, start: startDt, end: rawEnd, resource }];
  }), [shifts, templateMap, employeeMap, shiftTypeMap]);

  // Holiday display events
  const holidayEvents = useMemo(() => {
    const hevents: any[] = [];
    if (vacationData) {
      for (const vp of vacationData.vacation_periods ?? []) {
        hevents.push({
          id: `vp-${vp.id}`,
          title: vp.name,
          start: parseISO(vp.start_date),
          end: new Date(parseISO(vp.end_date).getTime() + 86400000),
          allDay: true,
          resource: { type: "vacation_label", color: vp.color },
        });
      }
      for (const ph of vacationData.public_holidays ?? []) {
        hevents.push({
          id: `ph-${ph.date}`,
          title: ph.name,
          start: parseISO(ph.date),
          end: new Date(parseISO(ph.date).getTime() + 86400000),
          allDay: true,
          resource: { type: "holiday_label", color: "#f38ba8" },
        });
      }
      for (const ch of vacationData.custom_holidays ?? []) {
        hevents.push({
          id: `ch-${ch.id}`,
          title: ch.name,
          start: parseISO(ch.date),
          end: new Date(parseISO(ch.date).getTime() + 86400000),
          allDay: true,
          resource: { type: "holiday_label", color: ch.color },
        });
      }
      for (const ca of vacationData.care_absences ?? []) {
        hevents.push({
          id: `ca-${ca.id}`,
          title: `🏠 ${ca.label}`,
          start: parseISO(ca.start_date),
          end: new Date(parseISO(ca.end_date).getTime() + 86400000),
          allDay: true,
          resource: { type: "care_absence", color: "#cba6f7", careAbsence: ca },
        });
      }
      const absenceEmoji: Record<string, string> = {
        vacation: "🏖️",
        sick: "🤒",
        school_holiday: "📚",
        other: "📅",
      };
      const absenceColor: Record<string, string> = {
        vacation: "rgb(var(--ctp-blue) / 0.25)",
        sick: "rgb(var(--ctp-red) / 0.25)",
        school_holiday: "rgb(var(--ctp-yellow) / 0.25)",
        other: "rgb(var(--ctp-overlay1) / 0.25)",
      };
      for (const ea of vacationData.employee_absences ?? []) {
        const emoji = absenceEmoji[ea.type] ?? "📅";
        const color = absenceColor[ea.type] ?? absenceColor.other;
        hevents.push({
          id: `ea-${ea.id}`,
          title: `${emoji} ${ea.employee_name}`,
          start: parseISO(ea.start_date),
          end: new Date(parseISO(ea.end_date).getTime() + 86400000),
          allDay: true,
          resource: { type: "employee_absence", color, employeeAbsence: ea },
        });
      }
    }
    return hevents;
  }, [vacationData]);

  // Recurring shift events – gefiltert nach Ferien, Feiertagen, valid_from/until, echten Diensten
  const recurringEvents = useMemo(() => {
    if (view === "month") return [];
    const shiftDates = new Set((shifts as any[]).map((s: any) => s.date));
    return buildAllRecurringEvents(
      recurringShifts as any[],
      templateMap,
      parseISO(rangeStart),
      parseISO(rangeEnd),
      shiftDates,
      vacationData,
    );
  }, [recurringShifts, templateMap, rangeStart, rangeEnd, view, shifts, vacationData]);

  const allEvents = useMemo(() => [...events, ...holidayEvents, ...recurringEvents], [events, holidayEvents, recurringEvents]);

  // Event color / style
  const eventPropGetter = useCallback((event: any) => {
    const { shift, template, shiftType, type, color: labelColor } = event.resource ?? {};

    if (type === "vacation_label" || type === "holiday_label") {
      return {
        style: {
          backgroundColor: labelColor,
          borderColor: "transparent",
          color: "rgba(0,0,0,0.75)",
          fontSize: "0.65rem",
          fontWeight: "600",
          opacity: 0.88,
          borderRadius: "3px",
          pointerEvents: "none" as const,
          cursor: "default",
        },
      };
    }

    if (type === "care_absence") {
      return {
        style: {
          backgroundColor: "#cba6f7",
          borderColor: "#cba6f7",
          color: "rgba(0,0,0,0.80)",
          fontSize: "0.65rem",
          fontWeight: "600",
          opacity: 0.85,
          borderRadius: "3px",
          pointerEvents: "none" as const,
          cursor: "default",
        },
      };
    }

    if (type === "employee_absence") {
      return {
        style: {
          backgroundColor: labelColor ?? "rgba(137,180,250,0.4)",
          borderColor: "transparent",
          color: "rgba(0,0,0,0.75)",
          fontSize: "0.65rem",
          fontWeight: "600",
          opacity: 0.9,
          borderRadius: "3px",
          pointerEvents: "none" as const,
          cursor: "default",
        },
      };
    }

    if (type === "recurring_shift") {
      const c = labelColor ?? "#1E3A5F";
      return {
        style: {
          backgroundColor: c,
          borderColor: c,
          opacity: 0.25,
          fontSize: "0.7rem",
          cursor: "pointer",
          borderRadius: "3px",
        },
      };
    }

    if (!shift) return {};
    const isOpen = !shift.employee_id;
    const empColor = shift.employee_id ? (employeeColorMap[shift.employee_id] ?? "#89b4fa") : "#ef4444";
    const c = isOpen ? "#ef4444" : (shiftType?.color ?? template?.color ?? empColor);
    const isCancelled = shift.status.startsWith("cancelled");
    const isCompleted = shift.status === "completed";
    const isConfirmed = shift.status === "confirmed";
    return {
      style: {
        backgroundColor: isCompleted ? "transparent" : c,
        opacity: isCancelled ? 0.35 : 1,
        textDecoration: isCancelled ? "line-through" : "none",
        fontSize: "0.75rem",
        // Dünner Rahmen für alle; links etwas dicker je nach Status
        border: `1px solid ${c}`,
        borderLeft: isCancelled ? `1px dashed ${c}` : isConfirmed ? `4px solid ${c}` : isCompleted ? `4px solid ${c}` : `1px solid ${c}`,
        color: isCompleted ? c : "#1e1e2e",
        cursor: isPrivileged ? (dragging ? "grabbing" : "grab") : "pointer",
      },
    };
  }, [isPrivileged, dragging, employeeColorMap]);

  // Ungerade Stunden leicht heller für bessere optische Trennung
  const slotPropGetter = useCallback((date: Date) => {
    if (date.getHours() % 2 === 1) {
      return { style: { backgroundColor: "rgba(127,127,127,0.045)" } };
    }
    return {};
  }, []);

  const dayPropGetter = useCallback((date: Date) => {
    const ds = format(date, "yyyy-MM-dd");
    const isPublicHoliday = (vacationData?.public_holidays ?? []).some((ph: any) => ph.date === ds);
    const isVacation = (vacationData?.vacation_periods ?? []).some((vp: any) => ds >= vp.start_date && ds <= vp.end_date);
    const isCustom = (vacationData?.custom_holidays ?? []).some((ch: any) => ch.date === ds);
    const isCareAbsence = (vacationData?.care_absences ?? []).some(
      (ca: any) => ds >= ca.start_date && ds <= ca.end_date
    );
    if (isPublicHoliday) return { style: { backgroundColor: "rgba(243, 139, 168, 0.18)" } };
    if (isVacation)      return { style: { backgroundColor: "rgba(166, 227, 161, 0.15)" } };
    if (isCustom)        return { style: { backgroundColor: "rgba(250, 179, 135, 0.16)" } };
    if (isCareAbsence)   return { style: { backgroundColor: "rgba(203, 166, 247, 0.18)" } };
    return {};
  }, [vacationData]);

  const handleNavigate = (dir: "prev" | "next" | "today") => {
    if (dir === "today") { setCurrentDate(new Date()); return; }
    setCurrentDate(prev => {
      const d = new Date(prev);
      if (view === "month") return dir === "next" ? addMonths(d, 1) : subMonths(d, 1);
      const delta = view === "week" ? 7 : 1;
      d.setDate(d.getDate() + (dir === "next" ? delta : -delta));
      return d;
    });
  };

  const legend = templates.map((t: any) => ({ name: t.name, color: t.color }));

  const swipeHandlers = useSwipe({
    onSwipeLeft:  () => handleNavigate("next"),
    onSwipeRight: () => handleNavigate("prev"),
  });

  return (
    <div className="space-y-4 h-full" {...swipeHandlers}>
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold flex-1">Kalender</h1>
        {isPrivileged && (
          <button onClick={() => { setCreateDate(format(currentDate, "yyyy-MM-dd")); setShowCreate(true); }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 transition-opacity">
            <Plus size={16} />
            <span className="hidden sm:inline">Neuer Dienst</span>
          </button>
        )}

        <div className="flex items-center gap-1 bg-card rounded-lg border border-border p-1">
          <button onClick={() => handleNavigate("prev")} className="p-2.5 hover:bg-accent rounded"><ChevronLeft size={16} /></button>
          <button onClick={() => handleNavigate("today")} className="px-3 py-2 text-sm hover:bg-accent rounded font-medium">Heute</button>
          <button onClick={() => handleNavigate("next")} className="p-2.5 hover:bg-accent rounded"><ChevronRight size={16} /></button>
        </div>

        <div className="flex gap-1 bg-card rounded-lg border border-border p-1">
          {VIEWS.map(v => (
            <button key={v.key} onClick={() => setView(v.key)}
              className={`px-3 py-2 text-sm rounded font-medium transition-colors ${
                view === v.key ? "bg-primary text-primary-foreground" : "hover:bg-accent"
              }`}>
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {/* Legende */}
      <div className="flex flex-wrap gap-2 text-xs">
        {legend.map((l: any) => (
          <span key={l.name} className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: l.color }} />
            {l.name}
          </span>
        ))}
        <span className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: "rgb(var(--ctp-red))" }} />
          Offener Dienst
        </span>
        <span className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
          <span className="text-ctp-blue font-bold text-[10px]">•</span>
          Bestätigt
        </span>
        <span className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
          <span className="text-ctp-green font-bold text-[10px]">✓</span>
          Abgeschlossen
        </span>
        {(vacationData?.vacation_periods ?? []).length > 0 && (
          <span className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: "#a6e3a1" }} />
            Schulferien
          </span>
        )}
        {(vacationData?.public_holidays ?? []).length > 0 && (
          <span className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: "#f38ba8" }} />
            Feiertag
          </span>
        )}
        {(vacationData?.custom_holidays ?? []).length > 0 && (
          <span className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: "#fab387" }} />
            Beweglicher Tag
          </span>
        )}
        {(vacationData?.care_absences ?? []).length > 0 && (
          <span className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: "#cba6f7" }} />
            Abwesenheit betreute Person
          </span>
        )}
        {(vacationData?.employee_absences ?? []).length > 0 && (
          <span className="flex items-center gap-1.5 bg-card rounded-full px-2.5 py-1 border border-border text-foreground">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.6)" }} />
            MA-Abwesenheit
          </span>
        )}
        {isPrivileged && (
          <span className="ml-auto text-muted-foreground italic">
            Dienste verschieben per Drag &amp; Drop
          </span>
        )}
      </div>

      {/* Kalender */}
      <div className="bg-card rounded-xl border border-border overflow-hidden" style={{ height: "calc(100svh - 220px)", minHeight: 380 }}>
        <DnDCalendar
          localizer={localizer}
          events={allEvents}
          view={view}
          date={currentDate}
          onNavigate={setCurrentDate}
          onView={setView}
          eventPropGetter={eventPropGetter}
          dayPropGetter={dayPropGetter}
          slotPropGetter={slotPropGetter}
          scrollToTime={new Date(1970, 1, 1, 6, 0)}
          // Drag & Drop – nur für Admins/Manager
          draggableAccessor={(event: any) => {
            if (!isPrivileged) return false;
            const t = event.resource?.type;
            if (t === "vacation_label" || t === "holiday_label" || t === "recurring_shift") return false;
            const status = event.resource?.shift?.status ?? "";
            return !status.startsWith("cancelled") && status !== "completed";
          }}
          resizable={isPrivileged}
          resizableAccessor={(event: any) => {
            if (!isPrivileged) return false;
            const t = event.resource?.type;
            if (t === "vacation_label" || t === "holiday_label" || t === "recurring_shift") return false;
            const status = event.resource?.shift?.status ?? "";
            return !status.startsWith("cancelled") && status !== "completed";
          }}
          onEventDrop={handleEventDrop}
          onEventResize={handleEventResize}
          onDragStart={() => setDragging(true)}
          onDropFromOutside={() => setDragging(false)}
          onSelectEvent={(e: any) => {
            if (dragging) return;
            const t = e.resource?.type;
            if (t === "vacation_label" || t === "holiday_label" || t === "care_absence") return;
            if (t === "recurring_shift") { setSelectedRecurring(e.resource); return; }
            setSelectedShift(e.resource);
          }}
          onSelectSlot={isPrivileged ? (slot: any) => {
            setCreateDate(format(slot.start, "yyyy-MM-dd"));
            setShowCreate(true);
          } : undefined}
          selectable={isPrivileged}
          culture="de"
          toolbar={false}
          messages={{
            noEventsInRange: "Keine Dienste in diesem Zeitraum",
            showMore: (n: number) => `+${n} weitere`,
          }}
          step={30}
          timeslots={2}
        />
      </div>

      {/* Modals */}
      {showCreate && (
        <CreateShiftModal
          templates={templates as any[]}
          employees={employees as any[]}
          defaultDate={createDate}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); qc.invalidateQueries({ queryKey: ["shifts"] }); }}
        />
      )}

      {selectedRecurring && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setSelectedRecurring(null)}>
          <div className="bg-card rounded-xl shadow-xl p-5 max-w-sm w-full border border-border"
            onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="font-semibold text-lg text-foreground">
                  ↻ Regeltermin
                </div>
                <div className="text-sm text-muted-foreground">
                  {selectedRecurring.recurringShift?.label ?? selectedRecurring.template?.name ?? "–"}
                </div>
              </div>
              <span className="w-3 h-3 rounded-full mt-1.5 shrink-0"
                style={{ backgroundColor: selectedRecurring.color ?? "rgb(var(--ctp-overlay1))" }} />
            </div>
            <div className="space-y-1.5 text-sm">
              <Row label="Vorlage" value={selectedRecurring.template?.name ?? "–"} />
              <Row label="Uhrzeit" value={`${selectedRecurring.recurringShift?.start_time?.slice(0,5)} – ${selectedRecurring.recurringShift?.end_time?.slice(0,5)} Uhr`} />
              <Row label="Pause" value={selectedRecurring.recurringShift?.break_minutes ? `${selectedRecurring.recurringShift.break_minutes} Min` : "keine"} />
              {selectedRecurring.recurringShift?.notes && (
                <Row label="Notiz" value={selectedRecurring.recurringShift.notes} />
              )}
            </div>
            <button onClick={() => setSelectedRecurring(null)}
              className="mt-4 w-full text-sm text-center py-2 rounded-lg bg-accent hover:bg-accent/80 text-foreground transition-colors">
              Schließen
            </button>
          </div>
        </div>
      )}

      {selectedShift && (() => {
        const shift = selectedShift.shift;
        const statusStyles: Record<string, string> = {
          planned:           "bg-ctp-yellow/20 text-ctp-yellow",
          confirmed:         "bg-ctp-blue/20 text-ctp-blue",
          completed:         "bg-ctp-green/20 text-ctp-green",
          cancelled:         "bg-ctp-red/20 text-ctp-red",
          cancelled_unpaid:  "bg-ctp-red/20 text-ctp-red",
        };
        const statusLabels: Record<string, string> = {
          planned:          "Geplant",
          confirmed:        "Bestätigt",
          completed:        "Abgeschlossen",
          cancelled:        "Storniert",
          cancelled_unpaid: "Storniert (unbezahlt)",
        };
        const canConfirm = isPrivileged && shift.status === "planned";
        const canDelete  = isPrivileged && shift.status !== "completed";
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
            onClick={() => setSelectedShift(null)}>
            <div className="bg-card rounded-xl shadow-xl p-5 max-w-sm w-full border border-border"
              onClick={e => e.stopPropagation()}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="font-semibold text-lg text-foreground">
                    {selectedShift.template?.name ?? "Dienst"}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {shift.date} · {shift.start_time?.slice(0,5)} – {shift.end_time?.slice(0,5)} Uhr
                  </div>
                </div>
                <span className="w-3 h-3 rounded-full mt-1.5 shrink-0"
                  style={{ backgroundColor: selectedShift.template?.color ?? "rgb(var(--ctp-overlay1))" }} />
              </div>

              <div className="space-y-1.5 text-sm">
                <Row label="Mitarbeiter"
                  value={selectedShift.employee
                    ? `${selectedShift.employee.first_name} ${selectedShift.employee.last_name}`
                    : <span className="text-ctp-red font-medium flex items-center gap-1"><AlertCircle size={13}/>Offen</span>} />
                <Row label="Ort" value={shift.location ?? "–"} />
                <Row label="Pause" value={shift.break_minutes ? `${shift.break_minutes} Min` : "keine"} />
                <Row label="Status" value={
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusStyles[shift.status] ?? "bg-muted text-muted-foreground"}`}>
                    {statusLabels[shift.status] ?? shift.status}
                  </span>
                } />
                {shift.notes && (
                  <Row label="Notiz" value={<span className="text-ctp-yellow">{shift.notes}</span>} />
                )}
              </div>

              <div className="mt-4 flex gap-2">
                {canConfirm && (
                  <button
                    onClick={() => confirmMutation.mutate(shift.id)}
                    disabled={confirmMutation.isPending}
                    className="flex-1 flex items-center justify-center gap-1.5 text-sm py-2 rounded-lg bg-ctp-green/20 hover:bg-ctp-green/30 text-ctp-green font-medium transition-colors disabled:opacity-50">
                    <Check size={14} />
                    Bestätigen
                  </button>
                )}
                {canDelete && (
                  <button
                    onClick={() => {
                      if (confirm(`Dienst am ${shift.date} wirklich löschen?`)) {
                        deleteMutation.mutate(shift.id);
                      }
                    }}
                    disabled={deleteMutation.isPending}
                    className="flex-1 flex items-center justify-center gap-1.5 text-sm py-2 rounded-lg bg-ctp-red/20 hover:bg-ctp-red/30 text-ctp-red font-medium transition-colors disabled:opacity-50">
                    <Trash2 size={14} />
                    Löschen
                  </button>
                )}
                <button onClick={() => setSelectedShift(null)}
                  className={`text-sm text-center py-2 px-3 rounded-lg bg-accent hover:bg-accent/80 text-foreground transition-colors ${canConfirm || canDelete ? "" : "flex-1"}`}>
                  Schließen
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      {label && <span className="text-muted-foreground w-24 shrink-0">{label}</span>}
      <span className="text-foreground">{value}</span>
    </div>
  );
}
