const DAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export interface FormattedDateTime {
  date: string;
  time: string;
}

export function formatDateTime(date: Date): FormattedDateTime {
  const day = DAY_NAMES[date.getDay()];
  const d = date.getDate();
  const month = MONTH_NAMES[date.getMonth()];
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return {
    date: `${day}, ${d} ${month} ${year}`,
    time: `${hours}:${minutes}`,
  };
}

export function formatCurrency(amount: number): string {
  return (
    "£" +
    amount.toLocaleString("en-GB", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

export function calculateTotalCost(
  actions: ReadonlyArray<{ warning?: string }>,
): number {
  return actions.reduce((total, action) => {
    if (!action.warning) return total;
    const match = action.warning.match(/£([\d,]+\.?\d*)/);
    if (match) {
      return total + parseFloat(match[1].replace(/,/g, ""));
    }
    return total;
  }, 0);
}
