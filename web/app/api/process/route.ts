import { NextRequest, NextResponse } from "next/server";
import { SERVER_API_BASE } from "@/lib/api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function POST(req: NextRequest) {
  const incomingForm = await req.formData();
  const file = incomingForm.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "Falta el archivo en el campo 'file'" }, { status: 400 });
  }

  const upstreamForm = new FormData();
  upstreamForm.append("file", file, file.name);

  const upstream = await fetch(`${SERVER_API_BASE}/api/process`, {
    method: "POST",
    body: upstreamForm,
  });

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
