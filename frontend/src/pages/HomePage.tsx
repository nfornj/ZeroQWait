import React from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Container,
  Typography,
  Box,
  Button,
  Grid,
  Card,
  CardContent,
  CardMedia,
} from "@mui/material";
import ContentCutIcon from "@mui/icons-material/ContentCut";
import SearchIcon from "@mui/icons-material/Search";
import FavoriteIcon from "@mui/icons-material/Favorite";
import { useAuth } from "../contexts/AuthContext";

const HomePage: React.FC = () => {
  const { isAuthenticated } = useAuth();

  return (
    <Container maxWidth="lg">
      {/* Hero Section */}
      <Box
        sx={{
          pt: 8,
          pb: 6,
          textAlign: "center",
        }}
      >
        <Typography
          component="h1"
          variant="h2"
          align="center"
          color="text.primary"
          gutterBottom
        >
          <ContentCutIcon
            sx={{ fontSize: 40, verticalAlign: "middle", mr: 1 }}
          />
          FastCuts
        </Typography>
        <Typography
          variant="h5"
          align="center"
          color="text.secondary"
          paragraph
        >
          Find the best haircut services near you, quickly and easily. Save your
          favorites and never worry about finding a good haircut again!
        </Typography>
        <Box sx={{ mt: 4 }}>
          <Grid container spacing={2} justifyContent="center">
            <Grid item>
              <Button
                variant="contained"
                size="large"
                component={RouterLink}
                to="/search"
                startIcon={<SearchIcon />}
              >
                Find Haircuts
              </Button>
            </Grid>
            {isAuthenticated ? (
              <Grid item>
                <Button
                  variant="outlined"
                  size="large"
                  component={RouterLink}
                  to="/favorites"
                  startIcon={<FavoriteIcon />}
                >
                  My Favorites
                </Button>
              </Grid>
            ) : (
              <Grid item>
                <Button
                  variant="outlined"
                  size="large"
                  component={RouterLink}
                  to="/login"
                >
                  Login / Register
                </Button>
              </Grid>
            )}
          </Grid>
        </Box>
      </Box>

      {/* Features Section */}
      <Box sx={{ py: 8 }}>
        <Typography variant="h4" align="center" gutterBottom>
          How It Works
        </Typography>
        <Grid container spacing={4} sx={{ mt: 2 }}>
          <Grid item xs={12} md={4}>
            <Card sx={{ height: "100%" }}>
              <CardMedia
                component="div"
                sx={{
                  pt: "56.25%",
                  bgcolor: "primary.light",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <SearchIcon
                  sx={{
                    fontSize: 80,
                    color: "white",
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%, -50%)",
                  }}
                />
              </CardMedia>
              <CardContent sx={{ flexGrow: 1 }}>
                <Typography gutterBottom variant="h5" component="h2">
                  Search
                </Typography>
                <Typography>
                  Find haircut services near your location with our easy-to-use
                  search feature.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card sx={{ height: "100%" }}>
              <CardMedia
                component="div"
                sx={{
                  pt: "56.25%",
                  bgcolor: "secondary.light",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <ContentCutIcon
                  sx={{
                    fontSize: 80,
                    color: "white",
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%, -50%)",
                  }}
                />
              </CardMedia>
              <CardContent sx={{ flexGrow: 1 }}>
                <Typography gutterBottom variant="h5" component="h2">
                  Compare
                </Typography>
                <Typography>
                  View details, ratings, and prices to find the perfect haircut
                  service for you.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card sx={{ height: "100%" }}>
              <CardMedia
                component="div"
                sx={{
                  pt: "56.25%",
                  bgcolor: "error.light",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <FavoriteIcon
                  sx={{
                    fontSize: 80,
                    color: "white",
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%, -50%)",
                  }}
                />
              </CardMedia>
              <CardContent sx={{ flexGrow: 1 }}>
                <Typography gutterBottom variant="h5" component="h2">
                  Save
                </Typography>
                <Typography>
                  Save your favorite haircut services to quickly find them again
                  in the future.
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
};

export default HomePage;
