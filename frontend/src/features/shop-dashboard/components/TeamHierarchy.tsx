import * as React from "react";
import { ChevronRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import api from "../../../services/api";
import { useShop } from "../../../contexts/ShopContext";

type Color = "blue" | "green" | "red";

type TreeItem = {
  color?: Color;
  id: string;
  label: string;
  children?: TreeItem[];
};

const dotClass: Record<Color, string> = {
  blue: "bg-primary",
  green: "bg-success",
  red: "bg-destructive",
};

function TreeNode({
  item,
  level = 0,
  defaultExpanded,
}: {
  item: TreeItem;
  level?: number;
  defaultExpanded: Set<string>;
}) {
  const hasChildren = Boolean(item.children?.length);
  const [expanded, setExpanded] = React.useState(defaultExpanded.has(item.id));

  return (
    <li>
      <button
        type="button"
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-accent"
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={() => hasChildren && setExpanded((value) => !value)}
      >
        {hasChildren ? (
          <ChevronRight className={cn("size-4 transition-transform", expanded && "rotate-90")} />
        ) : (
          <span className="size-4" />
        )}
        {item.color && <span className={cn("size-1.5 rounded-full", dotClass[item.color])} />}
        <span className="truncate">{item.label}</span>
      </button>
      {hasChildren && expanded && (
        <ul className="mt-1 flex flex-col gap-1">
          {item.children?.map((child) => (
            <TreeNode key={child.id} item={child} level={level + 1} defaultExpanded={defaultExpanded} />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function TeamHierarchy() {
  const { shop } = useShop();
  const [items, setItems] = React.useState<TreeItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const defaultExpanded = React.useMemo(() => new Set(["managers", "employees"]), []);

  React.useEffect(() => {
    const fetchTeam = async () => {
      if (!shop) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const empResponse = await api.get(`/shops/${shop.id}/employees`);
        const employees = empResponse.data;
        const managers = employees.filter((employee: any) => employee.user.role === "manager");
        const regularEmployees = employees.filter((employee: any) => employee.user.role === "employee");

        const tree: TreeItem[] = [
          {
            id: "owner",
            label: "Owner (You)",
            color: "blue",
            children: [],
          },
        ];

        if (managers.length > 0) {
          tree.push({
            id: "managers",
            label: "Managers",
            children: managers.map((manager: any) => ({
              id: `m-${manager.user.id}`,
              label: manager.user.username,
              color: "green",
            })),
          });
        }

        if (regularEmployees.length > 0) {
          tree.push({
            id: "employees",
            label: "Employees",
            children: regularEmployees.map((employee: any) => ({
              id: `e-${employee.user.id}`,
              label: employee.user.username,
              color: "green",
            })),
          });
        }

        setItems(tree);
      } catch (err) {
        console.error("Failed to fetch team hierarchy", err);
      } finally {
        setLoading(false);
      }
    };

    fetchTeam();
  }, [shop]);

  return (
    <Card className="flex flex-grow flex-col gap-2 glass">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Team Hierarchy</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-4/5" />
            <Skeleton className="h-8 w-3/5" />
          </div>
        ) : (
          <ul aria-label="team hierarchy" className="-mx-2 flex flex-col gap-1">
            {items.map((item) => (
              <TreeNode key={item.id} item={item} defaultExpanded={defaultExpanded} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
