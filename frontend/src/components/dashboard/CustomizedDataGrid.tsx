import * as React from 'react';
import { DataGrid, GridColDef, GridRowsProp } from '@mui/x-data-grid';
import Chip from '@mui/material/Chip';
import { SparkLineChart } from '@mui/x-charts/SparkLineChart';

// Sample data - in a real app this would come from the API
const columns: GridColDef[] = [
    { field: 'pageTitle', headerName: 'Service', flex: 1.5, minWidth: 200 },
    {
        field: 'status',
        headerName: 'Status',
        flex: 0.5,
        minWidth: 80,
        renderCell: (params) => {
            const color = params.value === 'Online' ? 'success' : 'default';
            return <Chip label={params.value} color={color} size="small" variant="outlined" />;
        },
    },
    {
        field: 'users',
        headerName: 'Customers',
        headerAlign: 'right',
        align: 'right',
        flex: 1,
        minWidth: 80,
    },
    {
        field: 'eventCount',
        headerName: 'Total Services',
        headerAlign: 'right',
        align: 'right',
        flex: 1,
        minWidth: 100,
    },
    {
        field: 'viewsPerUser',
        headerName: 'Avg. Time (min)',
        headerAlign: 'right',
        align: 'right',
        flex: 1,
        minWidth: 120,
    },
    {
        field: 'averageTime',
        headerName: 'Wait Time',
        headerAlign: 'right',
        align: 'right',
        flex: 1,
        minWidth: 100,
    },
    {
        field: 'conversions',
        headerName: 'Daily Trend',
        flex: 1,
        minWidth: 150,
        renderCell: (params) => (
            <SparkLineChart
                data={params.value}
                width={100}
                height={30}
                plotType="bar"
                showHighlight={true}
                showTooltip={true}
                colors={['hsl(210, 98%, 42%)']}
                sx={{ p: 1 }}
            />
        ),
    },
];

const rows: GridRowsProp = [
    {
        id: 1,
        pageTitle: 'Men\'s Haircut',
        status: 'Online',
        users: 2124,
        eventCount: 8345,
        viewsPerUser: 25,
        averageTime: '15m',
        conversions: [4, 6, 8, 4, 2, 7, 3, 5, 4, 9],
    },
    {
        id: 2,
        pageTitle: 'Beard Trim',
        status: 'Online',
        users: 1722,
        eventCount: 5653,
        viewsPerUser: 15,
        averageTime: '5m',
        conversions: [2, 4, 3, 1, 5, 2, 4, 6, 3, 4],
    },
    {
        id: 3,
        pageTitle: 'Full Shave',
        status: 'Offline',
        users: 582,
        eventCount: 3455,
        viewsPerUser: 30,
        averageTime: '10m',
        conversions: [1, 2, 1, 3, 1, 2, 1, 2, 1, 2],
    },
    {
        id: 4,
        pageTitle: 'Kids Haircut',
        status: 'Online',
        users: 962,
        eventCount: 1125,
        viewsPerUser: 20,
        averageTime: '12m',
        conversions: [3, 4, 3, 5, 4, 3, 5, 4, 3, 5],
    },
    {
        id: 5,
        pageTitle: 'Hair Coloring',
        status: 'Offline',
        users: 1422,
        eventCount: 365,
        viewsPerUser: 60,
        averageTime: '5m',
        conversions: [1, 1, 2, 1, 1, 1, 1, 1, 1, 1],
    },
    {
        id: 6,
        pageTitle: 'Facial',
        status: 'Online',
        users: 500,
        eventCount: 450,
        viewsPerUser: 45,
        averageTime: '2m',
        conversions: [2, 2, 3, 2, 2, 3, 2, 2, 3, 2],
    },
];

export default function CustomizedDataGrid() {
    return (
        <DataGrid
            autoHeight
            checkboxSelection
            rows={rows}
            columns={columns}
            getRowClassName={(params) =>
                params.indexRelativeToCurrentPage % 2 === 0 ? 'even' : 'odd'
            }
            initialState={{
                pagination: { paginationModel: { pageSize: 5 } },
            }}
            pageSizeOptions={[5, 10, 20]}
            disableColumnResize
            density="compact"
            slotProps={{
                filterPanel: {
                    filterFormProps: {
                        logicOperatorInputProps: {
                            variant: 'outlined',
                            size: 'small',
                        },
                        columnInputProps: {
                            variant: 'outlined',
                            size: 'small',
                            sx: { mt: 'auto' },
                        },
                        operatorInputProps: {
                            variant: 'outlined',
                            size: 'small',
                            sx: { mt: 'auto' },
                        },
                        valueInputProps: {
                            InputComponentProps: {
                                variant: 'outlined',
                                size: 'small',
                            },
                        },
                    },
                },
            }}
        />
    );
}
