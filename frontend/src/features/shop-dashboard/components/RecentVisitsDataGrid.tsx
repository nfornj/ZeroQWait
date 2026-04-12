import React, { useEffect, useState } from 'react';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useShop } from '../../../contexts/ShopContext';
import axios from 'axios';
import { CircularProgress, Typography, Box } from '@mui/material';

export default function RecentVisitsDataGrid() {
    const { shop } = useShop();
    const [rows, setRows] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchHistory = async () => {
            if (!shop) return;
            try {
                setLoading(true);
                const token = localStorage.getItem('token');
                const headers = { Authorization: `Bearer ${token}` };

                // Fetch all queues for the shop to get items
                // Since we don't have a direct "all-items" endpoint yet, we fetch all queues and aggregate
                const queuesRes = await axios.get(`/queues/shop/${shop.id}/all`, { headers });
                const allQueues = queuesRes.data;

                let allItems: any[] = [];
                allQueues.forEach((q: any) => {
                    if (q.queue_items) {
                        const completed = q.queue_items.filter((i: any) => i.status === 'completed');
                        allItems = [...allItems, ...completed];
                    }
                });

                // Sort by completed_at desc
                allItems.sort((a, b) => {
                    return new Date(b.completed_at).getTime() - new Date(a.completed_at).getTime();
                });

                setRows(allItems);
            } catch (err) {
                console.error("Failed to fetch visit history", err);
            } finally {
                setLoading(false);
            }
        };

        fetchHistory();
    }, [shop]);

    const getRowFromGetterArgs = (firstArg: any, secondArg: any) => {
        if (secondArg && typeof secondArg === 'object') return secondArg;
        if (firstArg && typeof firstArg === 'object' && 'row' in firstArg) return firstArg.row;
        return {};
    };

    const columns: GridColDef[] = [
        { field: 'customer_name', headerName: 'Customer', flex: 1.5, minWidth: 150 },
        {
            field: 'notes',
            headerName: 'Service',
            flex: 1,
            minWidth: 120,
            valueGetter: (params, row) => {
                const safeRow = getRowFromGetterArgs(params, row);
                return safeRow.notes || 'General Service';
            }
        },
        {
            field: 'assigned_employee',
            headerName: 'Served By',
            flex: 1,
            valueGetter: (params, row) => {
                const safeRow = getRowFromGetterArgs(params, row);
                return safeRow.assigned_employee?.username || 'Shop Owner';
            }
        },
        {
            field: 'cost',
            headerName: 'Paid',
            type: 'number',
            width: 80,
            valueGetter: (params, row) => {
                const safeRow = getRowFromGetterArgs(params, row);
                return safeRow.service_cost || 0;
            },
            valueFormatter: (value: any) => {
                const numeric = typeof value === 'object' && value?.value !== undefined ? value.value : value;
                return `$${Number(numeric || 0).toFixed(2)}`;
            },
        },
        {
            field: 'completed_at',
            headerName: 'Date',
            flex: 1,
            minWidth: 120,
            valueFormatter: (value: any) => {
                const dateValue = typeof value === 'object' && value?.value !== undefined ? value.value : value;
                return dateValue ? new Date(dateValue).toLocaleDateString() : '-';
            },
        },
        {
            field: 'duration',
            headerName: 'Duration',
            flex: 0.8,
            valueGetter: (params, row) => {
                const safeRow = getRowFromGetterArgs(params, row);
                if (!safeRow.service_started_at || !safeRow.completed_at) return '-';
                const start = new Date(safeRow.service_started_at).getTime();
                const end = new Date(safeRow.completed_at).getTime();
                const minutes = Math.round((end - start) / 60000);
                return `${minutes} min`;
            }
        }
    ];

    if (loading) {
        return <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>;
    }

    if (rows.length === 0) {
        return (
            <Box sx={{ p: 4, textAlign: 'center' }}>
                <Typography color="text.secondary">No recent visits found.</Typography>
            </Box>
        );
    }

    return (
        <DataGrid
            autoHeight
            checkboxSelection
            rows={rows}
            columns={columns}
            getRowId={(row) => row.id}
            getRowClassName={(params) =>
                params.indexRelativeToCurrentPage % 2 === 0 ? 'even' : 'odd'
            }
            initialState={{
                pagination: { paginationModel: { pageSize: 10 } },
            }}
            pageSizeOptions={[10, 20]}
            disableColumnResize
            density="compact"
            sx={{
                bgcolor: 'var(--owner-glass-bg)',
                backdropFilter: 'blur(20px)',
                border: '1px solid var(--owner-glass-border)',
                boxShadow: 'var(--owner-glass-shadow)',
                '& .MuiDataGrid-columnHeaders': {
                    bgcolor: 'rgba(255,255,255,0.05)',
                    borderBottom: '1px solid var(--owner-glass-border)',
                },
                '& .MuiDataGrid-footerContainer': {
                    borderTop: '1px solid var(--owner-glass-border)',
                },
            }}
            slotProps={{
                filterPanel: {
                    filterFormProps: {
                        logicOperatorInputProps: { variant: 'outlined', size: 'small' },
                        columnInputProps: { variant: 'outlined', size: 'small', sx: { mt: 'auto' } },
                        operatorInputProps: { variant: 'outlined', size: 'small', sx: { mt: 'auto' } },
                        valueInputProps: { InputComponentProps: { variant: 'outlined', size: 'small' } },
                    },
                },
            }}
        />
    );
}
