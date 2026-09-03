#!/usr/bin/env node
/**
 * Send Gosh live chat via Tencent IM custom message (type 10000 / ScreenText).
 */
const TencentCloudChat = require("@tencentcloud/chat");
const WebSocket = require("ws");
const fs = require("fs");
const crypto = require("crypto");

if (typeof global.WebSocket === "undefined") {
  global.WebSocket = WebSocket;
}

function errCode(err) {
  return err && err.code;
}

function errMessage(err) {
  return String((err && err.message) || err);
}

function newTraceId() {
  if (crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
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
  const text = cfg.text;
  const live_id = cfg.live_id != null ? String(cfg.live_id) : "0";
  const watch_seconds = Number(cfg.watch_seconds || 0);
  const user = cfg.user;
  if (!sdkappid || !userid || !usersig || !group_id || !text || !user) {
    throw new Error(
      "Missing required fields: sdkappid, userid, usersig, group_id, text, user"
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

  if (watch_seconds > 0) {
    await new Promise((resolve) => setTimeout(resolve, watch_seconds * 1000));
  }

  const now = Math.floor(Date.now() / 1000);
  const traceId = cfg.trace_id || newTraceId();
  const inner = {
    type: 10000,
    msg_id: 0,
    user: user,
    data: {
      text: text,
      rich_content: [{ type: "text", text: text }],
    },
    occur_at: now,
    live_id: live_id,
    trace_id: traceId,
    operation_id: traceId,
    correlation_id: traceId,
    client_request_id: traceId,
  };

  const message = chat.createCustomMessage({
    to: group_id,
    conversationType: TencentCloudChat.TYPES.CONV_GROUP,
    payload: {
      data: JSON.stringify(inner),
      description: "",
      extension: "",
    },
  });

  const result = await chat.sendMessage(message);
  process.stdout.write(
    JSON.stringify({
      ok: true,
      messageID:
        result && result.data && result.data.message
          ? result.data.message.ID
          : null,
    })
  );
  chat.destroy();
  process.exit(0);
}

main().catch(function (err) {
  process.stderr.write(errMessage(err));
  process.exit(1);
});
