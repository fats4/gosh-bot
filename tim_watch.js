#!/usr/bin/env node
/**
 * Join Gosh live chat room via Tencent IM and stay connected to simulate watching.
 */
const TencentCloudChat = require("@tencentcloud/chat");
const WebSocket = require("ws");
const fs = require("fs");

if (typeof global.WebSocket === "undefined") {
  global.WebSocket = WebSocket;
}

function errCode(err) {
  return err && err.code;
}

function errMessage(err) {
  return String((err && err.message) || err);
}

function sleep(seconds) {
  return new Promise((resolve) => setTimeout(resolve, seconds * 1000));
}

async function main() {
  const raw =
    process.argv[2] && process.argv[2] !== "-"
      ? fs.readFileSync(process.argv[2], "utf8")
      : fs.readFileSync(0, "utf8");
  const cfg = JSON.parse(raw);
  const sdkappid = cfg.sdkappid;
  const userid = cfg.userid;
  const usersig = cfg.usersig;
  const group_id = cfg.group_id;
  const watch_seconds = Number(cfg.watch_seconds || 0);

  if (!sdkappid || !userid || !usersig || !group_id || watch_seconds <= 0) {
    throw new Error(
      "Missing required fields: sdkappid, userid, usersig, group_id, watch_seconds"
    );
  }

  const chat = TencentCloudChat.create({ SDKAppID: Number(sdkappid) });
  chat.setLogLevel(0);
  await chat.login({ userID: String(userid), userSig: usersig });

  try {
    await chat.joinGroup({ groupID: group_id });
  } catch (err) {
    const code = errCode(err);
    const msg = errMessage(err);
    if (code !== 10013 && code !== 10010 && msg.indexOf("already") === -1) {
      throw err;
    }
  }

  await sleep(watch_seconds);
  process.stdout.write(JSON.stringify({ ok: true, watched: watch_seconds }));
  chat.destroy();
  process.exit(0);
}

main().catch(function (err) {
  process.stderr.write(errMessage(err));
  process.exit(1);
});
