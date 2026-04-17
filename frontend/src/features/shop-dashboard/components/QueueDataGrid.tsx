import React from 'react';
import { DataGrid, GridColDef, GridActionsCellItem, GridRenderCellParams, GridToolbar } from '@mui/x-data-grid';
import { Chip } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RestartAltIcon from '@mui/icons-material/RestartAlt';

interface Queue {
    id: number;
    name: string;
    is_active: boolean;
    shop_id: number;
}

interface QueueDataGridProps {
    rows: Queue[];
    onEdit: (queue: Queue) => void;
    onDelete?: (id: number) => void;
    onReset?: (id: number) => void;
    onRowClick?: (queue: Queue) => void;
}

export default function QueueDataGrid({ rows, onEdit, onDelete, onReset, onRowClick }: QueueDataGridProps) {
    const columns: GridColDef<Queue>[] = [
        {
            field: 'name',
            headerName: 'Queue Name',
            flex: 1,
            minWidth: 150,
        },
        {
            field: 'id',
            headerName: 'Queue ID',
            width: 100,
        },
        {
            field: 'is_active',
            headerName: 'Status',
            width: 120,
            renderCell: (params: GridRenderCellParams<Queue>) => (
                <Chip
                    label={params.value ? 'Active' : 'Inactive'}
                    color={params.value ? 'success' : 'default'}
                    size="small"
                    variant="outlined"
                />
            ),
        },
        {
            field: 'actions',
            headerName: 'Actions',
            type: 'actions',
            width: 180,
            getActions: (params) => {
                const actions = [
                    <GridActionsCellItem
                        icon={<EditIcon />}
                        label="Edit"
                        onClick={() => onEdit(params.row)}
                        showInMenu={false}
                    />,
                ];
                if (onReset) {
                    actions.push(
                        <GridActionsCellItem
                            icon={<RestartAltIcon />}
                            label="Reset data"
                            onClick={() => onReset(params.row.id)}
                            showInMenu={false}
                        />
                    );
                }
                if (onDelete) {
                    actions.push(
                        <GridActionsCellItem
                            icon={<DeleteIcon />}
                            label="Delete queue"
                            onClick={() => onDelete(params.row.id)}
                            showInMenu={false}
                        />
                    );
                }
                return actions;
            },
        },
    ];

    return (
        <DataGrid
            autoHeight
            rows={rows}
            columns={columns}
            onRowClick={(params) => onRowClick?.(params.row as Queue)}
            slots={{ toolbar: GridToolbar }}
            slotProps={{
                toolbar: {
                    showQuickFilter: true,
                    quickFilterProps: { debounceMs: 250 }
                }
            }}
            initialState={{
                pagination: { paginationModel: { pageSize: 10 } },
            }}
            pageSizeOptions={[5, 10, 20]}
            checkboxSelection
            disableRowSelectionOnClick
            density="compact"
            sx={{
                border: 0,
                backgroundColor: 'background.paper',
                '& .MuiDataGrid-columnHeaders': {
                    bgcolor: 'background.default',
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                },
                '& .MuiDataGrid-cell:focus, & .MuiDataGrid-columnHeader:focus': {
                    outline: 'none',
                },
                '& .MuiDataGrid-toolbarContainer': {
                    p: 1,
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                },
                cursor: onRowClick ? 'pointer' : 'default',
            }}
        />
    );
}
