import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Box, CircularProgress, Container, Alert } from '@mui/material';
import axios from 'axios';
import MasterAIAgent from '../../../landing-page/components/MasterAIAgent';

interface AIShopPublicPageProps {
  shopSlug?: string;
}

const AIShopPublicPage: React.FC<AIShopPublicPageProps> = ({ shopSlug }) => {
  const { shopId } = useParams<{ shopId: string }>();
  const effectiveId = shopSlug || shopId;

  const [shop, setShop] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchShopData = async () => {
      if (!effectiveId) {
        setError('Shop not found');
        setLoading(false);
        return;
      }

      try {
        const isSlug = isNaN(Number(effectiveId));
        const endpoint = isSlug ? `/shops/s/${effectiveId}` : `/shops/${effectiveId}`;
        const response = await axios.get(endpoint);
        setShop(response.data);
      } catch (_err) {
        setError('Could not load shop details');
      } finally {
        setLoading(false);
      }
    };

    void fetchShopData();
  }, [effectiveId]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !shop) {
    return (
      <Container maxWidth="sm" sx={{ mt: 10 }}>
        <Alert severity="error">{error || 'Shop not found'}</Alert>
      </Container>
    );
  }

  return (
    <MasterAIAgent
      forceOpen={true}
      hideCloseButton={true}
      initialInteractionMode="chat"
      shopContext={{
        id: shop.id,
        slug: shop.slug,
        name: shop.name,
        city: shop.city,
        shopType: shop.shop_type,
      }}
    />
  );
};

export default AIShopPublicPage;
