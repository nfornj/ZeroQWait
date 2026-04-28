import React, { useState } from "react";
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  IconButton,
  Box,
  Rating,
  Chip,
  Link,
  Collapse,
  Alert,
} from "@mui/material";
import {
  Phone as PhoneIcon,
  Language as LanguageIcon,
  ExpandMore as ExpandMoreIcon,
} from "@mui/icons-material";
import { styled } from "@mui/material/styles";
import { HaircutService } from "../../../services/api";

interface HaircutCardProps {
  haircut: HaircutService;
  onFavoriteRemoved?: (id: number) => void;
}

const ExpandMore = styled(IconButton)<{ expand: boolean }>(
  ({ theme, expand }) => ({
    transform: !expand ? "rotate(0deg)" : "rotate(180deg)",
    marginLeft: "auto",
    transition: theme.transitions.create("transform", {
      duration: theme.transitions.duration.shortest,
    }),
  })
);

const HaircutCard: React.FC<HaircutCardProps> = ({
  haircut,
  onFavoriteRemoved,
}) => {
  const [expanded, setExpanded] = useState(false);

  const handleExpandClick = () => {
    setExpanded(!expanded);
  };

  return (
    <Card
      elevation={0}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #EBEBEB',
        overflow: 'hidden',
        transition: 'all 0.3s ease-in-out',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: '0px 8px 24px rgba(0, 0, 0, 0.12)',
          borderColor: 'transparent'
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          position: 'relative',
          background: 'linear-gradient(135deg, rgba(255, 90, 95, 0.1) 0%, rgba(0, 166, 153, 0.05) 100%)',
          p: 3,
          pb: 2
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            mb: 2
          }}
        >
          <Typography
            variant="h6"
            component="h2"
            sx={{
              fontWeight: 600,
              fontSize: '1.25rem',
              color: 'text.primary',
              flexGrow: 1,
              mr: 1
            }}
          >
            {haircut.name}
          </Typography>
        </Box>

        {/* Rating and Price */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Rating
              value={haircut.rating}
              precision={0.5}
              readOnly
              size="small"
              sx={{ fontSize: '1.1rem' }}
            />
            <Typography
              variant="body2"
              sx={{
                fontWeight: 500,
                color: 'text.secondary',
                ml: 0.5
              }}
            >
              {haircut.rating}
            </Typography>
          </Box>
          {haircut.price_range && (
            <Chip
              label={haircut.price_range}
              size="small"
              sx={{
                bgcolor: 'white',
                color: 'primary.main',
                fontWeight: 600,
                border: '1px solid',
                borderColor: 'primary.light'
              }}
            />
          )}
        </Box>
      </Box>

      <CardContent sx={{ flexGrow: 1, pt: 2 }}>
        {/* Location */}
        <Box sx={{ mb: 2 }}>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 500,
              color: 'text.primary',
              mb: 0.5
            }}
          >
            {haircut.address}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {`${haircut.city}, ${haircut.state} ${haircut.zip_code}`}
          </Typography>
        </Box>

        {/* Contact Info */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
          {haircut.phone && (
            <Link
              href={`tel:${haircut.phone}`}
              sx={{
                display: 'flex',
                alignItems: 'center',
                textDecoration: 'none',
                color: 'primary.main',
                fontSize: '0.875rem',
                fontWeight: 500,
                '&:hover': {
                  textDecoration: 'underline'
                }
              }}
            >
              <PhoneIcon sx={{ fontSize: 16, mr: 0.5 }} />
              {haircut.phone}
            </Link>
          )}
          {haircut.website && (
            <Link
              href={haircut.website}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                display: 'flex',
                alignItems: 'center',
                textDecoration: 'none',
                color: 'secondary.main',
                fontSize: '0.875rem',
                fontWeight: 500,
                '&:hover': {
                  textDecoration: 'underline'
                }
              }}
            >
              <LanguageIcon sx={{ fontSize: 16, mr: 0.5 }} />
              Visit Website
            </Link>
          )}
        </Box>
      </CardContent>

      {/* Expandable section */}
      {haircut.hours && (
        <>
          <CardActions
            disableSpacing
            sx={{
              borderTop: '1px solid #F0F0F0',
              px: 3,
              py: 1.5
            }}
          >
            <Typography
              variant="body2"
              sx={{
                fontWeight: 500,
                color: 'text.secondary',
                flexGrow: 1
              }}
            >
              Hours & Details
            </Typography>
            <ExpandMore
              expand={expanded}
              onClick={handleExpandClick}
              aria-expanded={expanded}
              aria-label="show more"
              sx={{
                color: 'text.secondary',
                '&:hover': {
                  bgcolor: 'rgba(0, 0, 0, 0.04)'
                }
              }}
            >
              <ExpandMoreIcon />
            </ExpandMore>
          </CardActions>

          <Collapse in={expanded} timeout="auto" unmountOnExit>
            <CardContent sx={{ pt: 0, borderTop: '1px solid #F0F0F0' }}>
              <Typography
                variant="subtitle2"
                sx={{
                  fontWeight: 600,
                  color: 'text.primary',
                  mb: 1
                }}
              >
                Hours of Operation
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  color: 'text.secondary',
                  lineHeight: 1.6
                }}
              >
                {haircut.hours}
              </Typography>
            </CardContent>
          </Collapse>
        </>
      )}
    </Card>
  );
};

export default HaircutCard;
