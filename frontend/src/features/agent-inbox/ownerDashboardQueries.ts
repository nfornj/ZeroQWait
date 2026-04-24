import { useQuery } from "@tanstack/react-query";

import api from "../../services/api";
import type { AgentFeedEvent, OwnerBriefing as OwnerBriefingData, OwnerDocumentRecord, PendingApproval, ShopPolicy } from "./types";

export interface QueueMetricsSnapshot {
  queue_length: number;
  estimated_wait_minutes: number;
  people_being_served: number;
  active_employees?: number;
  active_services?: number;
  today_revenue?: number;
  today_transactions?: number;
  weekly_revenue?: number;
  [key: string]: unknown;
}

export interface QueueRecord {
  id: number;
  name: string;
  is_active?: boolean;
  current_size?: number;
  [key: string]: unknown;
}

export interface AppointmentRecord {
  id: number;
  customer_name: string;
  customer_phone?: string | null;
  scheduled_start: string;
  scheduled_end: string;
  status: string;
  service_id?: number | null;
  employee_id?: number | null;
  service_cost?: number;
  notes?: string | null;
}

export interface EmployeeRecord {
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

export interface EmployeeAvailabilityRecord {
  employee_id: number;
  username: string;
  is_clocked_in: boolean;
  shift_start: string | null;
  appointments_today: number;
  next_available_slot: string | null;
}

export interface ServiceRecord {
  id: number;
  shop_id: number;
  name: string;
  description: string;
  duration_minutes: number;
  cost: number;
  currency: string;
  is_active: boolean;
}

export const ownerDashboardKeys = {
  briefing: (shopId: number) => ["owner-dashboard", "briefing", shopId] as const,
  pending: (shopId: number) => ["owner-dashboard", "pending", shopId] as const,
  feed: (shopId: number) => ["owner-dashboard", "feed", shopId] as const,
  documents: (shopId: number) => ["owner-dashboard", "documents", shopId] as const,
  policies: (shopId: number) => ["owner-dashboard", "policies", shopId] as const,
  queueMetrics: (shopId: number) => ["owner-dashboard", "queue-metrics", shopId] as const,
  queues: (shopId: number) => ["owner-dashboard", "queues", shopId] as const,
  appointmentsToday: (shopId: number) => ["owner-dashboard", "appointments-today", shopId] as const,
  employees: (shopId: number) => ["owner-dashboard", "employees", shopId] as const,
  employeeAvailability: (shopId: number, dateKey: string) => ["owner-dashboard", "employee-availability", shopId, dateKey] as const,
  services: (shopId: number) => ["owner-dashboard", "services", shopId] as const,
};

export const useOwnerBriefingQuery = (shopId?: number) =>
  useQuery({
    queryKey: shopId ? ownerDashboardKeys.briefing(shopId) : ["owner-dashboard", "briefing", "idle"],
    queryFn: async () => {
      const { data } = await api.get<OwnerBriefingData>("/v2/agent/briefing", {
        params: { shop_id: shopId },
      });
      return data;
    },
    enabled: Boolean(shopId),
  });

export const usePendingApprovalsQuery = (shopId?: number) =>
  useQuery({
    queryKey: shopId ? ownerDashboardKeys.pending(shopId) : ["owner-dashboard", "pending", "idle"],
    queryFn: async () => {
      const { data } = await api.get<{ pending: PendingApproval[] }>("/v2/agent/pending", {
        params: { shop_id: shopId },
      });
      return data.pending || [];
    },
    enabled: Boolean(shopId),
  });

export const useOwnerFeedQuery = (shopId?: number, limit = 25) =>
  useQuery({
    queryKey: shopId ? [...ownerDashboardKeys.feed(shopId), limit] : ["owner-dashboard", "feed", "idle", limit],
    queryFn: async () => {
      const { data } = await api.get<{ events: AgentFeedEvent[] }>("/v2/agent/feed", {
        params: { shop_id: shopId, limit },
      });
      return data.events || [];
    },
    enabled: Boolean(shopId),
  });

export const useOwnerDocumentsQuery = (shopId?: number) =>
  useQuery({
    queryKey: shopId ? ownerDashboardKeys.documents(shopId) : ["owner-dashboard", "documents", "idle"],
    queryFn: async () => {
      const { data } = await api.get<{ documents: OwnerDocumentRecord[] }>("/v2/agent/documents", {
        params: { shop_id: shopId },
      });
      return data.documents || [];
    },
    enabled: Boolean(shopId),
  });

export const useOwnerPoliciesQuery = (shopId?: number) =>
  useQuery({
    queryKey: shopId ? ownerDashboardKeys.policies(shopId) : ["owner-dashboard", "policies", "idle"],
    queryFn: async () => {
      const { data } = await api.get<{ policies: ShopPolicy[] }>("/v2/agent/policies", {
        params: { shop_id: shopId },
      });
      return data.policies || [];
    },
    enabled: Boolean(shopId),
  });

export const useOwnerOperationsSnapshot = (shopId?: number) => {
  const todayKey = new Date().toISOString().split("T")[0];

  const queueMetricsQuery = useQuery({
    queryKey: shopId ? ownerDashboardKeys.queueMetrics(shopId) : ["owner-dashboard", "queue-metrics", "idle"],
    queryFn: async () => {
      const { data } = await api.get<QueueMetricsSnapshot>(`/queues/shop/${shopId}/live-metrics`);
      return data;
    },
    enabled: Boolean(shopId),
  });

  const queuesQuery = useQuery({
    queryKey: shopId ? ownerDashboardKeys.queues(shopId) : ["owner-dashboard", "queues", "idle"],
    queryFn: async () => {
      const { data } = await api.get<QueueRecord[]>(`/queues/shop/${shopId}/all`);
      return data || [];
    },
    enabled: Boolean(shopId),
  });

  const appointmentsQuery = useQuery({
    queryKey: shopId ? ownerDashboardKeys.appointmentsToday(shopId) : ["owner-dashboard", "appointments-today", "idle"],
    queryFn: async () => {
      const { data } = await api.get<AppointmentRecord[]>(`/appointments/shop/${shopId}/today`);
      return data || [];
    },
    enabled: Boolean(shopId),
  });

  const employeesQuery = useQuery({
    queryKey: shopId ? ownerDashboardKeys.employees(shopId) : ["owner-dashboard", "employees", "idle"],
    queryFn: async () => {
      const { data } = await api.get<EmployeeRecord[]>(`/shops/${shopId}/employees`);
      return data || [];
    },
    enabled: Boolean(shopId),
  });

  const employeeAvailabilityQuery = useQuery({
    queryKey: shopId ? ownerDashboardKeys.employeeAvailability(shopId, todayKey) : ["owner-dashboard", "employee-availability", "idle", todayKey],
    queryFn: async () => {
      const { data } = await api.get<EmployeeAvailabilityRecord[]>(`/appointments/shop/${shopId}/employee-availability`, {
        params: { date: todayKey },
      });
      return data || [];
    },
    enabled: Boolean(shopId),
  });

  const servicesQuery = useQuery({
    queryKey: shopId ? ownerDashboardKeys.services(shopId) : ["owner-dashboard", "services", "idle"],
    queryFn: async () => {
      const { data } = await api.get<ServiceRecord[]>(`/shops/${shopId}/services`);
      return data || [];
    },
    enabled: Boolean(shopId),
  });

  const queueMetrics = queueMetricsQuery.data;
  const queues = queuesQuery.data || [];
  const appointments = appointmentsQuery.data || [];
  const employees = employeesQuery.data || [];
  const employeeAvailability = employeeAvailabilityQuery.data || [];
  const services = servicesQuery.data || [];

  const activeQueues = queues.filter((queue) => queue.is_active !== false).length;
  const confirmedAppointments = appointments.filter((appointment) =>
    ["scheduled", "confirmed", "checked_in", "in_progress"].includes(appointment.status)
  ).length;
  const activeAppointments = appointments.filter((appointment) =>
    ["checked_in", "in_progress"].includes(appointment.status)
  ).length;
  const clockedInEmployees = employeeAvailability.filter((entry) => entry.is_clocked_in).length;
  const unavailableEmployees = employeeAvailability.filter((entry) => !entry.is_clocked_in).length;
  const averageServiceDuration =
    services.length > 0
      ? Math.round(services.reduce((total, service) => total + Number(service.duration_minutes || 0), 0) / services.length)
      : 0;
  const averageServiceCost =
    services.length > 0
      ? services.reduce((total, service) => total + Number(service.cost || 0), 0) / services.length
      : 0;

  return {
    queueMetrics,
    queues,
    appointments,
    employees,
    employeeAvailability,
    services,
    stats: {
      waiting: Number(queueMetrics?.queue_length || 0),
      etaMinutes: Number(queueMetrics?.estimated_wait_minutes || 0),
      activeQueues,
      confirmedAppointments,
      activeAppointments,
      totalEmployees: employees.length,
      clockedInEmployees,
      unavailableEmployees,
      totalServices: services.length,
      averageServiceDuration,
      averageServiceCost,
    },
    isLoading:
      queueMetricsQuery.isLoading ||
      queuesQuery.isLoading ||
      appointmentsQuery.isLoading ||
      employeesQuery.isLoading ||
      employeeAvailabilityQuery.isLoading ||
      servicesQuery.isLoading,
    isFetching:
      queueMetricsQuery.isFetching ||
      queuesQuery.isFetching ||
      appointmentsQuery.isFetching ||
      employeesQuery.isFetching ||
      employeeAvailabilityQuery.isFetching ||
      servicesQuery.isFetching,
    queries: {
      queueMetricsQuery,
      queuesQuery,
      appointmentsQuery,
      employeesQuery,
      employeeAvailabilityQuery,
      servicesQuery,
    },
  };
};