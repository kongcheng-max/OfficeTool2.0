import React from 'react';
import { motion, useReducedMotion, type Variants } from 'framer-motion';

interface FadeInProps {
  children: React.ReactNode;
  /** 延迟（秒） */
  delay?: number;
  /** 位移距离（px），默认 12 */
  y?: number;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * 淡入上移 —— 单个元素进入视口时淡入（React Bits «Fade / Animated Content» 思路）。
 * 只触发一次，尊重 prefers-reduced-motion。
 */
export const FadeIn: React.FC<FadeInProps> = ({ children, delay = 0, y = 12, className, style }) => {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className} style={style}>{children}</div>;

  return (
    <motion.div
      className={className}
      style={style}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -8% 0px' }}
      transition={{ duration: 0.45, delay, ease: [0.4, 0, 0.2, 1] }}
    >
      {children}
    </motion.div>
  );
};

/**
 * 错峰容器 —— 包裹一组 <StaggerItem>，子项逐条进场（React Bits «Animated List» 思路，
 * 套用在既有列表上而非替换列表本身）。
 */
const containerVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.4, 0, 0.2, 1] } },
};

interface StaggerProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export const Stagger: React.FC<StaggerProps> = ({ children, className, style }) => {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className} style={style}>{children}</div>;

  return (
    <motion.div
      className={className}
      style={style}
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      {children}
    </motion.div>
  );
};

export const StaggerItem: React.FC<StaggerProps> = ({ children, className, style }) => {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className} style={style}>{children}</div>;

  return (
    <motion.div className={className} style={style} variants={itemVariants}>
      {children}
    </motion.div>
  );
};
