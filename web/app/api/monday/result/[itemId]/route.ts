import { NextRequest, NextResponse } from "next/server";
import { SERVER_API_BASE } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 30;

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ itemId: string }> }
) {
  const { itemId } = await params;
  const upstream = await fetch(
    `${SERVER_API_BASE}/api/monday/result/${encodeURIComponent(itemId)}`,
    { cache: "no-store" }
  );

  if (!upstream.ok) {
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "text/plain" },
    });
  }

  const buf = Buffer.from(await upstream.arrayBuffer());
  return new NextResponse(buf, {
    status: 200,
    headers: {
      "content-type": "image/png",
      "content-disposition": upstream.headers.get("content-disposition") ?? "inline",
    },
  });
}
