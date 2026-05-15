import React, { useEffect, useState } from "react";
import { ArrowUpRight, CalendarDays, CheckCircle, Plus, ShieldCheck, Users, UsersRound } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import api from "../../../services/api";
import AttendanceCalendar from "../components/AttendanceCalendar";
import TeamDataGrid from "../components/TeamDataGrid";
import Header from "../components/Header";

interface Employee {
  employee_link_id: number;
  shop_id: number;
  created_at: string;
  is_active: boolean;
  user: {
    id: number;
    username: string;
    email: string;
    role: string;
    is_active: boolean;
  };
}

const dashboardSurfaceStyle = {
  "--background": "210 20% 98%",
  "--foreground": "222 47% 11%",
  "--card": "0 0% 100%",
  "--card-foreground": "222 47% 11%",
  "--popover": "0 0% 100%",
  "--popover-foreground": "222 47% 11%",
  "--muted": "210 40% 96%",
  "--muted-foreground": "215 16% 47%",
  "--border": "214 32% 91%",
  "--input": "214 32% 91%",
  "--primary": "154 40% 30%",
  "--primary-foreground": "0 0% 100%",
  "--ring": "154 40% 30%",
} as React.CSSProperties;

const teamSections = [
  { label: "Roster", sub: "Access and roles", icon: Users },
  { label: "Attendance", sub: "Clock-in history", icon: CalendarDays },
  { label: "Managers", sub: "Owner coverage", icon: ShieldCheck },
  { label: "Status", sub: "Active members", icon: CheckCircle },
];

function MetricCard({ icon: Icon, value, label }: { icon: React.ElementType; value: number; label: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-none">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-2xl font-bold tracking-tight text-foreground">{value}</p>
          <p className="mt-1 text-sm text-muted-foreground">{label}</p>
        </div>
        <span className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-background text-primary">
          <Icon className="h-4 w-4" />
        </span>
      </div>
    </div>
  );
}

const EmployeeManagementPage: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [shopId, setShopId] = useState<number | null>(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    role: "employee",
  });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);
  const [checkingUsername, setCheckingUsername] = useState(false);
  const [emailAvailable, setEmailAvailable] = useState<boolean | null>(null);
  const [checkingEmail, setCheckingEmail] = useState(false);
  const [currentTab, setCurrentTab] = useState("employees");
  const [shifts, setShifts] = useState<any[]>([]);
  const [shiftsLoading, setShiftsLoading] = useState(false);
  const [selectedEmployeeFilter, setSelectedEmployeeFilter] = useState<number | null>(null);
  const [removeConfirmId, setRemoveConfirmId] = useState<number | null>(null);

  const fetchEmployees = React.useCallback(async (id: number) => {
    try {
      const response = await api.get(`/shops/${id}/employees`);
      setEmployees(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load employees");
    }
  }, []);

  const fetchShopAndEmployees = React.useCallback(async () => {
    try {
      const shopResponse = await api.get(`/shops/my-shops`);

      if (shopResponse.data.length === 0) {
        setError("No shop found. Please create a shop first.");
        setLoading(false);
        return;
      }

      const shop = shopResponse.data[0];
      setShopId(shop.id);
      await fetchEmployees(shop.id);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [fetchEmployees]);

  const fetchShifts = React.useCallback(async (id: number, employeeId: number | null = null) => {
    setShiftsLoading(true);
    try {
      let url = `/shops/${id}/employee-shifts?months=3`;
      if (employeeId) url += `&employee_id=${employeeId}`;
      const response = await api.get(url);
      setShifts(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load attendance data");
    } finally {
      setShiftsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchShopAndEmployees();
  }, [fetchShopAndEmployees]);

  useEffect(() => {
    if (currentTab === "attendance" && shopId) {
      fetchShifts(shopId, selectedEmployeeFilter);
    }
  }, [currentTab, shopId, selectedEmployeeFilter, fetchShifts]);

  useEffect(() => {
    const checkUsername = async () => {
      if (!formData.username || formData.username.length < 3) {
        setUsernameAvailable(null);
        return;
      }

      setCheckingUsername(true);
      try {
        const response = await api.get(`/check-username/${formData.username}`);
        setUsernameAvailable(response.data.available);
      } catch {
        setUsernameAvailable(null);
      } finally {
        setCheckingUsername(false);
      }
    };

    const timeoutId = setTimeout(checkUsername, 500);
    return () => clearTimeout(timeoutId);
  }, [formData.username]);

  useEffect(() => {
    const checkEmail = async () => {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!formData.email || !emailRegex.test(formData.email)) {
        setEmailAvailable(null);
        return;
      }

      setCheckingEmail(true);
      try {
        const response = await api.get(`/check-email/${encodeURIComponent(formData.email)}`);
        setEmailAvailable(response.data.available);
      } catch {
        setEmailAvailable(null);
      } finally {
        setCheckingEmail(false);
      }
    };

    const timeoutId = setTimeout(checkEmail, 500);
    return () => clearTimeout(timeoutId);
  }, [formData.email]);

  const handleAddEmployee = async () => {
    if (!shopId) return;

    setSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      await api.post(`/shops/${shopId}/employees`, formData);
      setSuccess("Employee added successfully!");
      setFormData({ username: "", email: "", password: "", role: "employee" });
      setOpenDialog(false);
      await fetchEmployees(shopId);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to add employee");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveEmployee = async (employeeId: number) => {
    if (!shopId) return;
    setRemoveConfirmId(employeeId);
  };

  const confirmRemoveEmployee = async () => {
    if (!shopId || removeConfirmId === null) return;
    try {
      await api.delete(`/shops/${shopId}/employees/${removeConfirmId}`);
      setSuccess("Employee removed successfully!");
      setRemoveConfirmId(null);
      await fetchEmployees(shopId);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to remove employee");
      setRemoveConfirmId(null);
    }
  };

  const handleReactivateEmployee = async (employeeId: number) => {
    if (!shopId) return;

    try {
      await api.put(`/shops/${shopId}/employees/${employeeId}/reactivate`, {});
      setSuccess("Employee reactivated successfully!");
      await fetchEmployees(shopId);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to reactivate employee");
    }
  };

  const fieldStatus = (checking: boolean, available: boolean | null, fallback = "") => {
    if (checking) return "Checking availability...";
    if (available === false) return "Already taken";
    if (available === true) return "Available";
    return fallback;
  };

  const activeMembers = employees.filter((employee) => employee.is_active).length;
  const managerCount = employees.filter((employee) => employee.is_active && employee.user.role === "manager").length;
  const staffCount = employees.filter((employee) => employee.is_active && employee.user.role !== "manager").length;

  if (loading) {
    return (
      <div className="flex min-h-full w-full flex-col bg-[#f9fafb] px-3 pb-16 md:px-6" style={dashboardSurfaceStyle}>
        <div className="flex min-h-[400px] items-center justify-center">
          <Skeleton className="h-40 w-full max-w-3xl rounded-2xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-full w-full flex-col bg-[#f9fafb] px-3 pb-16 md:px-6" style={dashboardSurfaceStyle}>
      <Header />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Team workspace</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage employee access, roles, and attendance from one focused roster.
          </p>
        </div>
        {currentTab === "employees" && (
          <Button
            onClick={() => setOpenDialog(true)}
            disabled={!shopId}
            className="w-full rounded-xl bg-primary text-primary-foreground shadow-none hover:bg-primary/90 sm:w-auto"
          >
            <Plus data-icon="inline-start" />
            Add employee
          </Button>
        )}
      </div>

      <nav className="mb-6 rounded-2xl border border-border bg-card p-1.5">
        <div className="grid grid-cols-1 gap-1 sm:grid-cols-2 xl:grid-cols-4">
          {teamSections.map((item, index) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                type="button"
                className="relative flex items-center gap-3 rounded-xl px-4 py-3.5 text-left transition-all hover:bg-muted/45"
              >
                <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border border-border bg-background text-muted-foreground">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-foreground">{item.label}</span>
                  <span className="block truncate text-xs text-muted-foreground">{item.sub}</span>
                </span>
                {index === 0 && <span className="absolute bottom-0 left-4 right-4 h-0.5 rounded-full bg-primary" />}
              </button>
            );
          })}
        </div>
      </nav>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="rounded-2xl border border-border bg-card p-6 shadow-none lg:col-span-8">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1 text-xs font-semibold text-muted-foreground">
                <UsersRound className="h-3.5 w-3.5 text-primary" />
                Staff operations
              </div>
              <h2 className="mt-4 text-2xl font-bold tracking-tight text-foreground">Team management</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                Keep your team list clean, track who is active, and review attendance patterns before assigning shifts.
              </p>
            </div>
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
              <ArrowUpRight className="h-5 w-5" />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:col-span-4 lg:grid-cols-1">
          <MetricCard icon={CheckCircle} value={activeMembers} label="Active members" />
          <MetricCard icon={ShieldCheck} value={managerCount} label="Managers" />
          <MetricCard icon={Users} value={staffCount} label="Employees" />
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4 rounded-2xl">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {success && (
        <Alert className="mb-4 rounded-2xl border-emerald-500/30 bg-emerald-500/10 text-emerald-700">
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      <Tabs value={currentTab} onValueChange={setCurrentTab} className="flex flex-col gap-4">
        <TabsList className="w-fit rounded-2xl border border-border bg-card p-1.5">
          <TabsTrigger
            value="employees"
            className="rounded-xl px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm"
          >
            <Users data-icon="inline-start" />
            Employee list
          </TabsTrigger>
          <TabsTrigger
            value="attendance"
            className="rounded-xl px-4 data-[state=active]:bg-background data-[state=active]:shadow-sm"
          >
            <CalendarDays data-icon="inline-start" />
            Attendance calendar
          </TabsTrigger>
        </TabsList>

        <TabsContent value="employees">
          <TeamDataGrid
            rows={employees}
            onDelete={handleRemoveEmployee}
            onReactivate={handleReactivateEmployee}
          />
        </TabsContent>

        <TabsContent value="attendance">
          {shiftsLoading ? (
            <div className="flex min-h-[400px] items-center justify-center rounded-2xl border border-border bg-card">
              <Skeleton className="h-40 w-full max-w-3xl rounded-2xl" />
            </div>
          ) : (
            <div className="rounded-2xl border border-border bg-card p-4 shadow-none">
              <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-base font-semibold tracking-tight text-foreground">Attendance history</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Review recent clock-ins by employee.</p>
                </div>
                <Badge variant="outline" className="w-fit rounded-full border-border bg-background text-muted-foreground">
                  Last 3 months
                </Badge>
              </div>
              <AttendanceCalendar
                shifts={shifts}
                employees={employees.filter((emp) => emp.is_active).map((emp) => ({
                  id: emp.user.id,
                  username: emp.user.username,
                }))}
                onEmployeeChange={setSelectedEmployeeFilter}
              />
            </div>
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={openDialog} onOpenChange={setOpenDialog}>
        <DialogContent className="rounded-2xl sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Add New Employee</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="employee-username">Username</Label>
              <Input
                id="employee-username"
                value={formData.username}
                onChange={(event) => setFormData({ ...formData, username: event.target.value })}
                aria-invalid={usernameAvailable === false}
                className="rounded-xl border-border bg-background"
              />
              <p className="text-xs text-muted-foreground">
                {fieldStatus(checkingUsername, usernameAvailable, "Employee will use this to log in")}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="employee-email">Email</Label>
              <Input
                id="employee-email"
                type="email"
                value={formData.email}
                onChange={(event) => setFormData({ ...formData, email: event.target.value })}
                aria-invalid={emailAvailable === false}
                className="rounded-xl border-border bg-background"
              />
              <p className="text-xs text-muted-foreground">
                {fieldStatus(checkingEmail, emailAvailable)}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="employee-password">Password</Label>
              <Input
                id="employee-password"
                type="password"
                value={formData.password}
                onChange={(event) => setFormData({ ...formData, password: event.target.value })}
                className="rounded-xl border-border bg-background"
              />
              <p className="text-xs text-muted-foreground">Temporary password - employee can change it later</p>
            </div>
            <div className="flex flex-col gap-2">
              <Label>Role</Label>
              <Select value={formData.role} onValueChange={(role) => setFormData({ ...formData, role })}>
                <SelectTrigger className="rounded-xl border-border bg-background">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="employee">Employee</SelectItem>
                    <SelectItem value="manager">Manager</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" className="rounded-xl" onClick={() => setOpenDialog(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button
              className="rounded-xl"
              onClick={handleAddEmployee}
              disabled={
                submitting ||
                !formData.username ||
                !formData.email ||
                !formData.password ||
                usernameAvailable === false ||
                emailAvailable === false ||
                checkingUsername ||
                checkingEmail
              }
            >
              {submitting ? "Adding..." : "Add Employee"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={removeConfirmId !== null} onOpenChange={(next) => !next && setRemoveConfirmId(null)}>
        <DialogContent className="rounded-2xl">
          <DialogHeader>
            <DialogTitle>Remove Employee</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to remove this employee? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" className="rounded-xl" onClick={() => setRemoveConfirmId(null)}>
              Cancel
            </Button>
            <Button variant="destructive" className="rounded-xl" onClick={confirmRemoveEmployee}>
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmployeeManagementPage;
