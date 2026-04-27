import { KpiData } from "@shared/api";

interface KpiDetailPanelProps {
  kpiData: KpiData;
  onClose: () => void;
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

// Section icons
function ChartBarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M2 2v16h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M6 14v-4M10 14V8M14 14v-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function DocumentIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M4 4a2 2 0 012-2h4.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M7 10h6M7 13h6M7 7h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function TrendingIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M3 14l4-4 3 3 7-7m0 0h-5m5 0v5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function GridIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M3 3h6v6H3V3zm0 8h6v6H3v-6zm8-8h6v6h-6V3zm0 8h6v6h-6v-6z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M10 6v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function TargetIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="10" cy="10" r="4" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="10" cy="10" r="1.5" fill="currentColor"/>
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <rect x="3" y="4" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M3 8h14M7 2v4M13 2v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function LightBulbIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M10 2a6 6 0 014 10.5V14a2 2 0 01-2 2h-4a2 2 0 01-2-2v-1.5A6 6 0 0110 2z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M8 16h4M10 2v1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export default function KpiDetailPanel({ kpiData, onClose }: KpiDetailPanelProps) {
  const details = kpiData.details;

  // Determine KPI type
  const kpiType = kpiData.name.toLowerCase().includes("availability")
    ? "availability"
    : kpiData.name.toLowerCase().includes("waste")
    ? "waste"
    : "overall";

  // Helper function to get color class based on performance
  const getPerformanceColor = (percentage: number) => {
    if (percentage >= 93) return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    if (percentage >= 90) return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400";
    return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
  };

  return (
    <>
      {/* Backdrop with blur */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Slide-in panel */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white dark:bg-gray-900 shadow-2xl flex flex-col overflow-hidden animate-slide-from-right" data-testid={`kpi-drawer-${kpiType}`}>
        {/* Panel header */}
        <div className="flex flex-col gap-3 px-6 py-4 border-b border-app-neutral-400 dark:border-white/10 shrink-0 bg-gray-200 dark:bg-gray-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {kpiType === "availability" && <AvailabilityIcon />}
              {kpiType === "waste" && <WasteIcon />}
              <span className="font-bebas text-lg tracking-wide text-brand-secondary dark:text-white">
                {kpiData.name}
              </span>
            </div>
            <button
              onClick={onClose}
              className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-gray-100 dark:hover:bg-white/10 transition-colors text-gray-500 dark:text-white/60"
              data-testid="kpi-drawer-close"
            >
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
                <path d="M17.805 2.197a.75.75 0 00-1.061 0L10 8.94 3.256 2.197a.75.75 0 00-1.061 1.06L8.94 10l-6.744 6.743a.75.75 0 001.06 1.061L10 11.06l6.744 6.744a.75.75 0 001.06-1.06L11.06 10l6.744-6.744a.75.75 0 000-1.06z" fill="currentColor"/>
              </svg>
            </button>
          </div>

          {/* Score and trend badge */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-bebas text-5xl text-brand-primary leading-none" data-testid={`kpi-drawer-${kpiType}-value`}>
              {kpiData.value}
            </span>
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full ${kpiData.trend_direction === "up" ? 'bg-app-lime' : 'bg-app-pink'}`} data-testid={`kpi-drawer-${kpiType}-trend`}>
              <span className="text-black">
                {kpiData.trend_direction === "up" ? <TrendUpIcon /> : <TrendDownIcon />}
              </span>
              <span className="font-dm-sans text-sm text-black">
                {kpiData.trend}
              </span>
            </div>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">

          {/* Availability-specific content */}
          {kpiType === "availability" && details && (
            <>
              {/* Key Metrics - from performance_breakdown */}
              {details.performance_breakdown && (
                <div className="flex flex-col gap-4" data-testid="kpi-drawer-key-metrics">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <ChartBarIcon />
                    </span>
                    Key Metrics
                    <span className="font-dm-sans text-xs text-black/60 dark:text-white/60">
                      (Last 7 Days)
                    </span>
                  </h3>
                  <div className="flex flex-col gap-4">
                    {Object.entries(details.performance_breakdown).map(([key, value], i) => (
                      <div key={i} className="flex flex-col gap-1">
                        <div className="flex items-center justify-between">
                          <span className="font-dm-sans font-bold text-sm text-black dark:text-white">
                            {key.replace(/_/g, " ")}
                          </span>
                          <span className="font-bebas text-2xl text-black dark:text-white">
                            {String(value)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Summary */}
              {details.summary && (
                <div className="flex flex-col gap-3 rounded-2xl border border-app-neutral-400 bg-app-neutral-100 dark:bg-white/5 dark:border-white/10 p-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <DocumentIcon />
                    </span>
                    Summary
                  </h3>
                  <p className="font-dm-sans text-sm text-black dark:text-white/80 leading-6">
                    {details.summary}
                  </p>
                </div>
              )}

              {/* Top Drivers */}
              {details.top_drivers && details.top_drivers.length > 0 && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <TrendingIcon />
                    </span>
                    Top Drivers
                  </h3>
                  <div className="flex flex-col gap-3">
                    {details.top_drivers.map((driver, i) => (
                      <div key={i} className="flex flex-col gap-1 pb-3 border-b border-app-neutral-400 dark:border-white/10 last:border-b-0">
                        <div className="flex items-center gap-2">
                          <span className={`font-bebas text-xl ${driver.trend_direction === "up" ? 'text-green-600' : 'text-red-600'}`}>
                            {driver.trend}
                          </span>
                        </div>
                        <p className="font-dm-sans font-bold text-sm text-black dark:text-white">
                          {driver.driver}
                        </p>
                        {driver.Subcategory && (
                          <p className="font-dm-sans text-xs text-black/70 dark:text-white/70">
                            Subcategory: {driver.Subcategory}
                          </p>
                        )}
                        {driver.When && (
                          <p className="font-dm-sans text-xs text-black/60 dark:text-white/60">
                            When: {driver.When}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Performance by Category */}
              {details.category_performance && details.category_performance.length > 0 && (
                <div className="flex flex-col gap-4" data-testid="kpi-drawer-performance-by-category">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <GridIcon />
                    </span>
                    Performance by Category
                  </h3>
                  <div className="flex flex-col gap-4">
                    {details.category_performance.map((category, i) => {
                      const perfValue = parseFloat(category.performance);
                      return (
                        <div key={i} className="flex flex-col gap-2" data-testid="kpi-drawer-category-row">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-dm-sans text-sm text-black dark:text-white" data-testid="kpi-drawer-category-name">
                                {category.category}
                              </span>
                              {category.warning && (
                                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0">
                                  <path d="M8 1.333L1.333 14h13.334L8 1.333z" fill="#DC2626"/>
                                  <path d="M8 6v3.333M8 11h.007" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                                </svg>
                              )}
                            </div>
                            <span className={`font-bebas text-xl ${category.warning ? 'text-red-600' : 'text-black dark:text-white'}`} data-testid="kpi-drawer-category-value">
                              {category.performance}
                            </span>
                          </div>
                          <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-1000 ease-out ${
                                category.warning ? 'bg-red-600' : 'bg-brand-primary'
                              }`}
                              style={{
                                width: `${perfValue}%`,
                                animation: `slideInFromLeft 1s ease-out ${i * 0.1}s both`
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Performance by Time of Day */}
              {details.time_of_day_analysis && details.time_of_day_analysis.length > 0 && (
                <div className="flex flex-col gap-4" data-testid="kpi-drawer-performance-by-time">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <ClockIcon />
                    </span>
                    Performance by Time of Day
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse">
                      <thead>
                        <tr className="border-b border-app-neutral-400 dark:border-white/10">
                          <th className="text-left py-3 px-2 font-dm-sans font-bold text-xs text-black dark:text-white">
                            Day
                          </th>
                          <th className="text-center py-3 px-2 font-dm-sans font-bold text-xs text-black dark:text-white">
                            Morning<br/><span className="font-normal text-[10px] text-black/60 dark:text-white/60">(6AM-12PM)</span>
                          </th>
                          <th className="text-center py-3 px-2 font-dm-sans font-bold text-xs text-black dark:text-white">
                            Afternoon<br/><span className="font-normal text-[10px] text-black/60 dark:text-white/60">(12PM-6PM)</span>
                          </th>
                          <th className="text-center py-3 px-2 font-dm-sans font-bold text-xs text-black dark:text-white">
                            Evening<br/><span className="font-normal text-[10px] text-black/60 dark:text-white/60">(6PM-Close)</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {details.time_of_day_analysis.map((row, i) => {
                          const dayKey = row["day:"] || "";
                          return (
                            <tr key={i} className="border-b border-app-neutral-400/50 dark:border-white/5 last:border-b-0" data-testid="kpi-drawer-time-row">
                              <td className="py-3 px-2 font-dm-sans text-sm text-black dark:text-white" data-testid="kpi-drawer-time-day">
                                {dayKey}
                              </td>
                              {row.performance.map((perf, pi) => {
                                const timePeriod = pi === 0 ? "morning" : pi === 1 ? "afternoon" : "evening";
                                return (
                                  <td key={pi} className="py-3 px-2 text-center" data-testid={`kpi-drawer-time-${timePeriod}`}>
                                    <span className={`inline-block px-3 py-1 rounded-full font-dm-sans font-medium text-xs ${getPerformanceColor(parseFloat(perf.performance))}`}>
                                      {perf.performance}
                                    </span>
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}

          {/* waste specific content */}
          {kpiType === "waste" && details && (
            <>
              {/* Key Metrics - from performance_breakdown */}
              {details.performance_breakdown && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <ChartBarIcon />
                    </span>
                    Key Metrics
                    <span className="font-dm-sans text-xs text-black/60 dark:text-white/60">
                      (Last 7 Days)
                    </span>
                  </h3>
                  <div className="flex flex-col gap-4">
                    {Object.entries(details.performance_breakdown).map(([key, value], i) => (
                      <div key={i} className="flex flex-col gap-1">
                        <div className="flex items-center justify-between">
                          <span className="font-dm-sans font-bold text-sm text-black dark:text-white">
                            {key.replace(/_/g, " ")}
                          </span>
                          <span className="font-bebas text-2xl text-black dark:text-white">
                            {String(value)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Summary */}
              {details.summary && (
                <div className="flex flex-col gap-3 rounded-2xl border border-app-neutral-400 bg-app-neutral-100 dark:bg-white/5 dark:border-white/10 p-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <DocumentIcon />
                    </span>
                    Summary
                  </h3>
                  <p className="font-dm-sans text-sm text-black dark:text-white/80 leading-6">
                    {details.summary}
                  </p>
                </div>
              )}

              {/* Top Drivers */}
              {details.top_drivers && details.top_drivers.length > 0 && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <TrendingIcon />
                    </span>
                    Top Drivers
                  </h3>
                  <div className="flex flex-col gap-3">
                    {details.top_drivers.map((driver, i) => (
                      <div key={i} className="flex flex-col gap-1 pb-3 border-b border-app-neutral-400 dark:border-white/10 last:border-b-0">
                        <div className="flex items-center gap-2">
                          <span className={`font-bebas text-xl ${driver.trend_direction === "up" ? 'text-green-600' : 'text-red-600'}`}>
                            {driver.trend}
                          </span>
                        </div>
                        <p className="font-dm-sans font-bold text-sm text-black dark:text-white">
                          {driver.driver}
                        </p>
                        {driver.Subcategory && (
                          <p className="font-dm-sans text-xs text-black/70 dark:text-white/70">
                            Subcategory: {driver.Subcategory}
                          </p>
                        )}
                        {driver.When && (
                          <p className="font-dm-sans text-xs text-black/60 dark:text-white/60">
                            When: {driver.When}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Performance by Category */}
              {details.category_performance && details.category_performance.length > 0 && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <GridIcon />
                    </span>
                    Performance by Category
                  </h3>
                  <div className="flex flex-col gap-4">
                    {details.category_performance.map((category, i) => {
                      const perfValue = parseFloat(category.performance);
                      return (
                        <div key={i} className="flex flex-col gap-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-dm-sans text-sm text-black dark:text-white">
                                {category.category}
                              </span>
                              {category.warning && (
                                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0">
                                  <path d="M8 1.333L1.333 14h13.334L8 1.333z" fill="#DC2626"/>
                                  <path d="M8 6v3.333M8 11h.007" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                                </svg>
                              )}
                            </div>
                            <span className={`font-bebas text-xl ${category.warning ? 'text-red-600' : 'text-black dark:text-white'}`}>
                              {category.performance}
                            </span>
                          </div>
                          <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-1000 ease-out ${
                                category.warning ? 'bg-red-600' : 'bg-brand-primary'
                              }`}
                              style={{
                                width: `${perfValue}%`,
                                animation: `slideInFromLeft 1s ease-out ${i * 0.1}s both`
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}

          {/* overall specific content */}
          {kpiType === "overall" && details && (
            <>
              {/* Target and Previous Average Panels */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Target Panel */}
                {details.target && (
                  <div className="flex flex-col gap-3 rounded-2xl border border-app-neutral-400 bg-app-neutral-100 dark:bg-white/5 dark:border-white/10 p-4">
                    <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                        <TargetIcon />
                      </span>
                      Target
                    </h3>
                    <div className="flex flex-col gap-2">
                      <span className="font-bebas text-3xl text-black dark:text-white">
                        {details.target.value}
                      </span>
                      <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full ${details.target.trend_direction === "up" ? "bg-app-lime" : "bg-app-pink"} self-start`}>
                        <span className="text-black">
                          {details.target.trend_direction === "up" ? <TrendUpIcon /> : <TrendDownIcon />}
                        </span>
                        <span className="font-dm-sans text-sm text-black">
                          {details.target.trend}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Previous Average Panel */}
                {details.previous_average && (
                  <div className="flex flex-col gap-3 rounded-2xl border border-app-neutral-400 bg-app-neutral-100 dark:bg-white/5 dark:border-white/10 p-4">
                    <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                        <CalendarIcon />
                      </span>
                      Previous Average
                    </h3>
                    <div className="flex flex-col gap-2">
                      <span className="font-bebas text-3xl text-black dark:text-white">
                        {details.previous_average.value}
                      </span>
                      <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full ${details.previous_average.trend_direction === "up" ? "bg-app-lime" : "bg-app-pink"} self-start`}>
                        <span className="text-black">
                          {details.previous_average.trend_direction === "up" ? <TrendUpIcon /> : <TrendDownIcon />}
                        </span>
                        <span className="font-dm-sans text-sm text-black">
                          {details.previous_average.trend}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Performance Breakdown */}
              {details.performance_breakdown && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <ChartBarIcon />
                    </span>
                    Performance Breakdown
                  </h3>
                  <div className="flex flex-col gap-4">
                    {Object.entries(details.performance_breakdown).map(([key, value], i) => (
                      <div key={i} className="flex items-center justify-between">
                        <span className="font-dm-sans text-sm text-black dark:text-white">
                          {key.replace(/_/g, " ")}
                        </span>
                        <span className="font-bebas text-2xl text-black dark:text-white">
                          {String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Key Insights */}
              {details.Key_insights && details.Key_insights.length > 0 && (
                <div className="flex flex-col gap-3 rounded-2xl border border-app-neutral-400 bg-app-neutral-100 dark:bg-white/5 dark:border-white/10 p-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <LightBulbIcon />
                    </span>
                    Key Insights
                  </h3>
                  <ul className="flex flex-col gap-2">
                    {details.Key_insights.map((insight, i) => (
                      <li key={i} className="flex items-start gap-2 font-dm-sans text-sm text-black dark:text-white/80 leading-6">
                        <span className="mt-0.5 shrink-0">{i + 1}.</span>
                        <span>{insight}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
