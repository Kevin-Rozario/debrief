import type { PersonResponse } from "@/api/types.ts";

export function personName(people: PersonResponse[], personId: number) {
  return people.find(person => person.id === personId)?.name ?? "";
}

export function otherPersonId(
  consultation: { client_id: number; practitioner_id: number },
  callerId: number,
) {
  return consultation.client_id === callerId
    ? consultation.practitioner_id
    : consultation.client_id;
}
