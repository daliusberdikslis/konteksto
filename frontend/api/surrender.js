// Vercel Serverless Function — proxies surrender requests to the private HF Space.
// The HF_TOKEN environment variable must be set in the Vercel project settings.

export default async function handler(req, res) {
  // Only allow GET
  if (req.method !== "GET") {
    return res.status(405).json({ detail: "Method not allowed" });
  }

  const gameId = req.query.game_id;
  if (!gameId) {
    return res.status(400).json({ detail: "game_id parameter is required." });
  }

  const HF_TOKEN = process.env.HF_TOKEN;
  if (!HF_TOKEN) {
    console.error("HF_TOKEN environment variable is not set.");
    return res.status(500).json({ detail: "Server misconfiguration." });
  }

  const params = new URLSearchParams({ game_id: gameId });
  const backendUrl = `https://daliusber-konteksto.hf.space/api/v1/surrender?${params.toString()}`;

  try {
    const response = await fetch(backendUrl, {
      headers: {
        Authorization: `Bearer ${HF_TOKEN}`,
      },
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
