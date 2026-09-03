#!/usr/bin/env node
/**
 * Buka live Gosh di browser headless dan tetap menonton (boost viewer count).
 */
const fs = require("fs");
const puppeteer = require("puppeteer");
const { proxyLaunchArgs, applyProxyToPage } = require("./proxy_helper");

function readConfig() {
  const raw =
    process.argv[2] && process.argv[2] !== "-"
      ? fs.readFileSync(process.argv[2], "utf8")
      : fs.readFileSync(0, "utf8");
  return JSON.parse(raw);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  const cfg = readConfig();
  const url = cfg.url;
  const cookies = cfg.cookies || [];
  if (!url) {
    throw new Error("Missing required field: url");
  }

  const launchArgs = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--mute-audio",
  ].concat(proxyLaunchArgs(cfg.proxy));

  const browser = await puppeteer.launch({
    headless: true,
    args: launchArgs,
  });

  let closed = false;
  async function shutdown() {
    if (closed) {
      return;
    }
    closed = true;
    try {
      await browser.close();
    } catch (err) {
      // ignore
    }
    process.exit(0);
  }

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  try {
    const page = await browser.newPage();
    await applyProxyToPage(page, cfg.proxy);
    await page.setUserAgent(
      cfg.user_agent ||
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    );
    await page.setViewport({ width: 1280, height: 720 });

    if (cookies.length) {
      await page.setCookie(
        ...cookies.map(function (cookie) {
          return {
            name: cookie.name,
            value: cookie.value,
            domain: cookie.domain || ".gosh.com",
            path: cookie.path || "/",
          };
        })
      );
    }

    await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });

    process.stdout.write(JSON.stringify({ ok: true, mode: "keepalive", url: url }));

    while (!closed) {
      await sleep(30000);
    }
  } catch (err) {
    await shutdown();
    throw err;
  }
}

main().catch(function (err) {
  process.stderr.write(String(err && err.message ? err.message : err));
  process.exit(1);
});
