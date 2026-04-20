import { cn } from "@/lib/utils";
import { useCountUp } from "@/hooks/useCountUp";

interface KpiWidgetProps {
  label: string;
  value: string;
  change: string;
  changeLabel: string;
  trend: "up" | "down";
  clusterAvg: string;
  icon?: "availability" | "waste";
  animationDelay?: number;
  onClick?: () => void;
}

function TrendUpIcon() {
  return (
    <svg width="18" height="10" viewBox="0 0 20 11" fill="none">
      <path d="M18.3312 0H12.4906V1.66875H17.1514L10.8219 7.99833L5.8156 2.99207L0 8.80768L1.17981 9.98748L5.8156 5.35169L10.8219 10.3579L18.3312 2.84856V7.50939H20V1.66875C20 0.748436 19.2516 0 18.3312 0Z" fill="currentColor"/>
    </svg>
  );
}

function TrendDownIcon() {
  return (
    <svg width="18" height="10" viewBox="0 0 20 11" fill="none">
      <path d="M18.3312 2.84856V7.50939L10.8219 0L5.8156 5.00626L1.17981 0.370463L0 1.55027L5.8156 7.36587L10.8219 2.35962L17.1514 8.68919H12.4906V10.3579H18.3312C19.2516 10.3579 20 9.60951 20 8.68919V2.84856H18.3312Z" fill="currentColor"/>
    </svg>
  );
}

function AvailabilityIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <g clipPath="url(#avail-clip)">
        <path d="M19.6466 5.35753L18.0549 2.71503L9.99991 0.0300293L1.94491 2.71503L0.368247 5.33086C-0.0275864 5.99086 -0.10092 6.78253 0.165747 7.50336C0.42408 8.20253 0.96908 8.74336 1.66575 8.99753L1.65908 17.2009L9.99241 19.9784L18.3257 17.2009L18.3324 8.99753C19.0374 8.75086 19.5882 8.2092 19.8482 7.50753C20.1124 6.79336 20.0391 6.01003 19.6466 5.35586V5.35753ZM14.8657 3.4092L10.0066 5.03086L5.14575 3.40503L9.99991 1.7867L14.8657 3.4092ZM1.79658 6.19003L2.87325 4.40253L8.74658 6.3667L7.47241 8.49086C7.27325 8.82253 6.85991 8.97503 6.49491 8.85253L2.26075 7.4417C2.01325 7.3592 1.81908 7.1717 1.72825 6.9267C1.63825 6.68253 1.66241 6.41253 1.79658 6.19003ZM3.33241 9.55503L5.96825 10.4334C7.08741 10.8067 8.29491 10.36 8.90241 9.34836L9.16575 8.91003L9.16158 17.9459L3.32825 16.0017L3.33325 9.55586L3.33241 9.55503ZM10.8274 17.945L10.8316 8.9042L11.0974 9.34753C11.5607 10.1209 12.3741 10.5634 13.2316 10.5634C13.4974 10.5634 13.7674 10.5209 14.0316 10.4325L16.6657 9.55503L16.6607 16L10.8274 17.945ZM18.2857 6.9317C18.1982 7.1692 18.0099 7.35086 17.7699 7.43086L13.5049 8.85253C13.1399 8.97503 12.7266 8.82336 12.5274 8.49086L11.2557 6.3717L17.1316 4.41086L18.2191 6.2167C18.3491 6.43336 18.3741 6.6942 18.2857 6.9317Z" fill="#577DF7"/>
      </g>
      <defs>
        <clipPath id="avail-clip">
          <rect width="20" height="20" fill="white"/>
        </clipPath>
      </defs>
    </svg>
  );
}

function WasteIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M18.3337 3.33333H14.167V1.66667C14.167 1.22464 13.9914 0.800716 13.6788 0.488155C13.3663 0.175595 12.9424 0 12.5003 0L7.50033 0C7.0583 0 6.63437 0.175595 6.32181 0.488155C6.00925 0.800716 5.83366 1.22464 5.83366 1.66667V3.33333H1.66699V5H3.33366V17.5C3.33366 18.163 3.59705 18.7989 4.06589 19.2678C4.53473 19.7366 5.17062 20 5.83366 20H14.167C14.83 20 15.4659 19.7366 15.9348 19.2678C16.4036 18.7989 16.667 18.163 16.667 17.5V5H18.3337V3.33333ZM7.50033 1.66667H12.5003V3.33333H7.50033V1.66667ZM15.0003 17.5C15.0003 17.721 14.9125 17.933 14.7562 18.0893C14.6 18.2455 14.388 18.3333 14.167 18.3333H5.83366C5.61264 18.3333 5.40068 18.2455 5.2444 18.0893C5.08812 17.933 5.00033 17.721 5.00033 17.5V5H15.0003V17.5Z" fill="#577DF7"/>
      <path d="M9.16667 8.33325H7.5V14.9999H9.16667V8.33325Z" fill="#577DF7"/>
      <path d="M12.5007 8.33325H10.834V14.9999H12.5007V8.33325Z" fill="#577DF7"/>
    </svg>
  );
}

export default function KpiWidget({
  label,
  value,
  change,
  changeLabel,
  trend,
  clusterAvg,
  icon,
  animationDelay = 0,
  onClick,
}: KpiWidgetProps) {
  const isPositive = trend === "up";
  const tagBg = isPositive ? "bg-app-lime" : "bg-app-pink";
  const animatedValue = useCountUp(value, 1200, animationDelay);
  const animatedChange = useCountUp(change, 1000, animationDelay + 400);
  const animatedClusterAvg = useCountUp(clusterAvg, 1000, animationDelay + 600);

  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 flex-1 rounded-2xl bg-white dark:bg-white/10 shadow-kpi p-4",
        "animate-kpi-in opacity-0",
        onClick && "cursor-pointer hover:shadow-action transition-shadow duration-200"
      )}
      style={{ animationDelay: `${animationDelay}ms` }}
      onClick={onClick}
    >
      {/* Label row */}
      <div className="flex items-center justify-between">
        <span className="font-bebas text-base tracking-wide text-brand-secondary-300 dark:text-white/50">
          {label}
        </span>
        {icon === "availability" && <AvailabilityIcon />}
        {icon === "waste" && <WasteIcon />}
      </div>

      {/* Score row */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="font-bebas text-4xl text-black dark:text-white leading-none tabular-nums">
          {animatedValue}
        </span>
        <div className={cn("flex items-center gap-1.5 px-3 py-1 rounded-full", tagBg)}>
          <span className="text-black">
            {isPositive ? <TrendUpIcon /> : <TrendDownIcon />}
          </span>
          <span className="font-dm-sans text-sm text-black">
            {animatedChange}{changeLabel && ` ${changeLabel}`}
          </span>
        </div>
      </div>

      {/* Cluster avg */}
      <p className="font-dm-sans text-xs text-black dark:text-white/70">
        cluster avg: {animatedClusterAvg}
      </p>
    </div>
  );
}
