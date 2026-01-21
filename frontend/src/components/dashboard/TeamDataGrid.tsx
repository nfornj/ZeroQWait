import React from 'react';
import { DataGrid, GridColDef, GridRenderCellParams, GridActionsCellItem } from '@mui/x-data-grid';
import { Chip, IconButton } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import RestoreIcon from '@mui/icons-material/Restore';

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

interface TeamDataGridProps {
    rows: Employee[];
    onDelete: (id: number) => void;
    onReactivate: (id: number) => void;
}

export default function TeamDataGrid({ rows, onDelete, onReactivate }: TeamDataGridProps) {
    const columns: GridColDef<Employee>[] = [
        {
            field: 'username',
            headerName: 'Username',
            flex: 1,
            minWidth: 150,
            valueGetter: (value, row) => row.user.username,
        },
        {
            field: 'email',
            headerName: 'Email',
            flex: 1.5,
            minWidth: 200,
            valueGetter: (value, row) => row.user.email,
        },
        {
            field: 'role',
            headerName: 'Role',
            flex: 1,
            minWidth: 120,
            valueGetter: (value, row) => row.user.role.charAt(0).toUpperCase() + row.user.role.slice(1),
        },
        {
            field: 'status',
            headerName: 'Status',
            width: 120,
            renderCell: (params: GridRenderCellParams<Employee>) => (
                <Chip
                    label={params.row.is_active ? 'Active' : 'Inactive'}
                    color={params.row.is_active ? 'success' : 'default'}
                    size="small"
                    variant="outlined"
                />
            ),
        },
        {
            field: 'created_at',
            headerName: 'Added On',
            width: 150,
            valueFormatter: (value) => new Date(value).toLocaleDateString(),
        },
        {
            field: 'actions',
            headerName: 'Actions',
            type: 'actions',
            width: 100,
            getActions: (params) => {
                if (params.row.is_active) {
                    return [
                        <GridActionsCellItem
                            icon={<DeleteIcon color="error" />}
                            label="Remove"
                            onClick={() => onDelete(params.row.user.id)}
                        />,
                    ];
                } else {
                    return [
                        <GridActionsCellItem
                            icon={<RestoreIcon color="primary" />}
                            label="Reactivate"
                            onClick={() => onReactivate(params.row.user.id)}
                        />,
                    ];
                }
            },
        },
    ];

    return (
        <DataGrid
            autoHeight
            checkboxSelection
            disableRowSelectionOnClick
            rows={rows}
            columns={columns}
            getRowId={(row) => row.user.id}
            getRowClassName={(params) =>
                params.indexRelativeToCurrentPage % 2 === 0 ? 'even' : 'odd'
            }
            initialState={{
                pagination: { paginationModel: { pageSize: 10 } },
            }}
            pageSizeOptions={[10, 20, 50]}
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
