import type { SVGProps } from "react";

const FlagFrame = ({ children, ...props }: SVGProps<SVGSVGElement>) => (
  <svg
    viewBox="0 0 24 24"
    aria-hidden="true"
    className="size-6 overflow-hidden rounded-full"
    {...props}
  >
    <clipPath id="flag-clip">
      <circle cx="12" cy="12" r="12" />
    </clipPath>
    <g clipPath="url(#flag-clip)">{children}</g>
  </svg>
);

export function ZeroQwaitLogo() {
  return (
    <svg
      viewBox="0 0 100 21"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="h-[21px] w-[100px]"
      aria-label="ZeroQwait"
    >
      <text
        x="0"
        y="18"
        fill="currentColor"
        fontFamily="Arial, sans-serif"
        fontWeight="bold"
        fontSize="18"
      >
        ZeroQwait
      </text>
    </svg>
  );
}

export function IndiaFlag() {
  return (
    <FlagFrame>
      <rect width="24" height="8" fill="#FF9933" />
      <rect y="8" width="24" height="8" fill="#FFFFFF" />
      <rect y="16" width="24" height="8" fill="#138808" />
      <circle cx="12" cy="12" r="3" fill="none" stroke="#000080" strokeWidth="1" />
      <circle cx="12" cy="12" r="0.75" fill="#000080" />
    </FlagFrame>
  );
}

export function UsaFlag() {
  const stripeHeight = 24 / 13;

  return (
    <FlagFrame>
      <rect width="24" height="24" fill="#FFFFFF" />
      {Array.from({ length: 7 }).map((_, index) => (
        <rect
          key={index}
          y={index * stripeHeight * 2}
          width="24"
          height={stripeHeight}
          fill="#B22234"
        />
      ))}
      <rect width="10.5" height="12.8" fill="#3C3B6E" />
      {Array.from({ length: 12 }).map((_, index) => (
        <circle
          key={index}
          cx={2 + (index % 4) * 2.1}
          cy={2 + Math.floor(index / 4) * 3}
          r="0.35"
          fill="#FFFFFF"
        />
      ))}
    </FlagFrame>
  );
}

export function BrazilFlag() {
  return (
    <FlagFrame>
      <rect width="24" height="24" fill="#009C3B" />
      <path d="M12 3.7 22 12 12 20.3 2 12 12 3.7Z" fill="#FFDF00" />
      <circle cx="12" cy="12" r="4.5" fill="#002776" />
      <path d="M7.8 10.9c3.3-.4 6.3.3 8.9 2" stroke="#FFFFFF" strokeWidth="1" />
    </FlagFrame>
  );
}

export function GlobeFlag() {
  return (
    <FlagFrame>
      <circle cx="12" cy="12" r="12" fill="#2563EB" />
      <path
        d="M6.2 5.6c2.9 1.3 5.5 1.4 8.2.1M4.2 12h15.6M6.2 18.4c2.9-1.3 5.5-1.4 8.2-.1"
        stroke="#A7F3D0"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
      <path
        d="M12 3.4c-2 2.2-3 5-3 8.6s1 6.4 3 8.6M12 3.4c2 2.2 3 5 3 8.6s-1 6.4-3 8.6"
        stroke="#A7F3D0"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </FlagFrame>
  );
}
