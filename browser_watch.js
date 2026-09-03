#!/usr/bin/env node
/**
 * Buka live Gosh di browser headless (Puppeteer) agar join/heartbeat viewer terdaftar.
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
  const watchSeconds = Number(cfg.watch_seconds || 15);
  const cookies = cfg.cookies || [];
  if (!url || watchSeconds <= 0) {
    throw new Error("Missing required fields: url, watch_seconds");
  }

  const joinResults = [];
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

  try {
    const page = await browser.newPage();
    await applyProxyToPage(page, cfg.proxy);
    await page.setUserAgent(
      cfg.user_agent ||
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    );
    await page.setViewport({ width: 1280, height: 720 });

    page.on("response", async (response) => {
      try {
        const reqUrl = response.url();
        if (
          reqUrl.indexOf("/gosh_base/app/live/join") === -1 &&
          reqUrl.indexOf("/gosh_base/app/sys/heartbeat") === -1
        ) {
          return;
        }
        let body = "";
        try {
          body = await response.text();
        } catch (err) {
          body = "";
        }
        joinResults.push({
          url: reqUrl.split("?")[0],
          status: response.status(),
          body: body.slice(0, 300),
        });
      } catch (err) {
        // ignore listener errors
      }
    });

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

    await sleep(watchSeconds * 1000);

    process.stdout.write(
      JSON.stringify({
        ok: true,
        watched: watchSeconds,
        join_results: joinResults,
      })
    );
  } finally {
    await browser.close();
  }
}

main().catch(function (err) {
  process.stderr.write(String(err && err.message ? err.message : err));
  process.exit(1);
});
