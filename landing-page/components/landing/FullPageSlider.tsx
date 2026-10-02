"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";

export function FullPageSlider({ sections }: { sections: React.ReactNode[] }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const isTransitioning = useRef(false);

  const handleNext = () => {
    if (isTransitioning.current) return;
    if (currentIndex < sections.length - 1) {
      isTransitioning.current = true;
      setCurrentIndex((prev) => prev + 1);
      setTimeout(() => (isTransitioning.current = false), 1000);
    }
  };

  const handlePrev = () => {
    if (isTransitioning.current) return;
    if (currentIndex > 0) {
      isTransitioning.current = true;
      setCurrentIndex((prev) => prev - 1);
      setTimeout(() => (isTransitioning.current = false), 1000);
    }
  };

  const handleWheel = (e: React.WheelEvent) => {
    // Ignore minor horizontal scrolls
    if (Math.abs(e.deltaY) < 30) return;
    
    if (e.deltaY > 0) {
      handleNext();
    } else {
      handlePrev();
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Prevent default scrolling for these keys
      if (['ArrowDown', 'PageDown', ' ', 'ArrowUp', 'PageUp'].includes(e.key)) {
        e.preventDefault();
      }

      if (['ArrowDown', 'PageDown', ' '].includes(e.key)) {
        handleNext();
      } else if (['ArrowUp', 'PageUp'].includes(e.key)) {
        handlePrev();
      }
    };
    
    // non-passive so we can preventDefault
    window.addEventListener("keydown", handleKeyDown, { passive: false });
    return () => window.removeEventListener("keydown", handleKeyDown);
  }); // no dependencies to always capture latest state, or can use refs. Let's use refs for currentIndex or just bind properly. Wait, since it runs on every render, it will constantly rebind, which is fine since we return cleanup.

  return (
    <div 
      className="fixed inset-0 h-screen w-screen overflow-hidden bg-white"
      onWheel={handleWheel}
    >
      <motion.div
        className="h-full w-full"
        animate={{ y: `-${currentIndex * 100}vh` }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }} 
      >
        {sections.map((section, index) => (
          <div 
            key={index} 
            className="h-screen w-full flex items-center justify-center relative"
          >
            {/* The sections themselves can be wrapped in this container to enforce screen size limits */}
            <div className="h-full w-full max-h-screen overflow-hidden">
              {section}
            </div>
          </div>
        ))}
      </motion.div>

      {/* Optional Side Pagination Indicators */}
      <div className="fixed right-6 top-1/2 -translate-y-1/2 flex flex-col gap-3 z-50">
        {sections.map((_, index) => (
          <button
            key={index}
            onClick={() => {
              if(!isTransitioning.current) {
                isTransitioning.current = true;
                setCurrentIndex(index);
                setTimeout(() => (isTransitioning.current = false), 1000);
              }
            }}
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              currentIndex === index 
                ? "bg-slate-900 scale-150" 
                : "bg-slate-300 hover:bg-slate-400"
            }`}
            aria-label={`Go to slide ${index + 1}`}
          />
        ))}
      </div>
    </div>
  );
}
