import React from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    List,
    ListItem,
    ListItemButton,
    ListItemAvatar,
    ListItemText,
    Avatar,
    Box,
    Typography,
    Chip,
    Radio,
    RadioGroup,
    FormControlLabel,
    CircularProgress,
} from '@mui/material';
import ShuffleIcon from '@mui/icons-material/Shuffle';
import PersonIcon from '@mui/icons-material/Person';

interface Employee {
    user_id: number;
    username: string;
    email: string;
    profile_photo_url?: string;
    clock_in: string;
}

interface EmployeeSelectorProps {
    open: boolean;
    employees: Employee[];
    loading?: boolean;
    onClose: () => void;
    onSelect: (employeeId: number | null) => void;
    title?: string;
    allowRandom?: boolean;
}

const EmployeeSelector: React.FC<EmployeeSelectorProps> = ({
    open,
    employees,
    loading = false,
    onClose,
    onSelect,
    title = 'Assign Employee',
    allowRandom = true,
}) => {
    const [selectedOption, setSelectedOption] = React.useState<string>('random');
    const [selectedEmployeeId, setSelectedEmployeeId] = React.useState<number | null>(null);

    const handleOptionChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSelectedOption(event.target.value);
        if (event.target.value === 'random') {
            setSelectedEmployeeId(null);
        }
    };

    const handleEmployeeSelect = (employeeId: number) => {
        setSelectedOption('specific');
        setSelectedEmployeeId(employeeId);
    };

    const handleConfirm = () => {
        if (selectedOption === 'random') {
            onSelect(null); // null means random assignment
        } else if (selectedEmployeeId) {
            onSelect(selectedEmployeeId);
        }
        handleClose();
    };

    const handleClose = () => {
        setSelectedOption('random');
        setSelectedEmployeeId(null);
        onClose();
    };

    const getTimeSinceClockIn = (clockIn: string) => {
        const now = new Date();
        const clockInTime = new Date(clockIn);
        const diff = now.getTime() - clockInTime.getTime();
        const minutes = Math.floor(diff / 60000);

        if (minutes < 60) {
            return `${minutes}m ago`;
        }
        const hours = Math.floor(minutes / 60);
        return `${hours}h ago`;
    };

    return (
        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
            <DialogTitle>{title}</DialogTitle>
            <DialogContent>
                {loading ? (
                    <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
                        <CircularProgress />
                    </Box>
                ) : employees.length === 0 ? (
                    <Box textAlign="center" py={4}>
                        <Typography variant="body1" color="text.secondary">
                            No employees are currently clocked in
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            You will be assigned as the server
                        </Typography>
                    </Box>
                ) : (
                    <>
                        <RadioGroup value={selectedOption} onChange={handleOptionChange}>
                            {allowRandom && (
                                <FormControlLabel
                                    value="random"
                                    control={<Radio />}
                                    label={
                                        <Box display="flex" alignItems="center">
                                            <ShuffleIcon sx={{ mr: 1 }} />
                                            <Typography>Random Assignment</Typography>
                                            <Chip
                                                label="Auto"
                                                size="small"
                                                color="primary"
                                                sx={{ ml: 1 }}
                                            />
                                        </Box>
                                    }
                                />
                            )}
                            <FormControlLabel
                                value="specific"
                                control={<Radio />}
                                label={
                                    <Box display="flex" alignItems="center">
                                        <PersonIcon sx={{ mr: 1 }} />
                                        <Typography>Select Specific Employee</Typography>
                                    </Box>
                                }
                            />
                        </RadioGroup>

                        {selectedOption === 'specific' && (
                            <List sx={{ mt: 2 }}>
                                {employees.map((employee) => (
                                    <ListItem
                                        key={employee.user_id}
                                        disablePadding
                                        sx={{
                                            mb: 1,
                                            border: '1px solid',
                                            borderColor:
                                                selectedEmployeeId === employee.user_id
                                                    ? 'primary.main'
                                                    : 'divider',
                                            bgcolor:
                                                selectedEmployeeId === employee.user_id
                                                    ? 'primary.light'
                                                    : 'background.paper',
                                        }}
                                    >
                                        <ListItemButton
                                            onClick={() => handleEmployeeSelect(employee.user_id)}
                                            selected={selectedEmployeeId === employee.user_id}
                                        >
                                            <ListItemAvatar>
                                                <Avatar
                                                    src={employee.profile_photo_url}
                                                    sx={{
                                                        bgcolor:
                                                            selectedEmployeeId === employee.user_id
                                                                ? 'primary.main'
                                                                : 'secondary.main',
                                                    }}
                                                >
                                                    {employee.username.charAt(0).toUpperCase()}
                                                </Avatar>
                                            </ListItemAvatar>
                                            <ListItemText
                                                primary={employee.username}
                                                secondary={
                                                    <Box display="flex" alignItems="center" gap={1}>
                                                        <Chip
                                                            label="Online"
                                                            size="small"
                                                            color="success"
                                                            sx={{ height: 20 }}
                                                        />
                                                        <Typography variant="caption">
                                                            Clocked in {getTimeSinceClockIn(employee.clock_in)}
                                                        </Typography>
                                                    </Box>
                                                }
                                            />
                                        </ListItemButton>
                                    </ListItem>
                                ))}
                            </List>
                        )}
                    </>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose}>Cancel</Button>
                <Button
                    onClick={handleConfirm}
                    variant="contained"
                    color="primary"
                    disabled={loading || (employees.length === 0 && selectedOption === 'specific') || (selectedOption === 'specific' && !selectedEmployeeId)}
                >
                    Confirm
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default EmployeeSelector;
