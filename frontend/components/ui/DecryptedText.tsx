"use client";

import { useEffect, useState, useRef, useMemo } from "react";

interface DecryptedTextProps {
  text: string;
  speed?: number;
  maxIterations?: number;
  sequential?: boolean;
  revealDirection?: "start" | "end" | "center";
  characters?: string;
  className?: string;
  parentClassName?: string;
  encryptedClassName?: string;
  isActive?: boolean;
}

export default function DecryptedText({
  text,
  speed = 45,
  maxIterations = 14,
  sequential = true,
  characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*()_+0123456789",
  className = "",
  parentClassName = "",
  encryptedClassName = "",
  isActive = true,
}: DecryptedTextProps) {
  const [displayText, setDisplayText] = useState(text);
  const [isDecrypted, setIsDecrypted] = useState(false);
  const iterationRef = useRef(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const charArray = useMemo(() => text.split(""), [text]);

  useEffect(() => {
    if (!isActive) {
      setDisplayText(text);
      setIsDecrypted(false);
      iterationRef.current = 0;
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }

    iterationRef.current = 0;
    setIsDecrypted(false);

    if (intervalRef.current) clearInterval(intervalRef.current);

    intervalRef.current = setInterval(() => {
      setDisplayText(() => {
        return charArray
          .map((char, index) => {
            if (char === " " || char === "\n") return char;

            if (sequential) {
              if (index < iterationRef.current / (maxIterations / charArray.length)) {
                return char;
              }
            } else {
              if (iterationRef.current >= maxIterations) {
                return char;
              }
            }

            return characters[Math.floor(Math.random() * characters.length)];
          })
          .join("");
      });

      iterationRef.current += 1;

      if (iterationRef.current > maxIterations + charArray.length * 2) {
        setDisplayText(text);
        setIsDecrypted(true);
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }, speed);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isActive, text, speed, maxIterations, sequential, characters, charArray]);

  return (
    <span className={parentClassName} style={{ display: "inline-block" }}>
      <span className={isDecrypted ? className : encryptedClassName || className}>
        {displayText}
      </span>
    </span>
  );
}
