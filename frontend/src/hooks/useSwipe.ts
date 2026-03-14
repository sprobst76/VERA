import { useRef, useCallback } from "react";

interface SwipeHandlers {
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  threshold?: number; // px, default 60
}

/**
 * Returns touch event handlers to detect horizontal swipes.
 * Usage: <div {...swipeHandlers}>...</div>
 */
export function useSwipe({ onSwipeLeft, onSwipeRight, threshold = 60 }: SwipeHandlers) {
  const startX = useRef<number | null>(null);
  const startY = useRef<number | null>(null);

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    startX.current = e.touches[0].clientX;
    startY.current = e.touches[0].clientY;
  }, []);

  const onTouchEnd = useCallback((e: React.TouchEvent) => {
    if (startX.current === null || startY.current === null) return;
    const dx = e.changedTouches[0].clientX - startX.current;
    const dy = e.changedTouches[0].clientY - startY.current;

    // Only fire if horizontal movement dominates (not a scroll)
    if (Math.abs(dx) < threshold || Math.abs(dy) > Math.abs(dx) * 0.8) return;

    if (dx < 0) onSwipeLeft?.();
    else onSwipeRight?.();

    startX.current = null;
    startY.current = null;
  }, [onSwipeLeft, onSwipeRight, threshold]);

  return { onTouchStart, onTouchEnd };
}
