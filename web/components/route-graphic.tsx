export function RouteGraphic() {
  return (
    <svg viewBox="0 0 340 180" className="route-graphic" aria-hidden="true">
      <defs>
        <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <path
            d="M 24 0 L 0 0 0 24"
            fill="none"
            stroke="currentColor"
            strokeWidth=".5"
          />
        </pattern>
      </defs>
      <rect width="340" height="180" fill="url(#grid)" opacity=".35" />
      <ellipse
        cx="180"
        cy="100"
        rx="135"
        ry="66"
        fill="none"
        stroke="currentColor"
        opacity=".25"
      />
      <ellipse
        cx="180"
        cy="100"
        rx="70"
        ry="66"
        fill="none"
        stroke="currentColor"
        opacity=".2"
      />
      <path
        d="M50 104 Q180 -5 288 82"
        fill="none"
        stroke="#d86a3a"
        strokeWidth="1.7"
        strokeDasharray="4 5"
      />
      <circle cx="50" cy="104" r="4" fill="#d86a3a" />
      <circle cx="288" cy="82" r="4" fill="#d86a3a" />
      <text
        x="35"
        y="127"
        fill="currentColor"
        fontSize="10"
        fontFamily="monospace"
      >
        UNSTRUCTURED
      </text>
      <text
        x="239"
        y="105"
        fill="currentColor"
        fontSize="10"
        fontFamily="monospace"
      >
        STRUCTURED
      </text>
      <path
        d="m177 35 3 13 16 9-1 4-15-4-4 14-4-1 1-16-10-7 1-4 12 4z"
        fill="#d86a3a"
        transform="rotate(22 180 50)"
      />
    </svg>
  );
}
