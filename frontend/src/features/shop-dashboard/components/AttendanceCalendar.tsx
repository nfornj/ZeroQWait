import React, { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isToday,
  parseISO,
  startOfMonth,
  startOfWeek,
  subMonths,
} from "date-fns";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface Shift {
  id: number;
  user_id: number;
  username: string;
  email: string;
  profile_photo_url?: string;
  shop_id: number;
  clock_in: string;
  clock_out?: string;
}

interface AttendanceCalendarProps {
  shifts: Shift[];
  employees: Array<{ id: number; username: string }>;
  onEmployeeChange?: (employeeId: number | null) => void;
}

const weekDays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const AttendanceCalendar: React.FC<AttendanceCalendarProps> = ({
  shifts,
  employees,
  onEmployeeChange,
}) => {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedEmployee, setSelectedEmployee] = useState<number | null>(null);

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calendarStart = startOfWeek(monthStart);
  const calendarEnd = endOfWeek(monthEnd);
  const calendarDays = eachDayOfInterval({ start: calendarStart, end: calendarEnd });

  const handlePreviousMonth = () => {
    const newMonth = subMonths(currentMonth, 1);
    const threeMonthsAgo = subMonths(new Date(), 3);
    if (newMonth >= threeMonthsAgo) setCurrentMonth(newMonth);
  };

  const handleNextMonth = () => {
    const newMonth = addMonths(currentMonth, 1);
    if (newMonth <= new Date()) setCurrentMonth(newMonth);
  };

  const handleEmployeeChange = (value: string) => {
    const employeeId = value === "all" ? null : Number(value);
    setSelectedEmployee(employeeId);
    onEmployeeChange?.(employeeId);
  };

  const getShiftsForDay = (date: Date): Shift[] => {
    return shifts.filter((shift) => {
      if (selectedEmployee !== null && shift.user_id !== selectedEmployee) return false;
      const shiftDate = parseISO(shift.clock_in);
      return isSameDay(shiftDate, date);
    });
  };

  const calculateDuration = (clockIn: string, clockOut?: string): string => {
    const start = parseISO(clockIn);
    const end = clockOut ? parseISO(clockOut) : new Date();
    const diffMs = end.getTime() - start.getTime();
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}h ${minutes}m`;
  };

  const formatTime = (dateString: string): string => format(parseISO(dateString), "h:mm a");

  const canGoBack = subMonths(currentMonth, 1) >= subMonths(new Date(), 3);
  const canGoForward = addMonths(currentMonth, 1) <= new Date();

  return (
    <TooltipProvider>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="rounded-xl border-border bg-background shadow-none"
              onClick={handlePreviousMonth}
              disabled={!canGoBack}
            >
              <ChevronLeft />
            </Button>
            <p className="min-w-[150px] text-center text-lg font-semibold">
              {format(currentMonth, "MMMM yyyy")}
            </p>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="rounded-xl border-border bg-background shadow-none"
              onClick={handleNextMonth}
              disabled={!canGoForward}
            >
              <ChevronRight />
            </Button>
          </div>

          <Select value={selectedEmployee === null ? "all" : String(selectedEmployee)} onValueChange={handleEmployeeChange}>
            <SelectTrigger className="w-full rounded-xl border-border bg-background shadow-none sm:w-[220px]">
              <SelectValue placeholder="Filter by employee" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">All Employees</SelectItem>
                {employees.map((employee) => (
                  <SelectItem key={employee.id} value={String(employee.id)}>
                    {employee.username}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>

        <Card className="rounded-2xl border-border bg-background shadow-none">
          <CardContent className="p-4">
            <div className="grid grid-cols-7 gap-2">
              {weekDays.map((day) => (
                <div key={day} className="text-center text-xs font-semibold text-muted-foreground">
                  {day}
                </div>
              ))}

              {calendarDays.map((day) => {
                const dayShifts = getShiftsForDay(day);
                const isCurrentMonth = day.getMonth() === currentMonth.getMonth();
                const today = isToday(day);

                return (
                  <div
                    key={day.toISOString()}
                    className={cn(
                      "min-h-[104px] rounded-lg border bg-card p-2",
                      !isCurrentMonth && "bg-muted/40 text-muted-foreground",
                      today && "border-primary ring-1 ring-primary",
                    )}
                  >
                    <p className={cn("text-xs", today && "font-semibold text-primary")}>
                      {format(day, "d")}
                    </p>
                    {dayShifts.length > 0 && (
                      <div className="mt-2 flex flex-col gap-1">
                        {dayShifts.slice(0, 3).map((shift) => (
                          <Tooltip key={shift.id}>
                            <TooltipTrigger asChild>
                              <Badge
                                variant={shift.clock_out ? "default" : "secondary"}
                                className="block w-full truncate text-center text-[0.65rem]"
                              >
                                {shift.username}
                              </Badge>
                            </TooltipTrigger>
                            <TooltipContent>
                              <div className="flex flex-col gap-1 text-xs">
                                <span className="font-semibold">{shift.username}</span>
                                <span>In: {formatTime(shift.clock_in)}</span>
                                <span>Out: {shift.clock_out ? formatTime(shift.clock_out) : "Still active"}</span>
                                <span className="font-semibold">Duration: {calculateDuration(shift.clock_in, shift.clock_out)}</span>
                              </div>
                            </TooltipContent>
                          </Tooltip>
                        ))}
                        {dayShifts.length > 3 && (
                          <p className="text-center text-xs text-muted-foreground">
                            +{dayShifts.length - 3} more
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-border bg-background shadow-none">
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-medium">Legend</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap justify-center gap-4 pb-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <Badge>Complete</Badge>
              <span>Shift completed</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">Active</Badge>
              <span>Still clocked in</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
};

export default AttendanceCalendar;
