// Vercel Serverless Function — proxies new-game requests to the private HF Space.
// The HF_TOKEN environment variable must be set in the Vercel project settings.

export default async function handler(req, res) {
  // Only allow POST
  if (req.method !== "POST") {
    return res.status(405).json({ detail: "Method not allowed" });
  }

  const HF_TOKEN = process.env.HF_TOKEN;
  if (!HF_TOKEN) {
    console.error("HF_TOKEN environment variable is not set.");
    return res.status(500).json({ detail: "Server misconfiguration." });
  }

  const backendUrl = `https://daliusber-konteksto.hf.space/api/v1/games`;

  try {
    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${HF_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: "{}",
    });

    const data = await response.json();

    // Forward CORS headers
    res.setHeader("Access-Control-Allow-Origin", "*");
    return res.status(response.status).json(data);
  } catch (err) {
    console.error("Proxy error:", err);
    return res.status(502).json({ detail: "Failed to reach backend." });
  }
}
