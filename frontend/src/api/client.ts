import type {
  ErrorBody,
  ErrorCode,
  ErrorDetail,
  UniformResponse,
} from "./types.ts";

export const TICKET_STORAGE_KEY = "debrief.ticket";

const ERROR_CODES = new Set<ErrorCode>([
  "AUTHENTICATION_REQUIRED",
  "PERMISSION_DENIED",
  "RESOURCE_NOT_FOUND",
  "CONSULTATION_NOT_SCHEDULED",
  "CONSULTATION_NOT_STARTED",
  "CONSULTATION_NOT_COMPLETED",
  "NOTE_ALREADY_EXISTS",
  "NOTE_ALREADY_SHARED",
  "NOTE_NOT_SHARED",
  "SCHEDULING_CONFLICT",
  "VALIDATION_ERROR",
  "INTERNAL_SERVER_ERROR",
]);

export class ApiError extends Error {
  readonly code: ErrorCode;
  readonly status: number;
  readonly details: ErrorDetail[];

  constructor(
    message: string,
    code: ErrorCode,
    status: number,
    details: ErrorDetail[],
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function errorMessage(error: unknown, fallback: string): string | null {
  if (error == null) {
    return null;
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  return fallback;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
}

export function readTicket(): string | null {
  const ticket = localStorage.getItem(TICKET_STORAGE_KEY);
  if (ticket === null || ticket.trim() === "") {
    return null;
  }
  return ticket;
}

export function storeTicket(ticket: string): void {
  localStorage.setItem(TICKET_STORAGE_KEY, ticket);
  notifyTicket();
}

export function clearTicket(): void {
  localStorage.removeItem(TICKET_STORAGE_KEY);
  notifyTicket();
}

const ticketListeners = new Set<() => void>();

export function subscribeTicket(listener: () => void) {
  ticketListeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === TICKET_STORAGE_KEY) {
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    ticketListeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers({ Accept: "application/json" });
  const ticket = readTicket();
  if (ticket !== null) {
    headers.set("Authorization", `Bearer ${ticket}`);
  }
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(apiUrl(path), {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (response.status === 401) {
    clearTicket();
  }

  const envelope = await parseEnvelope<T>(response);
  if (isSignedOut(response.status, envelope)) {
    clearTicket();
  }
  if (!envelope.success || envelope.error !== null) {
    throw errorFromEnvelope(envelope, response.status);
  }
  return envelope.data as T;
}

function notifyTicket() {
  for (const listener of ticketListeners) {
    listener();
  }
}

function apiUrl(path: string): string {
  const base = import.meta.env.VITE_BACKEND_ORIGIN;
  if (typeof base !== "string" || base.trim() === "") {
    throw new Error("VITE_BACKEND_ORIGIN is not set.");
  }
  const prefix = base.replace(/\/$/, "");
  return `${prefix}${path.startsWith("/") ? path : `/${path}`}`;
}

function isSignedOut(
  httpStatus: number,
  envelope: UniformResponse<unknown>,
): boolean {
  return (
    httpStatus === 401 ||
    envelope.error?.status === 401 ||
    envelope.error?.code === "AUTHENTICATION_REQUIRED"
  );
}

function errorFromEnvelope(
  envelope: UniformResponse<unknown>,
  httpStatus: number,
): ApiError {
  const error = envelope.error;
  return new ApiError(
    envelope.message,
    error?.code ?? codeForStatus(httpStatus),
    error?.status ?? httpStatus,
    error?.details ?? [],
  );
}

function codeForStatus(status: number): ErrorCode {
  if (status === 401) {
    return "AUTHENTICATION_REQUIRED";
  }
  return "INTERNAL_SERVER_ERROR";
}

async function parseEnvelope<T>(
  response: Response,
): Promise<UniformResponse<T>> {
  let parsed: unknown;
  try {
    parsed = await response.json();
  } catch {
    throw new ApiError(
      "The server returned a response that was not JSON.",
      codeForStatus(response.status),
      response.status,
      [],
    );
  }
  if (!isUniformResponse(parsed)) {
    throw new ApiError(
      "The server returned a response that was not the expected envelope.",
      codeForStatus(response.status),
      response.status,
      [],
    );
  }
  return parsed as UniformResponse<T>;
}

function isUniformResponse(value: unknown): value is UniformResponse<unknown> {
  if (!isRecord(value)) {
    return false;
  }
  if (typeof value.success !== "boolean" || typeof value.message !== "string") {
    return false;
  }
  if (!("data" in value)) {
    return false;
  }
  if (value.error !== null && !isErrorBody(value.error)) {
    return false;
  }
  if (!isRecord(value.meta)) {
    return false;
  }
  return (
    typeof value.meta.request_id === "string" &&
    typeof value.meta.timestamp === "string"
  );
}

function isErrorBody(value: unknown): value is ErrorBody {
  if (!isRecord(value)) {
    return false;
  }
  if (!isErrorCode(value.code) || typeof value.status !== "number") {
    return false;
  }
  return Array.isArray(value.details) && value.details.every(isErrorDetail);
}

function isErrorDetail(value: unknown): value is ErrorDetail {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.field === "string" && typeof value.message === "string";
}

function isErrorCode(value: unknown): value is ErrorCode {
  return typeof value === "string" && ERROR_CODES.has(value as ErrorCode);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
