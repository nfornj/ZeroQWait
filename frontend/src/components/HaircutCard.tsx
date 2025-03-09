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
  Favorite as FavoriteIcon,
  FavoriteBorder as FavoriteBorderIcon,
  Phone as PhoneIcon,
  Language as LanguageIcon,
  ExpandMore as ExpandMoreIcon,
} from "@mui/icons-material";
import { styled } from "@mui/material/styles";
import { HaircutService, addFavorite, removeFavorite } from "../services/api";
import { useAuth } from "../contexts/AuthContext";

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
  const [isFavorite, setIsFavorite] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { isAuthenticated } = useAuth();

  const handleExpandClick = () => {
    setExpanded(!expanded);
  };

  const handleFavoriteClick = async () => {
    if (!isAuthenticated) {
      setError("Please log in to save favorites");
      return;
    }

    try {
      setError(null);
      if (isFavorite) {
        await removeFavorite(haircut.id);
        setIsFavorite(false);
        if (onFavoriteRemoved) {
          onFavoriteRemoved(haircut.id);
        }
      } else {
        await addFavorite(haircut.id);
        setIsFavorite(true);
      }
    } catch (err) {
      setError("Failed to update favorite status");
      console.error("Favorite error:", err);
    }
  };

  return (
    <Card>
      <CardContent>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <Typography variant="h6" component="h2" gutterBottom>
            {haircut.name}
          </Typography>
          <IconButton
            onClick={handleFavoriteClick}
            color={isFavorite ? "secondary" : "default"}
          >
            {isFavorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
          </IconButton>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mt: 1, mb: 1 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ mb: 1 }}>
          <Rating value={haircut.rating} precision={0.5} readOnly />
          {haircut.price_range && (
            <Chip label={haircut.price_range} size="small" sx={{ ml: 1 }} />
          )}
        </Box>

        <Typography variant="body2" color="text.secondary" gutterBottom>
          {haircut.address}
          <br />
          {`${haircut.city}, ${haircut.state} ${haircut.zip_code}`}
        </Typography>

        <Box sx={{ display: "flex", gap: 1, mt: 1 }}>
          {haircut.phone && (
            <Link
              href={`tel:${haircut.phone}`}
              sx={{ display: "flex", alignItems: "center" }}
            >
              <PhoneIcon fontSize="small" sx={{ mr: 0.5 }} />
              {haircut.phone}
            </Link>
          )}
          {haircut.website && (
            <Link
              href={haircut.website}
              target="_blank"
              rel="noopener noreferrer"
              sx={{ display: "flex", alignItems: "center" }}
            >
              <LanguageIcon fontSize="small" sx={{ mr: 0.5 }} />
              Website
            </Link>
          )}
        </Box>
      </CardContent>

      <CardActions disableSpacing>
        <ExpandMore
          expand={expanded}
          onClick={handleExpandClick}
          aria-expanded={expanded}
          aria-label="show more"
        >
          <ExpandMoreIcon />
        </ExpandMore>
      </CardActions>

      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <CardContent>
          {haircut.hours && (
            <>
              <Typography variant="subtitle2" gutterBottom>
                Hours of Operation
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                {haircut.hours}
              </Typography>
            </>
          )}
        </CardContent>
      </Collapse>
    </Card>
  );
};

export default HaircutCard;
