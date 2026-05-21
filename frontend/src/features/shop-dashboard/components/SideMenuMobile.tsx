import { Sheet, SheetContent } from '@/components/ui/sheet';
import { Separator } from '@/components/ui/separator';
import MenuContent from './MenuContent';
import OwnerAccountPanel from './OwnerAccountPanel';
import SelectContent from './SelectContent';

interface SideMenuMobileProps {
  open: boolean | undefined;
  toggleDrawer: (newOpen: boolean) => () => void;
}

export default function SideMenuMobile({ open, toggleDrawer }: SideMenuMobileProps) {
  return (
    <Sheet open={open} onOpenChange={(v) => toggleDrawer(v)()}>
      <SheetContent side="right" className="flex w-[260px] flex-col p-0">
        <div className="border-b border-border px-3 py-1">
          <SelectContent />
        </div>
        <div className="flex flex-1 flex-col overflow-hidden">
          <MenuContent />
        </div>
        <Separator />
        <div className="p-3">
          <OwnerAccountPanel />
        </div>
      </SheetContent>
    </Sheet>
  );
}
