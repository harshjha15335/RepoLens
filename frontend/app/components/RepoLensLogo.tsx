import React from "react";

interface RepoLensLogoProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

export default function RepoLensLogo({ size = 26, className, style }: RepoLensLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ display: "inline-block", verticalAlign: "middle", flexShrink: 0, ...style }}
      aria-label="RepoLens Logo"
    >
      <defs>
        <linearGradient id="repolens-grad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#2563EB" />
          <stop offset="60%" stopColor="#0EA5E9" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>
        <linearGradient id="repolens-ring" x1="6" y1="6" x2="26" y2="26" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#BAE6FD" stopOpacity="0.8" />
        </linearGradient>
      </defs>

      {/* Rounded squircle background */}
      <rect width="32" height="32" rx="9" fill="url(#repolens-grad)" />

      {/* Lens Optical Ring */}
      <circle cx="14" cy="14" r="8" stroke="url(#repolens-ring)" strokeWidth="2.2" strokeLinecap="round" />

      {/* Lens Handle */}
      <line x1="19.8" y1="19.8" x2="25.5" y2="25.5" stroke="#FFFFFF" strokeWidth="2.4" strokeLinecap="round" />

      {/* Code Aperture inside the Lens: < / > */}
      <path d="M12 11.5L9.5 14L12 16.5" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M16 11.5L18.5 14L16 16.5" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="14.8" y1="11" x2="13.2" y2="17" stroke="#FFFFFF" strokeWidth="1.4" strokeLinecap="round" opacity="0.85" />
    </svg>
  );
}
