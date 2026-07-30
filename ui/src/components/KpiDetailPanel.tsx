import { KpiData } from "@/models";
import {
  TrendUpIcon,
  TrendDownIcon,
  AvailabilityIcon,
  WasteIcon,
  ChartBarIcon,
  DocumentIcon,
  TrendingIcon,
  GridIcon,
  ClockIcon,
  TargetIcon,
  CalendarIcon,
  LightBulbIcon,
  CloseIcon,
} from "@/components/icons";

interface KpiDetailPanelProps {
  kpiData: KpiData;
  onClose: () => void;
}

export default function KpiDetailPanel({ kpiData, onClose }: KpiDetailPanelProps) {
  const details = kpiData.details;

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
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white dark:bg-gray-900 shadow-2xl flex flex-col overflow-hidden animate-slide-from-right">
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
              <CloseIcon />
            </button>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-bebas text-5xl text-brand-primary leading-none" data-testid={`kpi-drawer-${kpiType}-value`}>
              {kpiData.value}
            </span>
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full ${kpiData.trendDirection === "up" ? 'bg-app-lime' : 'bg-app-pink'}`}>
              <span className="text-black">
                {kpiData.trendDirection === "up" ? <TrendUpIcon /> : <TrendDownIcon />}
              </span>
              <span className="font-dm-sans text-sm text-black">
                {kpiData.trend}
              </span>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">

          {kpiType === "availability" && details && (
            <>
              {/* Key Metrics - from performanceBreakdown */}
              {details.performanceBreakdown && (
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
                    {Object.entries(details.performanceBreakdown).map(([key, value], i) => (
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

              {details.topDrivers && details.topDrivers.length > 0 && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <TrendingIcon />
                    </span>
                    Top Drivers
                  </h3>
                  <div className="flex flex-col gap-3">
                    {details.topDrivers.map((driver, i) => (
                      <div key={i} className="flex flex-col gap-1 pb-3 border-b border-app-neutral-400 dark:border-white/10 last:border-b-0">
                        <div className="flex items-center gap-2">
                          <span className={`font-bebas text-xl ${driver.trendDirection === "up" ? 'text-green-600' : 'text-red-600'}`}>
                            {driver.trend}
                          </span>
                        </div>
                        <p className="font-dm-sans font-bold text-sm text-black dark:text-white">
                          {driver.driver}
                        </p>
                        {driver.subcategory && (
                          <p className="font-dm-sans text-xs text-black/70 dark:text-white/70">
                            Subcategory: {driver.subcategory}
                          </p>
                        )}
                        {driver.when && (
                          <p className="font-dm-sans text-xs text-black/60 dark:text-white/60">
                            When: {driver.when}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Performance by Category */}
              {details.categoryPerformance && details.categoryPerformance.length > 0 && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <GridIcon />
                    </span>
                    Performance by Category
                  </h3>
                  <div className="flex flex-col gap-4">
                    {details.categoryPerformance.map((category, i) => {
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
              {details.timeOfDayAnalysis && details.timeOfDayAnalysis.length > 0 && (
                <div className="flex flex-col gap-4">
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
                        {details.timeOfDayAnalysis.map((row, i) => {
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
              {/* Key Metrics - from performanceBreakdown */}
              {details.performanceBreakdown && (
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
                    {Object.entries(details.performanceBreakdown).map(([key, value], i) => (
                      <div key={i} className="flex flex-col gap-1">
                        <div className="flex items-center justify-between">
                          <span className="font-dm-sans font-bold text-sm text-black dark:text-white" data-testid="kpi-drawer-key-metric-name">
                            {key.replace(/_/g, " ")}
                          </span>
                          <span className="font-bebas text-2xl text-black dark:text-white" data-testid="kpi-drawer-key-metric-value">
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
                <div className="flex flex-col gap-3 rounded-2xl border border-app-neutral-400 bg-app-neutral-100 dark:bg-white/5 dark:border-white/10 p-4" data-testid="kpi-drawer-summary">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <DocumentIcon />
                    </span>
                    Summary
                  </h3>
                  <p className="font-dm-sans text-sm text-black dark:text-white/80 leading-6" data-testid="kpi-drawer-summary-text">
                    {details.summary}
                  </p>
                </div>
              )}

              {/* Top Drivers */}
              {details.topDrivers && details.topDrivers.length > 0 && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <TrendingIcon />
                    </span>
                    Top Drivers
                  </h3>
                  <div className="flex flex-col gap-3">
                    {details.topDrivers.map((driver, i) => (
                      <div key={i} className="flex flex-col gap-1 pb-3 border-b border-app-neutral-400 dark:border-white/10 last:border-b-0">
                        <div className="flex items-center gap-2">
                          <span className={`font-bebas text-xl ${driver.trendDirection === "up" ? 'text-green-600' : 'text-red-600'}`}>
                            {driver.trend}
                          </span>
                        </div>
                        <p className="font-dm-sans font-bold text-sm text-black dark:text-white" data-testid="kpi-drawer-driver-name">
                          {driver.driver}
                        </p>
                        {driver.subcategory && (
                          <p className="font-dm-sans text-xs text-black/70 dark:text-white/70">
                            Subcategory: {driver.subcategory}
                          </p>
                        )}
                        {driver.when && (
                          <p className="font-dm-sans text-xs text-black/60 dark:text-white/60">
                            When: {driver.when}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Performance by Category */}
              {details.categoryPerformance && details.categoryPerformance.length > 0 && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <GridIcon />
                    </span>
                    Performance by Category
                  </h3>
                  <div className="flex flex-col gap-4">
                    {details.categoryPerformance.map((category, i) => {
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
                      <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full ${details.target.trendDirection === "up" ? "bg-app-lime" : "bg-app-pink"} self-start`}>
                        <span className="text-black">
                          {details.target.trendDirection === "up" ? <TrendUpIcon /> : <TrendDownIcon />}
                        </span>
                        <span className="font-dm-sans text-sm text-black">
                          {details.target.trend}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Previous Average Panel */}
                {details.previousAverage && (
                  <div className="flex flex-col gap-3 rounded-2xl border border-app-neutral-400 bg-app-neutral-100 dark:bg-white/5 dark:border-white/10 p-4">
                    <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                        <CalendarIcon />
                      </span>
                      Previous Average
                    </h3>
                    <div className="flex flex-col gap-2">
                      <span className="font-bebas text-3xl text-black dark:text-white">
                        {details.previousAverage.value}
                      </span>
                      <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full ${details.previousAverage.trendDirection === "up" ? "bg-app-lime" : "bg-app-pink"} self-start`}>
                        <span className="text-black">
                          {details.previousAverage.trendDirection === "up" ? <TrendUpIcon /> : <TrendDownIcon />}
                        </span>
                        <span className="font-dm-sans text-sm text-black">
                          {details.previousAverage.trend}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Performance Breakdown */}
              {details.performanceBreakdown && (
                <div className="flex flex-col gap-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <ChartBarIcon />
                    </span>
                    Performance Breakdown
                  </h3>
                  <div className="flex flex-col gap-4">
                    {Object.entries(details.performanceBreakdown).map(([key, value], i) => (
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
              {details.keyInsights && details.keyInsights.length > 0 && (
                <div className="flex flex-col gap-3 rounded-2xl border border-app-neutral-400 bg-app-neutral-100 dark:bg-white/5 dark:border-white/10 p-4">
                  <h3 className="font-bebas text-2xl text-black/50 dark:text-white/50 flex items-center gap-2">
                    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-brand-primary/20 text-brand-primary">
                      <LightBulbIcon />
                    </span>
                    Key Insights
                  </h3>
                  <ul className="flex flex-col gap-2">
                    {details.keyInsights.map((insight, i) => (
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
