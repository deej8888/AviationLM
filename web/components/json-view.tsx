export function JsonView({ value }: { value: unknown }) {
  const json = JSON.stringify(value, null, 2);
  return (
    <pre className="json-view">
      <code>
        {json
          .split(
            /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|\bnull\b|\btrue\b|\bfalse\b|\b\d+(?:\.\d+)?\b)/g,
          )
          .map((part, i) => (
            <span
              key={i}
              className={
                part.endsWith(":")
                  ? "json-key"
                  : part.startsWith('"')
                    ? "json-string"
                    : /^(null|true|false)$/.test(part)
                      ? "json-null"
                      : /^\d/.test(part)
                        ? "json-number"
                        : ""
              }
            >
              {part}
            </span>
          ))}
      </code>
    </pre>
  );
}
