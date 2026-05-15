import React, { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, Package } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

import {
  getInventoryItems,
  getLowStockAlerts,
  InventoryItem,
} from '../../../services/api';

interface InventorySummaryWidgetProps {
  shopId: number;
}

export default function InventorySummaryWidget({ shopId }: InventorySummaryWidgetProps) {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [outCount, setOutCount] = useState(0);
  const [lowCount, setLowCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getInventoryItems(shopId),
      getLowStockAlerts(shopId),
    ])
      .then(([itemsRes, alertsRes]) => {
        const allItems = itemsRes.data.items;
        const alerts = alertsRes.data.alerts;
        setItems(allItems);
        setOutCount(alerts.filter((a) => a.current_stock <= 0).length);
        setLowCount(alerts.filter((a) => a.current_stock > 0).length);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [shopId]);

  const totalValue = items.reduce(
    (sum, i) => sum + i.current_stock * (i.cost_per_unit ?? 0),
    0,
  );

  const hasAlerts = outCount > 0 || lowCount > 0;

  const statusBadge = outCount > 0
    ? { label: 'Critical', cls: 'border-red-200 bg-red-100 text-red-700' }
    : lowCount > 0
    ? { label: 'Low stock', cls: 'border-amber-200 bg-amber-100 text-amber-700' }
    : { label: 'All good', cls: 'border-emerald-200 bg-emerald-100 text-emerald-700' };

  return (
    <Card
      className={cn(
        'rounded-2xl border-border bg-card shadow-none',
        hasAlerts && outCount > 0 && 'border-red-200',
        hasAlerts && outCount === 0 && 'border-amber-200',
      )}
    >
      <CardContent className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-background">
              <Package className="h-4 w-4 text-primary" />
            </span>
            <span className="text-sm font-semibold text-foreground">Inventory</span>
          </div>
          <Badge
            variant="outline"
            className={cn('rounded-full border text-xs font-semibold', statusBadge.cls)}
          >
            {hasAlerts
              ? <AlertTriangle className="mr-1 h-3 w-3" />
              : <CheckCircle2 className="mr-1 h-3 w-3" />}
            {statusBadge.label}
          </Badge>
        </div>

        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-4 w-32" />
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold tracking-tight text-foreground">
                {items.length}
              </span>
              <span className="text-xs text-muted-foreground">items tracked</span>
            </div>

            <div className="flex flex-wrap gap-2">
              {outCount > 0 && (
                <span className="text-xs font-semibold text-red-600">
                  {outCount} out of stock
                </span>
              )}
              {lowCount > 0 && (
                <span className="text-xs font-semibold text-amber-600">
                  {lowCount} low stock
                </span>
              )}
              {!hasAlerts && (
                <span className="text-xs text-muted-foreground">
                  No alerts
                </span>
              )}
            </div>

            <p className="text-xs text-muted-foreground">
              Est. value: <span className="font-semibold text-foreground">${totalValue.toFixed(2)}</span>
            </p>
          </div>
        )}

        <div className="mt-4">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 px-0 text-xs text-primary hover:bg-transparent hover:text-primary/80"
            asChild
          >
            <Link to="/inventory">
              View inventory <ArrowRight className="h-3 w-3" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
