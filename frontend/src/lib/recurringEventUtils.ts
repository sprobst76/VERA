/**
 * Hilfsfunktionen für die Berechnung anzeigbarer Regeltermin-Events im Kalender.
 * Regeltermine werden NICHT angezeigt wenn:
 *   - der Tag außerhalb des valid_from/valid_until-Bereichs liegt
 *   - der Tag in einer Ferienperiode liegt
 *   - der Tag ein Feiertag ist (wenn skip_public_holidays)
 *   - an dem Tag bereits ein echter Dienst existiert
 */

import { getDay, eachDayOfInterval, parseISO, format } from "date-fns";

export interface VacationPeriod {
  start_date: string;
  end_date: string;
}

export interface PublicHoliday {
  date: string;
}

export interface VacationData {
  vacation_periods?: VacationPeriod[];
  public_holidays?: PublicHoliday[];
}

export interface RecurringShift {
  id: string;
  weekday: number;       // 0=Mo … 6=So
  start_time: string;    // "HH:MM:SS"
  end_time: string;
  label?: string;
  valid_from: string;    // "YYYY-MM-DD"
  valid_until: string;   // "YYYY-MM-DD"
  skip_public_holidays?: boolean;
  template_id?: string;
}

export interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  allDay: boolean;
  resource: {
    type: "recurring_shift";
    color: string;
    recurringShift: RecurringShift;
    template?: { name?: string; color?: string } | null;
  };
}

/**
 * Baut ein Set aus Datumsstrings (YYYY-MM-DD) aller Ferientage + optionaler Feiertage.
 */
export function buildSkipSet(
  vacationData: VacationData | undefined,
  skipHolidays: boolean,
): Set<string> {
  const skip = new Set<string>();
  if (!vacationData) return skip;

  for (const vp of vacationData.vacation_periods ?? []) {
    const days = eachDayOfInterval({
      start: parseISO(vp.start_date),
      end: parseISO(vp.end_date),
    });
    for (const d of days) skip.add(format(d, "yyyy-MM-dd"));
  }

  if (skipHolidays) {
    for (const ph of vacationData.public_holidays ?? []) {
      skip.add(ph.date);
    }
  }

  return skip;
}

/**
 * Gibt für einen Regeltermin und einen Datumsbereich alle Calendar-Events zurück,
 * gefiltert nach Ferien, Feiertagen, valid_from/valid_until und shiftDates.
 */
export function buildRecurringEventsForShift(
  rs: RecurringShift,
  rangeStart: Date,
  rangeEnd: Date,
  shiftDates: Set<string>,
  vacationData: VacationData | undefined,
  templateColor: string,
  templateName: string | undefined,
  template: { name?: string; color?: string } | null | undefined,
): CalendarEvent[] {
  const skipSet = buildSkipSet(vacationData, rs.skip_public_holidays ?? true);
  const validFrom = parseISO(rs.valid_from);
  const validUntil = parseISO(rs.valid_until);

  // Effektiver Datumsbereich = Schnittmenge aus Kalender-Range und valid_from/valid_until
  const effectiveStart = rangeStart < validFrom ? validFrom : rangeStart;
  const effectiveEnd = rangeEnd > validUntil ? validUntil : rangeEnd;

  if (effectiveStart > effectiveEnd) return [];

  const allDays = eachDayOfInterval({ start: effectiveStart, end: effectiveEnd });
  const events: CalendarEvent[] = [];

  // react-big-calendar: weekday 0=So,1=Mo,…,6=Sa → (rs.weekday+1)%7
  const rbcWeekday = (rs.weekday + 1) % 7;

  for (const d of allDays) {
    if (getDay(d) !== rbcWeekday) continue;

    const dateStr = format(d, "yyyy-MM-dd");

    // Nicht anzeigen wenn Ferien/Feiertag
    if (skipSet.has(dateStr)) continue;

    // Nicht anzeigen wenn an diesem Tag bereits ein echter Dienst existiert
    if (shiftDates.has(dateStr)) continue;

    const [sh, sm] = rs.start_time.slice(0, 5).split(":").map(Number);
    const [eh, em] = rs.end_time.slice(0, 5).split(":").map(Number);
    const startDt = new Date(d);
    startDt.setHours(sh, sm, 0, 0);
    const endDt = new Date(d);
    endDt.setHours(eh, em, 0, 0);

    events.push({
      id: `rs-${rs.id}-${dateStr}`,
      title: `↻ ${rs.label || templateName || "Regeltermin"}`,
      start: startDt,
      end: endDt,
      allDay: false,
      resource: {
        type: "recurring_shift",
        color: templateColor,
        recurringShift: rs,
        template: template ?? null,
      },
    });
  }

  return events;
}

/**
 * Berechnet alle sichtbaren Regeltermin-Events für den aktuellen Kalenderbereich.
 */
export function buildAllRecurringEvents(
  recurringShifts: RecurringShift[],
  templateMap: Record<string, { name?: string; color?: string }>,
  rangeStart: Date,
  rangeEnd: Date,
  shiftDates: Set<string>,
  vacationData: VacationData | undefined,
): CalendarEvent[] {
  const events: CalendarEvent[] = [];
  for (const rs of recurringShifts) {
    const tpl = rs.template_id ? templateMap[rs.template_id] : undefined;
    const color = tpl?.color ?? "rgb(var(--ctp-blue))";
    events.push(
      ...buildRecurringEventsForShift(
        rs,
        rangeStart,
        rangeEnd,
        shiftDates,
        vacationData,
        color,
        tpl?.name,
        tpl,
      ),
    );
  }
  return events;
}
