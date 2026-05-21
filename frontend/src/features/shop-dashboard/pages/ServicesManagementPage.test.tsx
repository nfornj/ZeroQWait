import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ServicesManagementPage from './ServicesManagementPage';
import api from '../../../services/api';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
    useNavigate: () => mockNavigate,
}));

jest.mock('../../../contexts/ShopContext', () => ({
    useShop: () => ({
        shop: {
            id: 7,
            name: 'Wellness Studio',
            slug: 'wellness-studio',
        },
    }),
}));

jest.mock('../../../services/api', () => ({
    __esModule: true,
    default: {
        get: jest.fn(),
        post: jest.fn(),
        put: jest.fn(),
        delete: jest.fn(),
    },
}));

const mockedApi = api as jest.Mocked<typeof api>;

const services = [
    {
        id: 1,
        shop_id: 7,
        name: 'RMT Massage',
        description: '1 hour therapeutic session focused on relaxation and muscle relief.',
        duration_minutes: 60,
        cost: 100,
        currency: 'USD',
        catalog_section: 'popular',
        is_active: true,
    },
    {
        id: 2,
        shop_id: 7,
        name: 'Physiotherapy',
        description: '1 hour session to improve mobility, reduce pain, and restore function.',
        duration_minutes: 60,
        cost: 100,
        currency: 'USD',
        catalog_section: 'popular',
        is_active: true,
    },
    {
        id: 3,
        shop_id: 7,
        name: 'Chiropractic',
        description: 'Hands-on spinal adjustments to improve alignment and well-being.',
        duration_minutes: 45,
        cost: 100,
        currency: 'USD',
        catalog_section: 'popular',
        is_active: true,
    },
    {
        id: 4,
        shop_id: 7,
        name: 'Deep Tissue Massage',
        description: 'Targeted pressure to release chronic muscle tension and improve circulation.',
        duration_minutes: 75,
        cost: 120,
        currency: 'USD',
        catalog_section: 'specialized',
        is_active: true,
    },
];

const setupApi = () => {
    mockedApi.get.mockImplementation((url: string) => {
        if (url === '/shops/7/services') {
            return Promise.resolve({ data: services });
        }
        if (url === '/analytics/services/7?days=30') {
            return Promise.resolve({ data: [{ name: 'RMT Massage', value: 6 }] });
        }
        return Promise.resolve({ data: [] });
    });
    mockedApi.post.mockResolvedValue({ data: {} });
    mockedApi.put.mockResolvedValue({ data: {} });
    mockedApi.delete.mockResolvedValue({ data: {} });
};

beforeEach(() => {
    jest.clearAllMocks();
    setupApi();
});

it('renders the grouped service catalog and insight panel', async () => {
    render(<ServicesManagementPage />);

    expect(await screen.findByRole('heading', { name: 'Service Catalog' })).toBeInTheDocument();
    expect(await screen.findByText('Popular Services')).toBeInTheDocument();
    expect(screen.getByText('Specialized Treatments')).toBeInTheDocument();
    expect(screen.getByText('You have 4 active services')).toBeInTheDocument();
    expect(screen.getByText('Most booked:')).toBeInTheDocument();
    expect(screen.getAllByText('RMT Massage').length).toBeGreaterThan(0);
    expect(screen.getByText('Deep Tissue Massage')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /View insights/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/overview');
});

it('creates a specialized service from the add-service card', async () => {
    render(<ServicesManagementPage />);

    await screen.findByText('Specialized Treatments');
    fireEvent.click(await screen.findByLabelText('Add a new service'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox', { name: /Service Name/i }), { target: { value: 'Acupuncture' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: /Price/i }), { target: { value: '85' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: /Duration/i }), { target: { value: '50' } });
    fireEvent.change(screen.getByRole('textbox', { name: /Description/i }), { target: { value: 'Focused treatment session.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/shops/7/services', {
            name: 'Acupuncture',
            description: 'Focused treatment session.',
            duration_minutes: 50,
            cost: 85,
            catalog_section: 'specialized',
        });
    });
});

it('edits an existing service', async () => {
    render(<ServicesManagementPage />);

    const editButtons = await screen.findAllByRole('button', { name: 'Edit' });
    fireEvent.click(editButtons[0]);

    fireEvent.change(screen.getByRole('textbox', { name: /Service Name/i }), { target: { value: 'RMT Advanced' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
        expect(mockedApi.put).toHaveBeenCalledWith('/shops/7/services/1', {
            name: 'RMT Advanced',
            description: '1 hour therapeutic session focused on relaxation and muscle relief.',
            duration_minutes: 60,
            cost: 100,
            catalog_section: 'popular',
        });
    });
});

it('duplicates a service with copied fields', async () => {
    render(<ServicesManagementPage />);

    const duplicateButtons = await screen.findAllByRole('button', { name: 'Duplicate' });
    fireEvent.click(duplicateButtons[0]);

    await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/shops/7/services', {
            name: 'RMT Massage Copy',
            description: '1 hour therapeutic session focused on relaxation and muscle relief.',
            duration_minutes: 60,
            cost: 100,
            currency: 'USD',
            catalog_section: 'popular',
        });
    });
});

it('confirms deletion before calling the delete endpoint', async () => {
    render(<ServicesManagementPage />);

    const deleteButtons = await screen.findAllByRole('button', { name: 'Delete' });
    fireEvent.click(deleteButtons[0]);

    expect(screen.getByText(/Are you sure you want to delete RMT Massage/)).toBeInTheDocument();
    const allDeleteButtons = screen.getAllByRole('button', { name: 'Delete' });
    fireEvent.click(allDeleteButtons[allDeleteButtons.length - 1]);

    await waitFor(() => {
        expect(mockedApi.delete).toHaveBeenCalledWith('/shops/7/services/1');
    });
});
