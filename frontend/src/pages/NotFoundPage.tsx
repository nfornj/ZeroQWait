import React from "react";
import { Link as RouterLink } from "react-router-dom";
import { Container, Typography, Button, Box } from "@mui/material";
import ContentCutIcon from "@mui/icons-material/ContentCut";

const NotFoundPage: React.FC = () => {
  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          mt: 8,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
        }}
      >
        <ContentCutIcon sx={{ fontSize: 60, color: "text.secondary", mb: 2 }} />
        <Typography variant="h2" component="h1" gutterBottom>
          404
        </Typography>
        <Typography variant="h5" component="h2" gutterBottom>
          Page Not Found
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          The page you're looking for doesn't exist or has been moved.
        </Typography>
        <Button
          variant="contained"
          component={RouterLink}
          to="/"
          sx={{ mt: 2 }}
        >
          Go to Homepage
        </Button>
      </Box>
    </Container>
  );
};

export default NotFoundPage;
