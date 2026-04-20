import { useState, useEffect, useRef } from "react";

/**
 * Animates a number from 0 to a target value over a given duration.
 * Parses the target string to extract the numeric portion and suffix (e.g. "96.5%" → 96.5 + "%").
 */
export function useCountUp(target: string, duration = 1200, delay = 0) {
  const match = target.match(/^([+-]?)(\d+(?:\.\d+)?)(.*)/);
  if (!match) return target;

  const sign = match[1];
  const numericTarget = parseFloat(match[2]);
  const suffix = match[3];
  const decimals = match[2].includes(".") ? match[2].split(".")[1].length : 0;

  const [current, setCurrent] = useState(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    const timeout = setTimeout(() => {
      const start = performance.now();

      const animate = (now: number) => {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        // Ease-out cubic for a satisfying deceleration
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

  return `${sign}${current.toFixed(decimals)}${suffix}`;
}
