import { expect, test, type Page, type Route } from "@playwright/test";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const authToken =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." +
  Buffer.from(JSON.stringify({ sub: "owner_e2e", exp: 4_102_444_800 })).toString("base64url") +
  ".test-signature";

const owner = {
  id: 7,
  username: "owner_e2e",
  email: "owner@example.com",
  role: "shop_owner",
  is_active: true,
};

const initialShop = {
  id: 41,
  owner_id: owner.id,
  name: "Wing Spa Wellness",
  description: "Professional massage therapies and holistic treatments.",
  shop_type: "Spa & Wellness",
  address: "123 Kingston Rd, Scarborough, ON M1N 1T7",
  city: "Scarborough",
  state: "ON",
  zip_code: "M1N 1T7",
  country: "Canada",
  phone: "647 879 2555",
  email: "hello@wingspa.ca",
  website: "www.wingspa.ca",
  average_service_time: 30,
  logo_url: "",
  primary_color: "#2D6A4F",
  secondary_color: "#D8F3DC",
  accent_color: "",
  background_color: "",
  dashboard_gradient: "ocean",
  ai_agent_name: null,
  slug: "wing-spa-wellness",
  tagline: "Relax. Restore. Rebalance.",
  tax_id: "BN-123",
  timezone: "America/Toronto",
  instagram: "@wingspawellness",
  whatsapp: "+1 647 879 2555",
  latitude: null,
  longitude: null,
  is_active: true,
  created_at: "2026-05-01T12:00:00Z",
  odoo_company_id: null,
  telegram_chat_id: null,
  telegram_notifications_enabled: false,
};

const initialBookingSettings = {
  bookingEnabled: true,
  requireConfirmation: false,
  allowRescheduling: true,
  allowCancellations: true,
  bookingNotice: "24",
  reminderPreferences: "email",
  reminderTime: "24",
  followUp: false,
  waitingList: false,
  autoConfirm: false,
};

const initialBusinessHours = DAYS.map((day) => ({
  day,
  isOpen: day !== "Sunday",
  openTime: day === "Saturday" ? "10:00" : "09:00",
  closeTime: day === "Sunday" ? "18:00" : "19:00",
}));

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installSettingsApiMocks(page: Page) {
  let shop = { ...initialShop };
  let bookingSettings = { ...initialBookingSettings };
  let businessHours = initialBusinessHours.map((item) => ({ ...item }));
  const closeDays: Array<Record<string, unknown>> = [];
  const saved = {
    shopPayloads: [] as Array<Record<string, unknown>>,
    bookingPayloads: [] as Array<Record<string, unknown>>,
    businessHourPayloads: [] as Array<Array<Record<string, unknown>>>,
    closeDayPayloads: [] as Array<Record<string, unknown>>,
  };

  await page.route("**/users/me", (route) => json(route, owner));
  await page.route("**/api/shops/my-shops", (route) => json(route, [shop]));
  await page.route("**/api/shops/41/services", (route) => json(route, []));
  await page.route("**/api/shops/41/llm-settings", (route) =>
    json(route, {
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
    }),
  );
  await page.route("**/api/shops/41/booking-settings", async (route, request) => {
    if (request.method() === "PUT") {
      bookingSettings = await request.postDataJSON();
      saved.bookingPayloads.push(bookingSettings);
    }
    await json(route, bookingSettings);
  });
  await page.route("**/api/shops/41/business-hours", async (route, request) => {
    if (request.method() === "PUT") {
      businessHours = await request.postDataJSON();
      saved.businessHourPayloads.push(businessHours);
    }
    await json(route, businessHours);
  });
  await page.route("**/api/shops/41/close-days", async (route, request) => {
    if (request.method() === "POST") {
      const payload = await request.postDataJSON();
      saved.closeDayPayloads.push(payload);
      closeDays.push({
        id: closeDays.length + 1,
        date: payload.date,
        name: payload.name,
        reason: payload.reason,
        notes: payload.notes,
        repeatYearly: payload.repeatYearly,
      });
    }
    await json(route, closeDays);
  });
  await page.route("**/api/shops/41", async (route, request) => {
    if (request.method() === "PUT") {
      const payload = await request.postDataJSON();
      saved.shopPayloads.push(payload);
      shop = { ...shop, ...payload };
    }
    await json(route, shop);
  });

  return saved;
}

test("settings page persists profile, booking preferences, business hours, and closed days", async ({ page }) => {
  const saved = await installSettingsApiMocks(page);

  await page.addInitScript((token) => localStorage.setItem("token", token), authToken);
  await page.goto("/settings");

  await expect(page.getByRole("heading", { name: "Customize your workspace" })).toBeVisible();
  await expect(page.getByPlaceholder("Your shop name").first()).toHaveValue("Wing Spa Wellness");

  await page.getByPlaceholder("Your shop name").first().fill("Wing Spa Wellness E2E");
  await page.getByRole("button", { name: "Sunset" }).last().click();
  await page.getByRole("button", { name: "Save & Continue" }).click();

  await expect.poll(() => saved.shopPayloads.length).toBeGreaterThan(0);
  expect(saved.shopPayloads.at(-1)).toMatchObject({
    name: "Wing Spa Wellness E2E",
    dashboard_gradient: "sunset",
    shop_type: "Spa & Wellness",
  });

  await expect(page.getByRole("heading", { name: "Business Information" })).toBeVisible();
  await page.getByPlaceholder("Optional").fill("BN-999");
  await page.getByRole("button", { name: "Save & Continue" }).click();

  await expect.poll(() => saved.shopPayloads.length).toBeGreaterThan(1);
  expect(saved.shopPayloads.at(-1)).toMatchObject({
    tax_id: "BN-999",
    timezone: "America/Toronto",
  });

  await expect(page.getByRole("heading", { name: "Client Experience" })).toBeVisible();
  await page.getByRole("switch", { name: "Require Confirmation" }).click();
  const bookingSaveCount = saved.bookingPayloads.length;
  await page.getByRole("button", { name: "Save & Continue" }).click();

  await expect.poll(() => saved.bookingPayloads.length).toBeGreaterThan(bookingSaveCount);
  expect(saved.bookingPayloads.at(-1)).toMatchObject({
    requireConfirmation: true,
    bookingNotice: "24",
  });

  await expect(page.getByRole("heading", { name: "Business Hours" })).toBeVisible();
  await page.locator('input[type="time"]').nth(1).fill("20:30");
  const businessHourSaveCount = saved.businessHourPayloads.length;
  await page.getByRole("button", { name: "Save Settings" }).click();

  await expect.poll(() => saved.businessHourPayloads.length).toBeGreaterThan(businessHourSaveCount);
  expect(saved.businessHourPayloads.at(-1)?.[0]).toMatchObject({
    day: "Monday",
    closeTime: "20:30",
  });

  await page.getByRole("button", { name: "Add Closed Day" }).click();
  await page.getByPlaceholder("e.g. Christmas, Renovation Day").fill("Christmas Day");
  await page.locator('input[type="date"]').fill("2026-12-25");
  await page.getByRole("switch", { name: "Repeat Yearly" }).click();
  await page.getByPlaceholder("Add any additional notes...").fill("We wish you a wonderful holiday.");
  await page.getByRole("button", { name: "Mark as Closed" }).click();

  await expect.poll(() => saved.closeDayPayloads.length).toBe(1);
  expect(saved.closeDayPayloads[0]).toEqual({
    date: "2026-12-25",
    name: "Christmas Day",
    reason: "Christmas Day",
    notes: "We wish you a wonderful holiday.",
    repeatYearly: true,
  });
  await expect(page.getByText("Christmas Day")).toBeVisible();
});
