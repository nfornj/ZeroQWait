import React, { useState } from 'react';
import {
    Box,
    Paper,
    Typography,
    IconButton,
    Chip,
    Tooltip,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Card,
    CardContent,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import {
    startOfMonth,
    endOfMonth,
    eachDayOfInterval,
    format,
    isSameDay,
    addMonths,
    subMonths,
    isToday,
    startOfWeek,
    endOfWeek,
    parseISO
} from 'date-fns';

interface Shift {
    id: number;
    user_id: number;
    username: string;
    email: string;
    profile_photo_url?: string;
    shop_id: number;
    clock_in: string;
    clock_out?: string;
}

interface AttendanceCalendarProps {
    shifts: Shift[];
    employees: Array<{ id: number; username: string }>;
    onEmployeeChange?: (employeeId: number | null) => void;
}

const AttendanceCalendar: React.FC<AttendanceCalendarProps> = ({
    shifts,
    employees,
    onEmployeeChange
}) => {
    const [currentMonth, setCurrentMonth] = useState(new Date());
    const [selectedEmployee, setSelectedEmployee] = useState<number | null>(null);

    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calendarStart = startOfWeek(monthStart);
    const calendarEnd = endOfWeek(monthEnd);
    const calendarDays = eachDayOfInterval({ start: calendarStart, end: calendarEnd });

    const handlePreviousMonth = () => {
        const newMonth = subMonths(currentMonth, 1);
        // Limit to 3 months back from today
        const threeMonthsAgo = subMonths(new Date(), 3);
        if (newMonth >= threeMonthsAgo) {
            setCurrentMonth(newMonth);
        }
    };

    const handleNextMonth = () => {
        const newMonth = addMonths(currentMonth, 1);
        // Can't go beyond current month
        if (newMonth <= new Date()) {
            setCurrentMonth(newMonth);
        }
    };

    const handleEmployeeChange = (event: any) => {
        const value = event.target.value;
        const employeeId = value === 'all' ? null : parseInt(value);
        setSelectedEmployee(employeeId);
        if (onEmployeeChange) {
            onEmployeeChange(employeeId);
        }
    };

    const getShiftsForDay = (date: Date): Shift[] => {
        return shifts.filter(shift => {
            const shiftDate = parseISO(shift.clock_in);
            return isSameDay(shiftDate, date);
        });
    };

    const calculateDuration = (clockIn: string, clockOut?: string): string => {
        const start = parseISO(clockIn);
        const end = clockOut ? parseISO(clockOut) : new Date();
        const diffMs = end.getTime() - start.getTime();
        const hours = Math.floor(diffMs / (1000 * 60 * 60));
        const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        return `${hours}h ${minutes}m`;
    };

    const formatTime = (dateString: string): string => {
        return format(parseISO(dateString), 'h:mm a');
    };

    const canGoBack = subMonths(currentMonth, 1) >= subMonths(new Date(), 3);
    const canGoForward = addMonths(currentMonth, 1) <= new Date();

    return (
        <Box>
            {/* Header with month navigation and employee filter */}
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Box display="flex" alignItems="center" gap={1}>
                    <IconButton
                        onClick={handlePreviousMonth}
                        disabled={!canGoBack}
                        size="small"
                    >
                        <ChevronLeftIcon />
                    </IconButton>
                    <Typography variant="h6" sx={{ minWidth: '150px', textAlign: 'center' }}>
                        {format(currentMonth, 'MMMM yyyy')}
                    </Typography>
                    <IconButton
                        onClick={handleNextMonth}
                        disabled={!canGoForward}
                        size="small"
                    >
                        <ChevronRightIcon />
                    </IconButton>
                </Box>

                <FormControl size="small" sx={{ minWidth: 200 }}>
                    <InputLabel>Filter by Employee</InputLabel>
                    <Select
                        value={selectedEmployee === null ? 'all' : selectedEmployee.toString()}
                        onChange={handleEmployeeChange}
                        label="Filter by Employee"
                    >
                        <MenuItem value="all">All Employees</MenuItem>
                        {employees.map(emp => (
                            <MenuItem key={emp.id} value={emp.id.toString()}>
                                {emp.username}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Box>

            {/* Calendar Grid */}
            <Paper sx={{ p: 2 }}>
                {/* Day headers */}
                <Box display="flex" gap={1} sx={{ mb: 1 }}>
                    {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                        <Box key={day} flex="1">
                            <Typography
                                variant="caption"
                                fontWeight="bold"
                                display="block"
                                textAlign="center"
                                color="text.secondary"
                            >
                                {day}
                            </Typography>
                        </Box>
                    ))}
                </Box>

                {/* Calendar days */}
                <Box display="flex" flexWrap="wrap" gap={1}>
                    {calendarDays.map((day, index) => {
                        const dayShifts = getShiftsForDay(day);
                        const isCurrentMonth = day.getMonth() === currentMonth.getMonth();
                        const isTodayDate = isToday(day);

                        return (
                            <Box key={index} sx={{ width: 'calc((100% - 6 * 8px) / 7)' }}>
                                <Paper
                                    variant="outlined"
                                    sx={{
                                        minHeight: '100px',
                                        p: 1,
                                        backgroundColor: isTodayDate
                                            ? 'action.selected'
                                            : isCurrentMonth
                                                ? 'background.paper'
                                                : 'action.hover',
                                        border: isTodayDate ? '2px solid' : '1px solid',
                                        borderColor: isTodayDate ? 'primary.main' : 'divider',
                                    }}
                                >
                                    <Typography
                                        variant="caption"
                                        fontWeight={isTodayDate ? 'bold' : 'normal'}
                                        color={isCurrentMonth ? 'text.primary' : 'text.disabled'}
                                    >
                                        {format(day, 'd')}
                                    </Typography>

                                    {dayShifts.length > 0 && (
                                        <Box mt={0.5} display="flex" flexDirection="column" gap={0.5}>
                                            {dayShifts.slice(0, 3).map(shift => (
                                                <Tooltip
                                                    key={shift.id}
                                                    title={
                                                        <Box>
                                                            <Typography variant="body2" fontWeight="bold">
                                                                {shift.username}
                                                            </Typography>
                                                            <Typography variant="caption">
                                                                In: {formatTime(shift.clock_in)}
                                                            </Typography>
                                                            <br />
                                                            <Typography variant="caption">
                                                                Out: {shift.clock_out ? formatTime(shift.clock_out) : 'Still active'}
                                                            </Typography>
                                                            <br />
                                                            <Typography variant="caption" fontWeight="bold">
                                                                Duration: {calculateDuration(shift.clock_in, shift.clock_out)}
                                                            </Typography>
                                                        </Box>
                                                    }
                                                    arrow
                                                >
                                                    <Chip
                                                        label={shift.username}
                                                        size="small"
                                                        color={shift.clock_out ? 'success' : 'warning'}
                                                        sx={{
                                                            fontSize: '0.65rem',
                                                            height: '20px',
                                                            width: '100%',
                                                            '& .MuiChip-label': {
                                                                overflow: 'hidden',
                                                                textOverflow: 'ellipsis',
                                                                whiteSpace: 'nowrap',
                                                            }
                                                        }}
                                                    />
                                                </Tooltip>
                                            ))}
                                            {dayShifts.length > 3 && (
                                                <Typography variant="caption" color="text.secondary" textAlign="center">
                                                    +{dayShifts.length - 3} more
                                                </Typography>
                                            )}
                                        </Box>
                                    )}
                                </Paper>
                            </Box>
                        );
                    })}
                </Box>
            </Paper>

            {/* Legend */}
            <Box mt={2} display="flex" gap={2} justifyContent="center">
                <Box display="flex" alignItems="center" gap={1}>
                    <Chip label="Complete" size="small" color="success" />
                    <Typography variant="caption">Shift completed</Typography>
                </Box>
                <Box display="flex" alignItems="center" gap={1}>
                    <Chip label="Active" size="small" color="warning" />
                    <Typography variant="caption">Still clocked in</Typography>
                </Box>
            </Box>
        </Box>
    );
};

export default AttendanceCalendar;
