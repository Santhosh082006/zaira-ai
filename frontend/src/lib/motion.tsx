"use client";

import React, { forwardRef } from "react";

interface MotionProps extends React.HTMLAttributes<HTMLDivElement> {
  initial?: any;
  animate?: any;
  exit?: any;
  transition?: any;
}

export const motion = {
  div: forwardRef<HTMLDivElement, MotionProps>(
    ({ initial, animate, exit, transition, className = "", children, ...props }, ref) => {
      return (
        <div ref={ref} className={`${className} animate-fadeIn`} {...props}>
          {children}
        </div>
      );
    }
  ),
  span: forwardRef<HTMLSpanElement, React.HTMLAttributes<HTMLSpanElement> & { initial?: any; animate?: any; exit?: any; transition?: any }>(
    ({ initial, animate, exit, transition, className = "", children, ...props }, ref) => {
      return (
        <span ref={ref} className={`${className} animate-fadeIn`} {...props}>
          {children}
        </span>
      );
    }
  ),
  p: forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement> & { initial?: any; animate?: any; exit?: any; transition?: any }>(
    ({ initial, animate, exit, transition, className = "", children, ...props }, ref) => {
      return (
        <p ref={ref} className={`${className} animate-fadeIn`} {...props}>
          {children}
        </p>
      );
    }
  ),
};

export const AnimatePresence: React.FC<{ children: React.ReactNode; mode?: string }> = ({ children }) => {
  return <>{children}</>;
};

export default motion;
