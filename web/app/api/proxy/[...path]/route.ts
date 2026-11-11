import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const target = path.join("/");
  const allowed =
    request.method === "POST"
      ? ["v1/extract", "v1/review"].includes(target)
      : [
          "healthz",
          "v1/domains",
          "v1/examples",
          "v1/benchmarks",
          "v1/schema/charter",
        ].includes(target);
  if (!allowed)
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  const body = request.method === "POST" ? await request.text() : undefined;
  if (body && Buffer.byteLength(body) > 64000) {
    return NextResponse.json({ detail: "Request too large" }, { status: 413 });
  }
  try {
    const response = await fetch(
      `${process.env.AEROLM_API_URL || "http://127.0.0.1:8000"}/${target}`,
      {
        method: request.method,
        body,
        cache: "no-store",
        signal: AbortSignal.timeout(120000),
        headers: {
          "Content-Type": "application/json",
          ...(process.env.AEROLM_API_KEY
            ? { Authorization: `Bearer ${process.env.AEROLM_API_KEY}` }
            : {}),
        },
      },
    );
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      {
        detail: "AeroLM API is unavailable. Start the Python API on port 8000.",
      },
      { status: 502 },
    );
  }
}

export { proxy as GET, proxy as POST };
