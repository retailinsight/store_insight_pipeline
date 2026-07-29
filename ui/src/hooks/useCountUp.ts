import { useState, useEffect, useRef } from "react";

export function useCountUp(target: string | undefined, duration = 1200, delay = 0) {
  const match = (target ?? "").match(/^([+-]?)(\d+(?:\.\d+)?)(.*)/);

  const sign = match?.[1] ?? "";
  const numericTarget = match ? parseFloat(match[2]) : 0;
  const suffix = match?.[3] ?? "";
  const decimals = match?.[2]?.includes(".") ? match[2].split(".")[1].length : 0;

  const [current, setCurrent] = useState(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    if (!match) return;

    const timeout = setTimeout(() => {
      const start = performance.now();

      const animate = (now: number) => {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        setCurrent(eased * numericTarget);

        if (progress < 1) {
          rafRef.current = requestAnimationFrame(animate);
        }
      };

      rafRef.current = requestAnimationFrame(animate);
    }, delay);

    return () => {
      clearTimeout(timeout);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [numericTarget, duration, delay]);

  if (!match) return target ?? "";

  return `${sign}${current.toFixed(decimals)}${suffix}`;
}
