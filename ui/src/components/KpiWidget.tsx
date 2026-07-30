import { cn } from "@/lib/utils";
import { useCountUp } from "@/hooks/useCountUp";
import {
  TrendUpIcon,
  TrendDownIcon,
  AvailabilityIcon,
  WasteIcon,
} from "@/components/icons";

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
