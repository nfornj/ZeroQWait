import { SearchIcon } from "lucide-react";

import { Input } from "@/components/ui/input";

export default function Search() {
  return (
    <div className="relative w-full md:w-[25ch]">
      <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input id="search" aria-label="search" placeholder="Search..." className="pl-9" />
    </div>
  );
}
