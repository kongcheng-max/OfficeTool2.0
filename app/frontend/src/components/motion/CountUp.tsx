import React, { useEffect, useRef } from 'react';
import { useInView, useMotionValue, useSpring, useReducedMotion } from 'framer-motion';

interface Props {
  /** 目标数值 */
  to: number;
  /** 起始数值，默认 0 */
  from?: number;
  /** 动画时长（秒），默认 1.4 */
  duration?: number;
  /** 千分位分隔，默认 true */
  separator?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * 数字滚动 —— 进入视口时从 from 滚动到 to（React Bits «Count Up» 思路）。
 * 用 useSpring 驱动，尊重 prefers-reduced-motion（直接显示终值）。
 */
const CountUp: React.FC<Props> = ({
  to,
  from = 0,
  duration = 1.4,
  separator = true,
  className,
  style,
}) => {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '0px 0px -10% 0px' });
  const reduce = useReducedMotion();

  const motionVal = useMotionValue(from);
  const spring = useSpring(motionVal, {
    duration: duration * 1000,
    bounce: 0,
  });

  const format = (n: number) => {
    const rounded = Math.round(n);
    return separator ? rounded.toLocaleString('en-US') : String(rounded);
  };

  useEffect(() => {
    if (reduce) {
      if (ref.current) ref.current.textContent = format(to);
      return;
    }
    if (inView) motionVal.set(to);
  }, [inView, to, reduce]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (reduce) return;
    const unsub = spring.on('change', (v) => {
      if (ref.current) ref.current.textContent = format(v);
    });
    return unsub;
  }, [spring, reduce]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <span ref={ref} className={className} style={style}>
      {format(reduce ? to : from)}
    </span>
  );
};

export default CountUp;
