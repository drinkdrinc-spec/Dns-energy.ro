export const BrandMark = ({ size = 40 }) => (
  <img
    src="/dns-energy-official.png"
    alt="DNS Energy"
    width={Math.round(size * 1.52)}
    height={size}
    style={{ width: Math.round(size * 1.52), height: size, objectFit: "contain", flexShrink: 0 }}
  />
);

