'use client';

import { type ReactNode } from 'react';
import { motion, useReducedMotion, type Variants } from 'framer-motion';

interface TextRevealProps {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  as?: 'h1' | 'h2' | 'h3' | 'p' | 'span';
  stagger?: number;
  delay?: number;
  /** Split strategy: 'words' splits on spaces, 'lines' splits on \n */
  split?: 'words' | 'lines';
}

const container: Variants = {
  hidden: {},
  visible: ( stagger: number ) => ({
    transition: {
      staggerChildren: stagger,
    },
  }),
};

const child: Variants = {
  hidden: {
    opacity: 0,
    y: 20,
    filter: 'blur(8px)',
  },
  visible: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: {
      type: 'spring',
      damping: 20,
      stiffness: 100,
    },
  },
};

/**
 * Staggered text reveal with blur-to-clear transition.
 * Respects prefers-reduced-motion by showing text immediately.
 */
export function TextReveal({
  children,
  className = '',
  style,
  as: Tag = 'p',
  stagger = 0.04,
  delay = 0,
  split = 'words',
}: TextRevealProps) {
  const reduceMotion = useReducedMotion();

  if (reduceMotion) {
    return <Tag className={className} style={style}>{children}</Tag>;
  }

  const text = typeof children === 'string' ? children : '';
  if (!text) {
    return <Tag className={className} style={style}>{children}</Tag>;
  }

  const tokens = split === 'lines' ? text.split('\n') : text.split(' ');

  return (
    <Tag className={className} style={style}>
      <motion.span
        variants={container}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.6 }}
        style={{ display: 'inline' }}
      >
        {tokens.map((token, i) => (
          <motion.span
            key={`${token}-${i}`}
            variants={child}
            custom={stagger}
            style={{ display: 'inline-block' }}
          >
            {token}{split === 'words' ? ' ' : '\n'}
          </motion.span>
        ))}
      </motion.span>
    </Tag>
  );
}
