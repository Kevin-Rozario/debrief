import { CalendarIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatLocalInstant } from "@/lib/time.ts";

export function DateTimePicker({
  id,
  value,
  onChange,
  invalid = false,
  describedBy,
}: {
  id: string;
  value: Date;
  onChange: (value: Date) => void;
  invalid?: boolean;
  describedBy?: string;
}) {
  const [open, setOpen] = useState(false);

  function chooseDay(day: Date | undefined) {
    if (day === undefined) {
      return;
    }
    const next = new Date(day);
    next.setHours(value.getHours(), value.getMinutes(), 0, 0);
    onChange(next);
  }

  function chooseTime(time: string) {
    const [hourText, minuteText] = time.split(":");
    const hour = Number(hourText);
    const minute = Number(minuteText);
    if (!Number.isInteger(hour) || !Number.isInteger(minute)) {
      return;
    }
    const next = new Date(value);
    next.setHours(hour, minute, 0, 0);
    onChange(next);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={(
          <Button
            id={id}
            type="button"
            variant="outline"
            aria-invalid={invalid}
            aria-describedby={describedBy}
            className="mt-3 h-11 w-full justify-start px-3 text-base font-normal motion-reduce:transition-none motion-reduce:active:translate-y-0"
          />
        )}
      >
        <CalendarIcon />
        {formatLocalInstant(value)}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-0">
        <Calendar
          key={`${value.getFullYear()}-${value.getMonth()}`}
          mode="single"
          selected={value}
          defaultMonth={value}
          onSelect={chooseDay}
        />
        <div className="border-t border-stone-200 p-3 dark:border-stone-800">
          <Label htmlFor={`${id}-time`}>Time</Label>
          <Input
            id={`${id}-time`}
            type="time"
            step={60}
            value={toTimeInput(value)}
            onChange={event => chooseTime(event.target.value)}
            className="mt-2"
          />
        </div>
      </PopoverContent>
    </Popover>
  );
}

function toTimeInput(value: Date) {
  const hour = String(value.getHours()).padStart(2, "0");
  const minute = String(value.getMinutes()).padStart(2, "0");
  return `${hour}:${minute}`;
}
