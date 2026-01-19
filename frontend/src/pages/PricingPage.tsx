import React from "react";
import {
    Container,
    Typography,
    Box,
    Card,
    CardContent,
    Button,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Chip,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { Link } from "react-router-dom";

const PricingPage: React.FC = () => {
    const tiers = [
        {
            name: "Free",
            price: "$0",
            period: "forever",
            features: [
                "Up to 1 shop",
                "50 customers per queue",
                "Basic queue management",
                "Shared database (multi-tenant)",
                "Email support",
                "Mobile-friendly interface",
            ],
            cta: "Get Started",
            to: "/register/shop-owner",
            highlighted: false,
            color: "primary",
        },
        {
            name: "Premium",
            price: "$29",
            period: "per month",
            features: [
                "Up to 5 shops",
                "200 customers per queue",
                "🔒 Dedicated database (isolated data)",
                "Advanced analytics & reports",
                "Priority support (24/7)",
                "Custom branding & colors",
                "SMS notifications",
                "Automatic backups",
            ],
            cta: "Start Free Trial",
            to: "/register/shop-owner",
            highlighted: true,
            color: "secondary",
        },
    ];

    return (
        <Container maxWidth="lg" sx={{ py: 8 }}>
            <Box sx={{ textAlign: "center", mb: 6 }}>
                <Typography variant="h2" component="h1" gutterBottom fontWeight="bold">
                    Choose Your Plan
                </Typography>
                <Typography variant="h6" color="text.secondary" paragraph>
                    Start free, upgrade when you need more capacity
                </Typography>
            </Box>

            <Box display="flex" flexWrap="wrap" gap={4} alignItems="stretch">
                {tiers.map((tier) => (
                    <Box xs={12} md={4} key={tier.name}>
                        <Card
                            raised={tier.highlighted}
                            sx={{
                                height: "100%",
                                display: "flex",
                                flexDirection: "column",
                                position: "relative",
                                border: tier.highlighted ? "2px solid" : "1px solid",
                                borderColor: tier.highlighted ? "secondary.main" : "divider",
                                transition: "transform 0.2s",
                                "&:hover": {
                                    transform: "translateY(-8px)",
                                },
                            }}
                        >
                            {tier.highlighted && (
                                <Chip
                                    label="Most Popular"
                                    color="secondary"
                                    sx={{
                                        position: "absolute",
                                        top: 16,
                                        right: 16,
                                        fontWeight: "bold",
                                    }}
                                />
                            )}

                            <CardContent sx={{ flexGrow: 1, pt: tier.highlighted ? 4 : 3 }}>
                                <Typography variant="h4" component="h2" gutterBottom fontWeight="bold">
                                    {tier.name}
                                </Typography>

                                <Box sx={{ my: 3 }}>
                                    <Typography
                                        variant="h3"
                                        component="span"
                                        color={tier.highlighted ? "secondary" : "primary"}
                                        fontWeight="bold"
                                    >
                                        {tier.price}
                                    </Typography>
                                    <Typography variant="body1" component="span" color="text.secondary">
                                        {" "}
                                        / {tier.period}
                                    </Typography>
                                </Box>

                                <List sx={{ mt: 2 }}>
                                    {tier.features.map((feature, index) => (
                                        <ListItem key={index} disablePadding sx={{ mb: 1 }}>
                                            <ListItemIcon sx={{ minWidth: 36 }}>
                                                <CheckCircleIcon color="success" fontSize="small" />
                                            </ListItemIcon>
                                            <ListItemText
                                                primary={feature}
                                                primaryTypographyProps={{ variant: "body2" }}
                                            />
                                        </ListItem>
                                    ))}
                                </List>

                                <Button
                                    component={Link}
                                    to={tier.to}
                                    variant={tier.highlighted ? "contained" : "outlined"}
                                    color={tier.color as any}
                                    fullWidth
                                    size="large"
                                    sx={{
                                        mt: 3,
                                        py: 1.5,
                                        fontWeight: "bold",
                                    }}
                                >
                                    {tier.cta}
                                </Button>
                            </CardContent>
                        </Card>
                    </Box>
                ))}
            </Box>

            <Box sx={{ mt: 8, textAlign: "center" }}>
                <Typography variant="h5" gutterBottom>
                    All plans include:
                </Typography>
                <Box display="flex" flexWrap="wrap" gap={2} sx={{ mt: 2, justifyContent: "center" }}>
                    {[
                        "Real-time queue tracking",
                        "Customer notifications",
                        "Wait time estimates",
                        "Mobile responsive",
                        "No setup fees",
                        "Cancel anytime",
                    ].map((feature) => (
                        <Box xs={12} sm={6} md={4} key={feature}>
                            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                                <CheckCircleIcon color="primary" sx={{ mr: 1 }} fontSize="small" />
                                <Typography variant="body1">{feature}</Typography>
                            </Box>
                        </Box>
                    ))}
                </Box>
            </Box>

            <Box sx={{ mt: 6, textAlign: "center" }}>
                <Typography variant="body2" color="text.secondary">
                    Need a custom plan? <Link to="/register/shop-owner">Contact us</Link> for enterprise pricing
                </Typography>
            </Box>
        </Container>
    );
};

export default PricingPage;
