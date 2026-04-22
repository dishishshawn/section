const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export async function GET(request: Request) {
  try {
    const res = await fetch(`${API_URL}`, {
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    return Response.json(data);
  } catch (error) {
    return Response.json({ error: "Failed to fetch from backend" }, { status: 500 });
  }
}
