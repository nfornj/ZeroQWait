import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    Box,
    Typography,
    Button,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
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
import AttendanceCalendar from '../components/AttendanceCalendar';


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
        password: ''
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

    const fetchEmployees = React.useCallback(async (id: number, token: string) => {
        try {
            const response = await axios.get(`/shops/${id}/employees`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setEmployees(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load employees');
        }
    }, []);

    const fetchShopAndEmployees = React.useCallback(async () => {
        try {
            const token = localStorage.getItem('token');
            if (!token) {
                setError('Not authenticated');
                setLoading(false);
                return;
            }

            // Get shop ID first
            const shopResponse = await axios.get(`/shops/my-shops`, {
                headers: { Authorization: `Bearer ${token}` }
            });

            if (shopResponse.data.length === 0) {
                setError('No shop found. Please create a shop first.');
                setLoading(false);
                return;
            }

            const shop = shopResponse.data[0];
            setShopId(shop.id);

            // Fetch employees
            await fetchEmployees(shop.id, token);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load data');
        } finally {
            setLoading(false);
        }
    }, [fetchEmployees]);

    const fetchShifts = React.useCallback(async (id: number, token: string, employeeId: number | null = null) => {
        setShiftsLoading(true);
        try {
            let url = `/shops/${id}/employee-shifts?months=3`;
            if (employeeId) {
                url += `&employee_id=${employeeId}`;
            }
            const response = await axios.get(url, {
                headers: { Authorization: `Bearer ${token}` }
            });
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
            const token = localStorage.getItem('token');
            if (token) {
                fetchShifts(shopId, token, selectedEmployeeFilter);
            }
        }
    }, [currentTab, shopId, selectedEmployeeFilter, fetchShifts]);

    useEffect(() => {
        const checkUsername = async () => {
            if (!formData.username || formData.username.length < 3) {
                setUsernameAvailable(null);
                return;
            }

            setCheckingUsername(true);
            try {
                const response = await axios.get(`/check-username/${formData.username}`);
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
                const response = await axios.get(`/check-email/${encodeURIComponent(formData.email)}`);
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
            const token = localStorage.getItem('token');
            await axios.post(
                `/shops/${shopId}/employees`,
                formData,
                { headers: { Authorization: `Bearer ${token}` } }
            );

            setSuccess('Employee added successfully!');
            setFormData({ username: '', email: '', password: '' });
            setOpenDialog(false);

            // Refresh employee list
            await fetchEmployees(shopId, token!);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to add employee');
        } finally {
            setSubmitting(false);
        }
    };

    const handleRemoveEmployee = async (employeeId: number) => {
        if (!shopId) return;
        if (!window.confirm('Are you sure you want to remove this employee?')) return;

        try {
            const token = localStorage.getItem('token');
            await axios.delete(
                `/shops/${shopId}/employees/${employeeId}`,
                { headers: { Authorization: `Bearer ${token}` } }
            );

            setSuccess('Employee removed successfully!');
            await fetchEmployees(shopId, token!);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to remove employee');
        }
    };

    const handleReactivateEmployee = async (employeeId: number) => {
        if (!shopId) return;

        try {
            const token = localStorage.getItem('token');
            await axios.put(
                `/shops/${shopId}/employees/${employeeId}/reactivate`,
                {},
                { headers: { Authorization: `Bearer ${token}` } }
            );

            setSuccess('Employee reactivated successfully!');
            await fetchEmployees(shopId, token!);
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
        <Box sx={{ p: 3 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Box display="flex" alignItems="center" gap={2}>
                    <PeopleIcon sx={{ fontSize: 32 }} />
                    <Typography variant="h4" component="h1">
                        Team Management
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

            {error && <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>{success}</Alert>}

            <Paper sx={{ mb: 3 }}>
                <Tabs value={currentTab} onChange={handleTabChange} aria-label="team management tabs">
                    <Tab label="Employee List" icon={<PeopleIcon />} iconPosition="start" />
                    <Tab label="Attendance Calendar" icon={<CalendarMonthIcon />} iconPosition="start" />
                </Tabs>
            </Paper>

            {currentTab === 0 && (
                <Paper>
                    <TableContainer>
                        <Table>
                            <TableHead>
                                <TableRow>
                                    <TableCell><strong>Username</strong></TableCell>
                                    <TableCell><strong>Email</strong></TableCell>
                                    <TableCell><strong>Status</strong></TableCell>
                                    <TableCell><strong>Added On</strong></TableCell>
                                    <TableCell align="right"><strong>Actions</strong></TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {employees.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                                            <Typography color="text.secondary">
                                                No employees yet. Add your first employee to get started!
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    employees.map((employee) => (
                                        <TableRow key={employee.user.id}>
                                            <TableCell>{employee.user.username}</TableCell>
                                            <TableCell>{employee.user.email}</TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={employee.is_active ? 'Active' : 'Inactive'}
                                                    color={employee.is_active ? 'success' : 'default'}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                {new Date(employee.created_at).toLocaleDateString()}
                                            </TableCell>
                                            <TableCell align="right">
                                                {employee.is_active ? (
                                                    <IconButton
                                                        color="error"
                                                        onClick={() => handleRemoveEmployee(employee.user.id)}
                                                        title="Remove employee"
                                                    >
                                                        <DeleteIcon />
                                                    </IconButton>
                                                ) : (
                                                    <IconButton
                                                        color="primary"
                                                        onClick={() => handleReactivateEmployee(employee.user.id)}
                                                        title="Reactivate employee"
                                                    >
                                                        <RestoreIcon />
                                                    </IconButton>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
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
        </Box>
    );
};

export default EmployeeManagementPage;
