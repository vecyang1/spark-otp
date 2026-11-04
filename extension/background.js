/**
 * Spark OTP Autofill - Manifest V3 Background Service Worker
 * Executes localhost daemon HTTP requests from the privileged extension origin,
 * bypassing page-level Content-Security-Policy (CSP) and Chrome Private Network Access (PNA)
 * loopback restrictions on HTTPS origins.
 */

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || typeof msg !== "object") return false;

  if (msg.type === "SPARK_OTP_PROXY_FETCH" && typeof msg.url === "string") {
    // Security gate: only proxy requests targeting local Spark OTP daemon (127.0.0.1 or localhost)
    try {
      const parsed = new URL(msg.url);
      if (parsed.hostname !== "127.0.0.1" && parsed.hostname !== "localhost") {
        sendResponse({ ok: false, status: 403, error: "Forbidden host" });
        return false;
      }
    } catch (e) {
      sendResponse({ ok: false, status: 400, error: "Invalid URL" });
      return false;
    }

    fetch(msg.url, { cache: "no-store" })
      .then(async (res) => {
        const data = await res.json().catch(() => null);
        sendResponse({ ok: res.ok, status: res.status, data });
      })
      .catch((err) => {
        sendResponse({ ok: false, status: 0, error: String(err) });
      });
    return true; // Keep message channel open for async response
  }

  return false;
});
