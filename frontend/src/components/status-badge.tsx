import type { ConsultationStatus } from "@/api/types.ts";
import { Badge } from "@/components/ui/badge";

const LABEL: Record<ConsultationStatus, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};

const WEIGHT: Record<ConsultationStatus, string> = {
  scheduled: "bg-stone-800 text-stone-50 dark:bg-stone-200 dark:text-stone-900",
  completed: "bg-stone-400 text-stone-950 dark:bg-stone-500 dark:text-stone-50",
  cancelled:
    "bg-stone-200 text-stone-500 dark:bg-stone-800 dark:text-stone-500",
};

export function StatusBadge({ status }: { status: ConsultationStatus }) {
  return <Badge className={WEIGHT[status]}>{LABEL[status]}</Badge>;
}
