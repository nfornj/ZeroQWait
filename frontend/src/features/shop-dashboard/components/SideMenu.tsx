import SelectContent from './SelectContent';
import MenuContent from './MenuContent';
import OwnerAccountPanel from './OwnerAccountPanel';

export const SIDEBAR_WIDTH = 240;

export default function SideMenu() {
  return (
    <aside
      className="hidden md:flex flex-col flex-shrink-0 border-r border-border bg-background"
      style={{ width: SIDEBAR_WIDTH }}
    >
      {/* Shop identity */}
      <div className="border-b border-border px-3 py-1">
        <SelectContent />
      </div>

      {/* Nav items */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <MenuContent />
      </div>

      {/* Account panel */}
      <div className="border-t border-border p-3">
        <OwnerAccountPanel />
      </div>
    </aside>
  );
}
