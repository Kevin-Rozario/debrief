const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;

export interface ConsultationTime {
  listDate: string;
  localRange: string;
  detailWhen: string;
  utcRange: string;
}

/** List date, local range, detail line, and the UTC range beneath it. */
export function formatConsultationTime(startsAt: string, endsAt: string): ConsultationTime {
  const start = parseUtc(startsAt);
  const end = parseUtc(endsAt);
  const range = formatLocalRange(start, end);
  return {
    listDate: formatDate(start, false),
    localRange: range,
    detailWhen: `${formatDate(start, true)}, ${range}`,
    utcRange: formatUtcRange(start, end),
  };
}

/** "22 Sep 2026, 4:30 pm" in the viewer's zone. */
export function formatSharedAt(iso: string): string {
  return formatLocalInstant(parseUtc(iso));
}

/** "9 Oct 2026, 2:30 pm" in the viewer's zone. */
export function formatLocalInstant(instant: Date): string {
  const clock = formatLocalClock(instant);
  return `${formatDate(instant, true)}, ${clock.time} ${clock.meridiem}`;
}

/** "23 Sep 2026" in the viewer's zone. */
export function formatDay(iso: string): string {
  return formatDate(parseUtc(iso), true);
}

function parseUtc(iso: string): Date {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) {
    throw new TypeError("Invalid datetime.");
  }
  return instant;
}

function formatDate(instant: Date, withYear: boolean): string {
  const day = `${instant.getDate()} ${MONTHS[instant.getMonth()]}`;
  if (!withYear) {
    return day;
  }
  return `${day} ${instant.getFullYear()}`;
}

function formatLocalRange(start: Date, end: Date): string {
  const from = formatLocalClock(start);
  const to = formatLocalClock(end);
  if (from.meridiem === to.meridiem) {
    return `${from.time}–${to.time} ${to.meridiem}`;
  }
  return `${from.time} ${from.meridiem}–${to.time} ${to.meridiem}`;
}

function formatLocalClock(instant: Date): { time: string; meridiem: "am" | "pm" } {
  const hours = instant.getHours();
  const meridiem = hours < 12 ? "am" : "pm";
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  const minutes = String(instant.getMinutes()).padStart(2, "0");
  return { time: `${hour12}:${minutes}`, meridiem };
}

function formatUtcRange(start: Date, end: Date): string {
  return `${formatUtcClock(start)}–${formatUtcClock(end)} UTC`;
}

function formatUtcClock(instant: Date): string {
  const hours = String(instant.getUTCHours()).padStart(2, "0");
  const minutes = String(instant.getUTCMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
}
