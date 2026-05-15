import { Clock, BellRing, Smartphone, ListOrdered } from 'lucide-react';

const items = [
  {
    icon: Clock,
    title: 'AI Receptionist',
    description:
      'Your shop gets a browser-based AI receptionist for customer questions, queue joins, and appointment requests.',
  },
  {
    icon: BellRing,
    title: 'Owner Agent Workspace',
    description:
      'Owners can monitor approvals, queue activity, team updates, and day-to-day operations from one workspace.',
  },
  {
    icon: Smartphone,
    title: 'Mobile-First Experience',
    description:
      'Customers can join queues, view live progress, and book appointments directly from their phone browser.',
  },
  {
    icon: ListOrdered,
    title: 'Live Queue and Booking',
    description:
      'ZeroQwait supports live queue management, appointment booking flows, and service discovery across your shop pages.',
  },
];

export default function Content() {
  return (
    <div className="hidden md:flex flex-col gap-8 max-w-md self-center">
      <div className="flex items-center gap-2">
        <span className="text-4xl font-bold text-violet-400">ZeroQwait</span>
      </div>

      <div className="flex flex-col gap-6">
        {items.map((item, index) => {
          const Icon = item.icon;
          return (
            <div key={index} className="flex gap-3">
              <Icon className="h-5 w-5 mt-0.5 flex-shrink-0 text-violet-400" />
              <div>
                <p className="text-sm font-semibold text-white mb-0.5">{item.title}</p>
                <p className="text-sm text-white/60 leading-relaxed">{item.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
