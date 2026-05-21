import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ShopSettingsPage from "./ShopSettingsPage";
import api from "../../../services/api";

jest.mock("@/lib/utils", () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(" "),
}), { virtual: true });

jest.mock("../../../services/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    put: jest.fn(),
    post: jest.fn(),
    delete: jest.fn(),
  },
}));

const mockSetThemePreset = jest.fn();
const mockSetDashboardGradient = jest.fn();
const mockRefreshOwnedShops = jest.fn();

jest.mock("../../../contexts/ThemeContext", () => ({
  useThemeContext: () => ({
    themePreset: "forest",
    setThemePreset: mockSetThemePreset,
    dashboardGradient: "ocean",
    setDashboardGradient: mockSetDashboardGradient,
  }),
  gradientPresets: {
    minimal: { light: "none", dark: "none" },
    violet: { light: "linear-gradient(violet, white)", dark: "linear-gradient(violet, black)" },
    ocean: { light: "linear-gradient(blue, cyan)", dark: "linear-gradient(navy, teal)" },
    sunset: { light: "linear-gradient(orange, yellow)", dark: "linear-gradient(brown, orange)" },
  },
}));

jest.mock("../../../contexts/ShopContext", () => ({
  useShop: () => ({
    refreshOwnedShops: mockRefreshOwnedShops,
  }),
}));

const shop = {
  id: 41,
  name: "Persisted Settings Shop",
  description: "Persisted dashboard description",
  shop_type: "Spa & Wellness",
  address: "123 Kingston Rd",
  city: "Scarborough",
  state: "ON",
  zip_code: "M1N 1T7",
  country: "Canada",
  phone: "647 879 2555",
  email: "hello@wingspa.ca",
  website: "www.wingspa.ca",
  tagline: "Relax. Restore. Rebalance.",
  tax_id: "BN-123",
  timezone: "America/Toronto",
  instagram: "@wingspawellness",
  whatsapp: "+1 647 879 2555",
  primary_color: "#2D6A4F",
  secondary_color: "#D8F3DC",
  dashboard_gradient: "ocean",
  logo_url: "",
  slug: "wing-spa-wellness",
};

const businessHours = [
  { day: "Monday", isOpen: true, openTime: "09:00", closeTime: "19:00" },
  { day: "Tuesday", isOpen: true, openTime: "09:00", closeTime: "19:00" },
  { day: "Wednesday", isOpen: true, openTime: "09:00", closeTime: "19:00" },
  { day: "Thursday", isOpen: true, openTime: "09:00", closeTime: "20:00" },
  { day: "Friday", isOpen: true, openTime: "09:00", closeTime: "20:00" },
  { day: "Saturday", isOpen: true, openTime: "10:00", closeTime: "18:00" },
  { day: "Sunday", isOpen: false, openTime: "09:00", closeTime: "18:00" },
];

const bookingSettings = {
  bookingEnabled: true,
  requireConfirmation: true,
  allowRescheduling: true,
  allowCancellations: true,
  bookingNotice: "24",
  reminderPreferences: "both",
  reminderTime: "24",
  followUp: true,
  waitingList: true,
  autoConfirm: false,
};

describe("ShopSettingsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRefreshOwnedShops.mockResolvedValue([shop]);
    (api.put as jest.Mock).mockResolvedValue({ data: {} });
    (api.get as jest.Mock).mockImplementation((url: string) => {
      if (url === "/shops/my-shops") return Promise.resolve({ data: [shop] });
      if (url.endsWith("/business-hours")) return Promise.resolve({ data: businessHours });
      if (url.endsWith("/booking-settings")) return Promise.resolve({ data: bookingSettings });
      if (url.endsWith("/services")) return Promise.resolve({ data: [] });
      if (url.endsWith("/close-days")) return Promise.resolve({ data: [] });
      if (url.endsWith("/llm-settings")) {
        return Promise.resolve({
          data: {
            shop_id: 41,
            subscription_tier: "free",
            environment_name: "Managed AI",
            environment_summary: "Managed by ZeroQwait",
            operating_mode: "managed",
            status_label: "Ready",
            uses_default: true,
            can_customize: false,
            capabilities: [],
            experience_notes: [],
          },
        });
      }
      return Promise.resolve({ data: {} });
    });
  });

  it("loads persisted settings and saves all settings endpoints", async () => {
    render(<ShopSettingsPage />);

    const shopNameInputs = await screen.findAllByDisplayValue("Persisted Settings Shop");
    fireEvent.change(shopNameInputs[0], { target: { value: "Updated Settings Shop" } });
    fireEvent.click(screen.getByRole("button", { name: /Save & Continue/i }));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith(
        "/shops/41",
        expect.objectContaining({
          name: "Updated Settings Shop",
          shop_type: "Spa & Wellness",
          dashboard_gradient: "ocean",
          timezone: "America/Toronto",
        }),
      );
      expect(api.put).toHaveBeenCalledWith("/shops/41/booking-settings", bookingSettings);
      expect(api.put).toHaveBeenCalledWith("/shops/41/business-hours", businessHours);
    });

    expect(mockRefreshOwnedShops).toHaveBeenCalled();
    expect(mockSetThemePreset).toHaveBeenCalledWith("forest");
    expect(mockSetDashboardGradient).toHaveBeenCalledWith("ocean");
  });
});
