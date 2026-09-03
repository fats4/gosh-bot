/**
 * Parse proxy string untuk Puppeteer.
 * Format: host:port | http://host:port | http://user:pass@host:port | socks5://...
 */
function parseProxy(proxy) {
  if (!proxy || !String(proxy).trim()) {
    return null;
  }
  let raw = String(proxy).trim();
  if (raw.indexOf("://") === -1) {
    raw = "http://" + raw;
  }
  const parsed = new URL(raw);
  const port = parsed.port || (parsed.protocol === "https:" ? "443" : "80");
  const server = parsed.protocol + "//" + parsed.hostname + ":" + port;
  return {
    server: server,
    username: parsed.username || null,
    password: parsed.password || null,
  };
}

async function applyProxyToPage(page, proxy) {
  const cfg = parseProxy(proxy);
  if (!cfg) {
    return;
  }
  if (cfg.username) {
    await page.authenticate({
      username: cfg.username,
      password: cfg.password || "",
    });
  }
}

function proxyLaunchArgs(proxy) {
  const cfg = parseProxy(proxy);
  if (!cfg) {
    return [];
  }
  return ["--proxy-server=" + cfg.server];
}

module.exports = {
  parseProxy: parseProxy,
  applyProxyToPage: applyProxyToPage,
  proxyLaunchArgs: proxyLaunchArgs,
};
