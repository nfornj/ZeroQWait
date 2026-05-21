import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import api from '../../../services/api';
import { TextDecoder, TextEncoder } from 'util';

(global as any).TextEncoder = TextEncoder;
(global as any).TextDecoder = TextDecoder;

jest.mock('@mui/x-data-grid', () => ({
    DataGrid: () => <div data-testid="mock-datagrid" />,
    GridActionsCellItem: ({ label, onClick }: any) => <button aria-label={label} onClick={onClick}>{label}</button>,
    GridColDef: {},
}));

import ShopSettingsPage from './ShopSettingsPage';

jest.mock('../../../services/api', () => ({
    __esModule: true,
    default: {
        get: jest.fn(),
        post: jest.fn(),
        put: jest.fn(),
        delete: jest.fn(),
    },
}));

jest.mock('../../../contexts/ThemeContext', () => ({
    useThemeContext: () => ({
        themePreset: 'forest',
        setThemePreset: jest.fn(),
    }),
}));

const mockedApi = api as jest.Mocked<typeof api>;

const mockShop = {
    id: 7,
    name: 'Wing Spa Wellness',
    description: 'Professional massage therapies and holistic treatments.',
    phone: '647 879 2555',
    website: 'www.wingspa.ca',
    email: 'hello@wingspa.ca',
    shop_type: 'Spa & Wellness',
    address: '123 Kingston Rd',
    city: 'Scarborough',
    state: 'ON',
    zip_code: 'M1N 1T7',
    country: 'Canada',
    primary_color: '#2D6A4F',
    secondary_color: '#D8F3DC',
    accent_color: '',
    background_color: '',
    logo_url: '',
    slug: 'wing-spa-wellness',
};

const mockServices = [
    { id: 1, name: 'RMT Massage', duration_minutes: 60, cost: 100, description: 'Therapeutic massage.' },
];

const mockCloseDays = [
    { id: 11, date: '2026-05-19', reason: 'Victoria Day' },
];

const mockAiEnvironment = {
    shop_id: 7,
    subscription_tier: 'premium',
    environment_name: 'Owner AI Environment',
    environment_summary: 'Managed AI environment for shop workflows.',
    operating_mode: 'Managed',
    status_label: 'Healthy',
    uses_default: true,
    can_customize: false,
    capabilities: ['Answer customer FAQs', 'Summarize queue performance'],
    experience_notes: ['Model settings are centrally managed.'],
};

const setupApi = () => {
    mockedApi.get.mockImplementation((url: string) => {
        if (url === '/shops/my-shops') return Promise.resolve({ data: [mockShop] });
        if (url === '/shops/7/services') return Promise.resolve({ data: mockServices });
        if (url === '/shops/7/close-days') return Promise.resolve({ data: mockCloseDays });
        if (url === '/shops/7/llm-settings') return Promise.resolve({ data: mockAiEnvironment });
        return Promise.resolve({ data: {} });
    });
    mockedApi.put.mockResolvedValue({ data: {} });
    mockedApi.post.mockResolvedValue({ data: {} });
    mockedApi.delete.mockResolvedValue({ data: {} });
};

beforeEach(() => {
    jest.clearAllMocks();
    setupApi();
    (global as any).URL.createObjectURL = jest.fn(() => 'blob:test-logo');
});

it('renders and navigates the settings wizard sections', async () => {
    render(<ShopSettingsPage />);

    expect(await screen.findByRole('heading', { name: 'Customize your workspace' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Business Info/i }));
    expect(await screen.findByText('Business Information')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Experience/i }));
    expect(await screen.findByText('Client Experience')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Availability/i }));
    expect(await screen.findByText('Business Hours')).toBeInTheDocument();
});

it('saves branding payload and uploads logo', async () => {
    const { container } = render(<ShopSettingsPage />);

    await screen.findByRole('heading', { name: 'Customize your workspace' });

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['logo-file'], 'logo.png', { type: 'image/png' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByRole('button', { name: 'Save & Continue' }));

    await waitFor(() => {
        expect(mockedApi.put).toHaveBeenCalledWith('/shops/7', expect.objectContaining({
            name: 'Wing Spa Wellness',
            phone: '647 879 2555',
            website: 'www.wingspa.ca',
            email: 'hello@wingspa.ca',
            city: 'Scarborough',
        }));
    });

    await waitFor(() => {
        expect(mockedApi.put).toHaveBeenCalledWith('/shops/7/logo', expect.any(FormData));
    });
});

it('preserves close-day add and service create flows', async () => {
    render(<ShopSettingsPage />);

    await screen.findByRole('heading', { name: 'Customize your workspace' });
    fireEvent.click(screen.getByRole('button', { name: /Availability/i }));
    fireEvent.click(await screen.findByRole('button', { name: 'Add Closed Day' }));

    fireEvent.change(screen.getByRole('textbox', { name: 'Name' }), { target: { value: 'Christmas Day' } });
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2026-12-25' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save & Continue' }));

    await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/shops/7/close-days', null, {
            params: { date_str: '2026-12-25', reason: 'Christmas Day' },
        });
    });

    fireEvent.click(screen.getByRole('button', { name: 'Advanced Tools' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Add Service' }));

    fireEvent.change(screen.getByRole('textbox', { name: 'Name' }), { target: { value: 'Acupuncture' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Cost' }), { target: { value: '95' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Duration (min)' }), { target: { value: '50' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'Description' }), { target: { value: 'Focused treatment' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/shops/7/services', expect.objectContaining({
            name: 'Acupuncture',
            duration_minutes: 50,
            cost: 95,
        }));
    });
});
