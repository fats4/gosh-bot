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

function joinStatusOk(status) {
  return status === 200 || status === 204;
}

function hasJoinOk(joinResults) {
  return joinResults.some(function (item) {
    return (
      String(item.url || "").indexOf("/live/join") !== -1 &&
      joinStatusOk(Number(item.status))
    );
  });
}

async function main() {
  const cfg = readConfig();
  const url = cfg.url;
  const watchSeconds = Number(cfg.watch_seconds || 15);
  const cookies = cfg.cookies || [];
  const gotoTimeout = Number(cfg.goto_timeout || 90000);
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

    page.on("response", async function (response) {
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

    const startedAt = Date.now();

    const joinWait = page
      .waitForResponse(
        function (response) {
          return (
            response.url().indexOf("/gosh_base/app/live/join") !== -1 &&
            response.request().method() === "POST" &&
            joinStatusOk(response.status())
          );
        },
        { timeout: gotoTimeout }
      )
      .catch(function () {
        return null;
      });

    try {
      await page.goto(url, {
        waitUntil: "domcontentloaded",
        timeout: gotoTimeout,
      });
    } catch (err) {
      const msg = String(err && err.message ? err.message : err);
      if (msg.indexOf("timeout") === -1 && msg.indexOf("TIMED_OUT") === -1) {
        throw err;
      }
    }

    await joinWait;
    const elapsedMs = Date.now() - startedAt;
    const remainMs = Math.max(watchSeconds * 1000 - elapsedMs, 0);
    if (remainMs > 0) {
      await sleep(remainMs);
    }

    process.stdout.write(
      JSON.stringify({
        ok: true,
        watched: watchSeconds,
        joined: hasJoinOk(joinResults),
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
