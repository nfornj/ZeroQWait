import React, { useState, useEffect } from 'react';
import api from '../../../services/api';
import {
    Box,
    Typography,
    Button,
    Paper,
    Card,
    CardContent,
    Grid,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    IconButton,
    Chip,
    Alert,
    CircularProgress,
    Tabs,
    Tab
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import RestoreIcon from '@mui/icons-material/Restore';
import PeopleIcon from '@mui/icons-material/People';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import PaymentsIcon from '@mui/icons-material/Payments';
import DownloadIcon from '@mui/icons-material/Download';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import AttendanceCalendar from '../components/AttendanceCalendar';
import TeamDataGrid from '../components/TeamDataGrid';
import Header from '../components/Header';


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
        username: '',
        email: '',
        password: '',
        role: 'employee'
    });
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);
    const [checkingUsername, setCheckingUsername] = useState(false);
    const [emailAvailable, setEmailAvailable] = useState<boolean | null>(null);
    const [checkingEmail, setCheckingEmail] = useState(false);
    const [currentTab, setCurrentTab] = useState(0);
    const [shifts, setShifts] = useState<any[]>([]);
    const [shiftsLoading, setShiftsLoading] = useState(false);
    const [selectedEmployeeFilter, setSelectedEmployeeFilter] = useState<number | null>(null);
    const [removeConfirmId, setRemoveConfirmId] = useState<number | null>(null);
    const [payslips, setPayslips] = useState<any[]>([]);
    const [payrollLoading, setPayrollLoading] = useState(false);
    const [draftingPayroll, setDraftingPayroll] = useState(false);

    const fetchEmployees = React.useCallback(async (id: number) => {
        try {
            const response = await api.get(`/shops/${id}/employees`);
            setEmployees(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load employees');
        }
    }, []);

    const fetchShopAndEmployees = React.useCallback(async () => {
        try {
            // Get shop ID first
            const shopResponse = await api.get(`/shops/my-shops`);

            if (shopResponse.data.length === 0) {
                setError('No shop found. Please create a shop first.');
                setLoading(false);
                return;
            }

            const shop = shopResponse.data[0];
            setShopId(shop.id);

            // Fetch employees
            await fetchEmployees(shop.id);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load data');
        } finally {
            setLoading(false);
        }
    }, [fetchEmployees]);

    const fetchShifts = React.useCallback(async (id: number, employeeId: number | null = null) => {
        setShiftsLoading(true);
        try {
            let url = `/shops/${id}/employee-shifts?months=3`;
            if (employeeId) {
                url += `&employee_id=${employeeId}`;
            }
            const response = await api.get(url);
            setShifts(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load attendance data');
        } finally {
            setShiftsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchShopAndEmployees();
    }, [fetchShopAndEmployees]);

    useEffect(() => {
        // Fetch shifts when switching to attendance tab
        if (currentTab === 1 && shopId) {
            fetchShifts(shopId, selectedEmployeeFilter);
        }
    }, [currentTab, shopId, selectedEmployeeFilter, fetchShifts]);

    const fetchPayslips = React.useCallback(async (id: number) => {
        setPayrollLoading(true);
        try {
            const res = await api.get(`/payroll/shop/${id}/payslips?limit=100`);
            setPayslips(res.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load payslips');
        } finally {
            setPayrollLoading(false);
        }
    }, []);

    useEffect(() => {
        if (currentTab === 2 && shopId) {
            fetchPayslips(shopId);
        }
    }, [currentTab, shopId, fetchPayslips]);

    const handleDraftPeriod = async () => {
        if (!shopId) return;
        setDraftingPayroll(true);
        setError(null);
        try {
            const today = new Date();
            const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
            const period_start = firstOfMonth.toISOString().split('T')[0];
            const res = await api.post(`/payroll/shop/${shopId}/draft-period`, {
                period_start,
                regular_hours_per_employee: 80
            });
            const data = res.data;
            if (data.created?.length > 0) {
                setSuccess(`Drafted ${data.created.length} payslip(s) for the period ${data.period_start} – ${data.period_end}.`);
            } else if (data.skipped?.length > 0) {
                setSuccess(`All employees already have payslips for this period (${data.skipped.length} skipped).`);
            } else if (data.errors?.length > 0) {
                setError('Some payslips could not be drafted: ' + data.errors.map((e: any) => e.employee).join(', '));
            } else {
                setError('No payroll profiles found. Please set up profiles for employees first.');
            }
            await fetchPayslips(shopId);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to draft payroll');
        } finally {
            setDraftingPayroll(false);
        }
    };

    const handleDownloadPayslipPdf = async (payslipId: number, employeeName: string, period: string) => {
        if (!shopId) return;
        try {
            const res = await api.get(`/payroll/shop/${shopId}/payslips/${payslipId}/pdf`, {
                responseType: 'blob'
            });
            const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
            const a = document.createElement('a');
            a.href = url;
            a.download = `payslip_${employeeName.replace(/\s+/g, '_')}_${period}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err: any) {
            setError('Failed to download PDF');
        }
    };

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
            } catch (err) {
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
            // Basic email validation
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!formData.email || !emailRegex.test(formData.email)) {
                setEmailAvailable(null);
                return;
            }

            setCheckingEmail(true);
            try {
                const response = await api.get(`/check-email/${encodeURIComponent(formData.email)}`);
                setEmailAvailable(response.data.available);
            } catch (err) {
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

            setSuccess('Employee added successfully!');
            setFormData({ username: '', email: '', password: '', role: 'employee' });
            setOpenDialog(false);

            // Refresh employee list
            await fetchEmployees(shopId);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to add employee');
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
            setSuccess('Employee removed successfully!');
            setRemoveConfirmId(null);
            await fetchEmployees(shopId);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to remove employee');
            setRemoveConfirmId(null);
        }
    };

    const handleReactivateEmployee = async (employeeId: number) => {
        if (!shopId) return;

        try {
            await api.put(`/shops/${shopId}/employees/${employeeId}/reactivate`, {});
            setSuccess('Employee reactivated successfully!');
            await fetchEmployees(shopId);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to reactivate employee');
        }
    };

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setCurrentTab(newValue);
    };

    const handleEmployeeFilterChange = (employeeId: number | null) => {
        setSelectedEmployeeFilter(employeeId);
    };

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
            <Header />

            <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid size={{ xs: 12, md: 8 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3 }}>
                        <CardContent>
                            <Box display="flex" justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }} flexDirection={{ xs: 'column', md: 'row' }} gap={2}>
                                <Box>
                                    <Typography variant="h5" sx={{ mb: 0.5, fontWeight: 700 }}>
                                        Team Management
                                    </Typography>
                                    <Typography color="text.secondary">
                                        Manage employees, assign roles, and review attendance in one place.
                                    </Typography>
                                </Box>
                                {currentTab === 0 && (
                                    <Button
                                        variant="contained"
                                        startIcon={<AddIcon />}
                                        onClick={() => setOpenDialog(true)}
                                        disabled={!shopId}
                                    >
                                        Add Employee
                                    </Button>
                                )}
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, md: 4 }}>
                    <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
                        <CardContent>
                            <Typography variant="body2" color="text.secondary">Active Team Members</Typography>
                            <Typography variant="h4" sx={{ fontWeight: 700, mt: 0.5 }}>
                                {employees.filter((e) => e.is_active).length}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {error && <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>{success}</Alert>}

            <Paper variant="outlined" sx={{ mb: 3, borderRadius: 3, overflow: 'hidden' }}>
                <Tabs value={currentTab} onChange={handleTabChange} aria-label="team management tabs">
                    <Tab label="Employee List" icon={<PeopleIcon />} iconPosition="start" />
                    <Tab label="Attendance Calendar" icon={<CalendarMonthIcon />} iconPosition="start" />
                    <Tab label="Payroll" icon={<PaymentsIcon />} iconPosition="start" />
                </Tabs>
            </Paper>

            {currentTab === 0 && (
                <Paper variant="outlined" sx={{ width: '100%', overflow: 'hidden', borderRadius: 3 }}>
                    <TeamDataGrid
                        rows={employees}
                        onDelete={handleRemoveEmployee}
                        onReactivate={handleReactivateEmployee}
                    />
                </Paper>
            )}

            {currentTab === 1 && (
                <Box>
                    {shiftsLoading ? (
                        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                            <CircularProgress />
                        </Box>
                    ) : (
                        <AttendanceCalendar
                            shifts={shifts}
                            employees={employees.filter(emp => emp.is_active).map(emp => ({
                                id: emp.user.id,
                                username: emp.user.username
                            }))}
                            onEmployeeChange={handleEmployeeFilterChange}
                        />
                    )}
                </Box>
            )}

            {currentTab === 2 && (
                <Box>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                        <Typography variant="h6" fontWeight={700}>Payroll — 15-Day Periods</Typography>
                        <Button
                            variant="contained"
                            startIcon={<PaymentsIcon />}
                            onClick={handleDraftPeriod}
                            disabled={draftingPayroll}
                        >
                            {draftingPayroll ? <CircularProgress size={20} /> : 'Draft 15-Day Payroll'}
                        </Button>
                    </Box>
                    {payrollLoading ? (
                        <Box display="flex" justifyContent="center" py={6}><CircularProgress /></Box>
                    ) : payslips.length === 0 ? (
                        <Paper variant="outlined" sx={{ p: 4, borderRadius: 3, textAlign: 'center' }}>
                            <Typography color="text.secondary">No payslips yet. Click "Draft 15-Day Payroll" to generate payslips for all active employees.</Typography>
                        </Paper>
                    ) : (
                        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3 }}>
                            <Table size="small">
                                <TableHead>
                                    <TableRow sx={{ bgcolor: 'action.hover' }}>
                                        <TableCell><strong>Employee</strong></TableCell>
                                        <TableCell><strong>Period</strong></TableCell>
                                        <TableCell align="right"><strong>Gross Pay</strong></TableCell>
                                        <TableCell align="right"><strong>CPP</strong></TableCell>
                                        <TableCell align="right"><strong>EI</strong></TableCell>
                                        <TableCell align="right"><strong>Fed Tax</strong></TableCell>
                                        <TableCell align="right"><strong>Prov Tax</strong></TableCell>
                                        <TableCell align="right"><strong>Net Pay</strong></TableCell>
                                        <TableCell align="center"><strong>Status</strong></TableCell>
                                        <TableCell align="center"><strong>PDF</strong></TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {payslips.map((slip) => (
                                        <TableRow key={slip.id} hover>
                                            <TableCell>{slip.employee_name || '—'}</TableCell>
                                            <TableCell sx={{ whiteSpace: 'nowrap', fontSize: '0.8rem' }}>
                                                {slip.period_start} – {slip.period_end}
                                            </TableCell>
                                            <TableCell align="right">${parseFloat(slip.gross_pay || 0).toFixed(2)}</TableCell>
                                            <TableCell align="right">${parseFloat(slip.cpp_deduction || 0).toFixed(2)}</TableCell>
                                            <TableCell align="right">${parseFloat(slip.ei_deduction || 0).toFixed(2)}</TableCell>
                                            <TableCell align="right">${parseFloat(slip.fed_tax || 0).toFixed(2)}</TableCell>
                                            <TableCell align="right">${parseFloat(slip.prov_tax || 0).toFixed(2)}</TableCell>
                                            <TableCell align="right" sx={{ fontWeight: 700, color: 'success.main' }}>
                                                ${parseFloat(slip.net_pay || 0).toFixed(2)}
                                            </TableCell>
                                            <TableCell align="center">
                                                <Chip
                                                    label={slip.status || 'draft'}
                                                    size="small"
                                                    color={slip.status === 'approved' ? 'success' : slip.status === 'paid' ? 'primary' : 'default'}
                                                />
                                            </TableCell>
                                            <TableCell align="center">
                                                <IconButton
                                                    size="small"
                                                    title="Download PDF"
                                                    onClick={() => handleDownloadPayslipPdf(slip.id, slip.employee_name || 'employee', slip.period_start)}
                                                >
                                                    <DownloadIcon fontSize="small" />
                                                </IconButton>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                </Box>
            )}

            {/* Add Employee Dialog */}
            <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Add New Employee</DialogTitle>
                <DialogContent>
                    <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <TextField
                            label="Username"
                            value={formData.username}
                            onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                            fullWidth
                            required
                            error={usernameAvailable === false}
                            helperText={
                                checkingUsername
                                    ? 'Checking availability...'
                                    : usernameAvailable === false
                                        ? 'Username already taken'
                                        : usernameAvailable === true
                                            ? '✓ Username available'
                                            : 'Employee will use this to log in'
                            }
                            InputProps={{
                                endAdornment: checkingUsername ? <CircularProgress size={20} /> : null
                            }}
                        />
                        <TextField
                            label="Email"
                            type="email"
                            value={formData.email}
                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                            fullWidth
                            required
                            error={emailAvailable === false}
                            helperText={
                                checkingEmail
                                    ? 'Checking availability...'
                                    : emailAvailable === false
                                        ? 'Email already registered'
                                        : emailAvailable === true
                                            ? '✓ Email available'
                                            : ''
                            }
                            InputProps={{
                                endAdornment: checkingEmail ? <CircularProgress size={20} /> : null
                            }}
                        />
                        <TextField
                            label="Password"
                            type="password"
                            value={formData.password}
                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                            fullWidth
                            required
                            helperText="Temporary password - employee can change it later"
                        />
                        <TextField
                            select
                            label="Role"
                            value={formData.role}
                            onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                            fullWidth
                            required
                            SelectProps={{
                                native: true,
                            }}
                        >
                            <option value="employee">Employee</option>
                            <option value="manager">Manager</option>
                        </TextField>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpenDialog(false)} disabled={submitting}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleAddEmployee}
                        variant="contained"
                        disabled={submitting || !formData.username || !formData.email || !formData.password || usernameAvailable === false || emailAvailable === false || checkingUsername || checkingEmail}
                    >
                        {submitting ? <CircularProgress size={24} /> : 'Add Employee'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Remove Employee Confirmation Dialog */}
            <Dialog open={removeConfirmId !== null} onClose={() => setRemoveConfirmId(null)}>
                <DialogTitle>Remove Employee</DialogTitle>
                <DialogContent>
                    <Typography>Are you sure you want to remove this employee? This action cannot be undone.</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRemoveConfirmId(null)}>Cancel</Button>
                    <Button variant="contained" color="error" onClick={confirmRemoveEmployee}>Remove</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default EmployeeManagementPage;
