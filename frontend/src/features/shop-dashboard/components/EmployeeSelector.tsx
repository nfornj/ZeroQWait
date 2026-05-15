import React from "react";
import { Shuffle, User } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";

interface Employee {
  user_id: number;
  username: string;
  email: string;
  profile_photo_url?: string;
  clock_in: string;
}

interface EmployeeSelectorProps {
  open: boolean;
  employees: Employee[];
  loading?: boolean;
  onClose: () => void;
  onSelect: (employeeId: number | null) => void;
  title?: string;
  allowRandom?: boolean;
}

const EmployeeSelector: React.FC<EmployeeSelectorProps> = ({
  open,
  employees,
  loading = false,
  onClose,
  onSelect,
  title = "Assign Employee",
  allowRandom = true,
}) => {
  const [selectedOption, setSelectedOption] = React.useState<string>(allowRandom ? "random" : "specific");
  const [selectedEmployeeId, setSelectedEmployeeId] = React.useState<number | null>(null);

  const handleEmployeeSelect = (employeeId: number) => {
    setSelectedOption("specific");
    setSelectedEmployeeId(employeeId);
  };

  const handleConfirm = () => {
    if (selectedOption === "random") {
      onSelect(null);
    } else if (selectedEmployeeId) {
      onSelect(selectedEmployeeId);
    }
    handleClose();
  };

  const handleClose = () => {
    setSelectedOption(allowRandom ? "random" : "specific");
    setSelectedEmployeeId(null);
    onClose();
  };

  const getTimeSinceClockIn = (clockIn: string) => {
    const now = new Date();
    const clockInTime = new Date(clockIn);
    const diff = now.getTime() - clockInTime.getTime();
    const minutes = Math.floor(diff / 60000);

    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  const confirmDisabled =
    loading ||
    (employees.length === 0 && selectedOption === "specific") ||
    (selectedOption === "specific" && !selectedEmployeeId);

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && handleClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex min-h-[200px] flex-col justify-center gap-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : employees.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-sm font-medium">No employees are currently clocked in</p>
            <p className="mt-1 text-sm text-muted-foreground">You will be assigned as the server</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <ToggleGroup
              type="single"
              value={selectedOption}
              onValueChange={(value) => {
                if (!value) return;
                setSelectedOption(value);
                if (value === "random") setSelectedEmployeeId(null);
              }}
              className="justify-start"
              variant="outline"
            >
              {allowRandom && (
                <ToggleGroupItem value="random" aria-label="Random assignment">
                  <Shuffle data-icon="inline-start" />
                  Random
                  <Badge variant="secondary">Auto</Badge>
                </ToggleGroupItem>
              )}
              <ToggleGroupItem value="specific" aria-label="Select specific employee">
                <User data-icon="inline-start" />
                Specific
              </ToggleGroupItem>
            </ToggleGroup>

            {selectedOption === "specific" && (
              <ScrollArea className="max-h-[320px] pr-3">
                <div className="flex flex-col gap-2">
                  {employees.map((employee) => (
                    <button
                      key={employee.user_id}
                      type="button"
                      onClick={() => handleEmployeeSelect(employee.user_id)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-accent",
                        selectedEmployeeId === employee.user_id && "border-primary bg-accent",
                      )}
                    >
                      <Avatar>
                        <AvatarImage src={employee.profile_photo_url} alt={employee.username} />
                        <AvatarFallback>{employee.username.charAt(0).toUpperCase()}</AvatarFallback>
                      </Avatar>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{employee.username}</p>
                        <div className="mt-1 flex items-center gap-2">
                          <Badge>Online</Badge>
                          <span className="text-xs text-muted-foreground">
                            Clocked in {getTimeSinceClockIn(employee.clock_in)}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            )}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="button" onClick={handleConfirm} disabled={confirmDisabled}>
            Confirm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default EmployeeSelector;
