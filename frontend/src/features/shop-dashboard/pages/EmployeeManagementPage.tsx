import React, { useEffect, useState } from "react";
import { CalendarDays, Plus, Users } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Skeleton className="h-40 w-full max-w-3xl" />
      </div>
    );
  }

  return (
    <div className="w-full max-w-[1700px]">
      <Header />

      <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-12">
        <Card className="md:col-span-8">
          <CardContent className="p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">Team Management</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Manage employees, assign roles, and review attendance in one place.
                </p>
              </div>
              {currentTab === "employees" && (
                <Button onClick={() => setOpenDialog(true)} disabled={!shopId} className="self-start md:self-center">
                  <Plus data-icon="inline-start" />
                  Add Employee
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
        <Card className="md:col-span-4">
          <CardContent className="p-6">
            <p className="text-sm text-muted-foreground">Active Team Members</p>
            <p className="mt-1 text-3xl font-semibold tracking-tight">
              {employees.filter((employee) => employee.is_active).length}
            </p>
          </CardContent>
        </Card>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {success && (
        <Alert className="mb-4">
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      <Tabs value={currentTab} onValueChange={setCurrentTab} className="flex flex-col gap-4">
        <TabsList className="w-fit">
          <TabsTrigger value="employees">
            <Users data-icon="inline-start" />
            Employee List
          </TabsTrigger>
          <TabsTrigger value="attendance">
            <CalendarDays data-icon="inline-start" />
            Attendance Calendar
          </TabsTrigger>
        </TabsList>

        <TabsContent value="employees">
          <Card>
            <CardContent className="p-0">
              <TeamDataGrid
                rows={employees}
                onDelete={handleRemoveEmployee}
                onReactivate={handleReactivateEmployee}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="attendance">
          {shiftsLoading ? (
            <div className="flex min-h-[400px] items-center justify-center">
              <Skeleton className="h-40 w-full max-w-3xl" />
            </div>
          ) : (
            <AttendanceCalendar
              shifts={shifts}
              employees={employees.filter((emp) => emp.is_active).map((emp) => ({
                id: emp.user.id,
                username: emp.user.username,
              }))}
              onEmployeeChange={setSelectedEmployeeFilter}
            />
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={openDialog} onOpenChange={setOpenDialog}>
        <DialogContent className="sm:max-w-lg">
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
              />
              <p className="text-xs text-muted-foreground">Temporary password - employee can change it later</p>
            </div>
            <div className="flex flex-col gap-2">
              <Label>Role</Label>
              <Select value={formData.role} onValueChange={(role) => setFormData({ ...formData, role })}>
                <SelectTrigger>
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
            <Button variant="outline" onClick={() => setOpenDialog(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button
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
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove Employee</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to remove this employee? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRemoveConfirmId(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmRemoveEmployee}>
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmployeeManagementPage;
