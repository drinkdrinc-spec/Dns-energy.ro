export const BrandMark = ({ size = 40 }) => (
  <svg width={size} height={size} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="12" fill="#fff" />
    <path d="M26 7 L13 27 h8 l-3 14 L35 19 h-8 z" fill="#2878f0" />
    <path d="M26 7 L13 27 h8 l-3 14 L35 19 h-8 z" fill="url(#g)" opacity="0.55" />
    <defs>
      <linearGradient id="g" x1="13" y1="7" x2="35" y2="41" gradientUnits="userSpaceOnUse">
        <stop stopColor="#42c7d9" />
        <stop offset="1" stopColor="#2878f0" />
      </linearGradient>
    </defs>
  </svg>
);
