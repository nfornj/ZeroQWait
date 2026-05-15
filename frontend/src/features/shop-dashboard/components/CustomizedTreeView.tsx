import * as React from "react";
import { ChevronRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Color = "blue" | "green";

type TreeItem = {
  color?: Color;
  id: string;
  label: string;
  children?: TreeItem[];
};

const ITEMS: TreeItem[] = [
  {
    id: "1",
    label: "Website",
    children: [
      { id: "1.1", label: "Home", color: "green" },
      { id: "1.2", label: "Pricing", color: "green" },
      { id: "1.3", label: "About us", color: "green" },
      {
        id: "1.4",
        label: "Blog",
        children: [
          { id: "1.1.1", label: "Announcements", color: "blue" },
          { id: "1.1.2", label: "April lookahead", color: "blue" },
          { id: "1.1.3", label: "What's new", color: "blue" },
          { id: "1.1.4", label: "Meet the team", color: "blue" },
        ],
      },
    ],
  },
  {
    id: "2",
    label: "Store",
    children: [
      { id: "2.1", label: "All products", color: "green" },
      {
        id: "2.2",
        label: "Categories",
        children: [
          { id: "2.2.1", label: "Gadgets", color: "blue" },
          { id: "2.2.2", label: "Phones", color: "blue" },
          { id: "2.2.3", label: "Wearables", color: "blue" },
        ],
      },
      { id: "2.3", label: "Bestsellers", color: "green" },
      { id: "2.4", label: "Sales", color: "green" },
    ],
  },
  { id: "4", label: "Contact", color: "blue" },
  { id: "5", label: "Help", color: "blue" },
];

const dotClass: Record<Color, string> = {
  blue: "bg-primary",
  green: "bg-success",
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

export default function CustomizedTreeView() {
  const defaultExpanded = React.useMemo(() => new Set(["1", "1.4"]), []);

  return (
    <Card className="flex flex-grow flex-col gap-2">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Product tree</CardTitle>
      </CardHeader>
      <CardContent>
        <ul aria-label="pages" className="-mx-2 flex flex-col gap-1">
          {ITEMS.map((item) => (
            <TreeNode key={item.id} item={item} defaultExpanded={defaultExpanded} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
