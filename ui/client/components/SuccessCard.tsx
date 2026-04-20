import { cn } from "@/lib/utils";

function TrendUpIcon() {
  return (
    <svg width="16" height="9" viewBox="0 0 20 11" fill="none">
      <path d="M18.3312 0H12.4906V1.66875H17.1514L10.8219 7.99833L5.8156 2.99207L0 8.80768L1.17981 9.98748L5.8156 5.35169L10.8219 10.3579L18.3312 2.84856V7.50939H20V1.66875C20 0.748436 19.2516 0 18.3312 0Z" fill="currentColor"/>
    </svg>
  );
}

function TrendDownIcon() {
  return (
    <svg width="16" height="9" viewBox="0 0 20 11" fill="none">
      <path d="M18.3312 2.84856V7.50939L10.8219 0L5.8156 5.00626L1.17981 0.370463L0 1.55027L5.8156 7.36587L10.8219 2.35962L17.1514 8.68919H12.4906V10.3579H18.3312C19.2516 10.3579 20 9.60951 20 8.68919V2.84856H18.3312Z" fill="currentColor"/>
    </svg>
  );
}

interface SuccessCardProps {
  title: string;
  trigger_types: string[];
  type: string;
  value: string;
  trend_direction: "up" | "down";
  trend: string;
  impact: string;
  isFirst?: boolean;
  isLast?: boolean;
}

export default function SuccessCard({
  title,
  trigger_types,
  type,
  value,
  trend_direction,
  trend,
  impact,
  isFirst,
  isLast,
}: SuccessCardProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 flex-1 bg-white dark:bg-white/5 p-4",
        // Vertical divider on desktop (left border on all but first)
        !isFirst && "md:border-l border-black/[0.10] dark:border-white/[0.10]",
        // Horizontal divider on mobile (top border on all but first)
        !isFirst && "border-t md:border-t-0 border-black/[0.10] dark:border-white/[0.10]"
      )}
    >
      {/* Trigger Types & Type Tags */}
      {(trigger_types.length > 0 || type) && (
        <div className="flex items-center gap-2 flex-wrap">
          {trigger_types.map((triggerType) => (
            <span
              key={triggerType}
              className="px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-dm-sans font-medium"
            >
              {triggerType}
            </span>
          ))}
          {type && (
            <span className="px-3 py-1 rounded-full bg-purple-100 text-purple-700 text-xs font-dm-sans font-medium">
              {type}
            </span>
          )}
        </div>
      )}

      {/* Title */}
      <h3 className="font-dm-sans font-bold text-base text-black dark:text-white leading-5">
        {title}
      </h3>

      {/* Value */}
      <div className="font-bebas text-2xl font-bold text-black dark:text-white">
        {value}
      </div>

      {/* Trend Tag */}
      <div className="flex items-center gap-1.5 px-3 py-1 rounded-full w-fit" style={{
        backgroundColor: trend_direction === "up" ? "#EDFAC2" : "#fee2e2",
      }}>
        <span className={cn(
          "text-black",
          trend_direction === "down" ? "text-red-700" : ""
        )}>
          {trend_direction === "up" ? <TrendUpIcon /> : <TrendDownIcon />}
        </span>
        <span className={cn(
          "font-dm-sans text-sm",
          trend_direction === "down" ? "text-red-700" : "text-black"
        )}>
          {trend}
        </span>
      </div>

      {/* Impact Statement */}
      <p className="font-dm-sans text-sm text-black dark:text-white/80 leading-5">
        {impact}
      </p>
    </div>
  );
}
