/** JSON shapes from `backend/app/schemas.py`. Datetimes are UTC strings ending in Z. */

export type PersonRole = "client" | "practitioner";

export type ConsultationStatus = "scheduled" | "completed" | "cancelled";

export type ErrorCode
  = | "AUTHENTICATION_REQUIRED"
    | "PERMISSION_DENIED"
    | "RESOURCE_NOT_FOUND"
    | "CONSULTATION_NOT_SCHEDULED"
    | "CONSULTATION_NOT_STARTED"
    | "CONSULTATION_NOT_COMPLETED"
    | "NOTE_ALREADY_EXISTS"
    | "NOTE_ALREADY_SHARED"
    | "NOTE_NOT_SHARED"
    | "SCHEDULING_CONFLICT"
    | "VALIDATION_ERROR"
    | "INTERNAL_SERVER_ERROR";

export interface ErrorDetail {
  field: string;
  message: string;
}

export interface ErrorBody {
  code: ErrorCode;
  status: number;
  details: ErrorDetail[];
}

export interface ResponseMeta {
  request_id: string;
  timestamp: string;
}

export interface UniformResponse<T> {
  success: boolean;
  message: string;
  data: T | null;
  error: ErrorBody | null;
  meta: ResponseMeta;
}

export interface ServiceInfo {
  name: string;
  version: string;
}

export interface HealthStatus {
  status: string;
}

export interface LoginRequest {
  person_id: number;
}

export interface TokenResponseData {
  token: string;
}

export interface PersonResponse {
  id: number;
  name: string;
  role: PersonRole;
}

export interface PractitionerResponse {
  id: number;
  name: string;
  specialty: string | null;
}

export interface BookConsultationRequest {
  practitioner_id: number;
  starts_at: string;
  ends_at: string;
}

export interface ConsultationResponse {
  id: number;
  client_id: number;
  practitioner_id: number;
  starts_at: string;
  ends_at: string;
  status: ConsultationStatus;
  cancelled_by_id: number | null;
}

export interface CreateNoteRequest {
  body: string;
}

export interface UpdateNoteRequest {
  body: string;
}

export interface CreateAddendumRequest {
  body: string;
}

export interface AddendumResponse {
  id: number;
  note_id: number;
  body: string;
  created_at: string;
}

export interface NoteResponse {
  id: number;
  consultation_id: number;
  body: string;
  shared_at: string | null;
  created_at: string;
  addenda: AddendumResponse[];
}

export type ConsultationDetailResponse = ConsultationResponse & {
  note: NoteResponse | null;
};
