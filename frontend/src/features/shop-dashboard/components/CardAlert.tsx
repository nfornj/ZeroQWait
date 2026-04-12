import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';

export default function CardAlert() {
  return (
    <Card variant="outlined" sx={{ m: 1.5, flexShrink: 0, bgcolor: 'var(--owner-glass-bg)', backdropFilter: 'blur(20px)', borderColor: 'var(--owner-glass-border)', boxShadow: 'var(--owner-glass-shadow)' }}>
      <CardContent>
        <AutoAwesomeRoundedIcon fontSize="small" sx={{ color: 'var(--owner-secondary)' }} />
        <Typography gutterBottom sx={{ fontWeight: 600 }}>
          Plan about to expire
        </Typography>
        <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
          Enjoy 10% off when renewing your plan today.
        </Typography>
        <Button variant="contained" size="small" fullWidth sx={{ bgcolor: 'var(--owner-primary)', '&:hover': { bgcolor: 'var(--owner-primary)', filter: 'brightness(0.95)' } }}>
          Get the discount
        </Button>
      </CardContent>
    </Card>
  );
}
