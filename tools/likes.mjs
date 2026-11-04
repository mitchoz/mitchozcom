#!/usr/bin/env node
/*
  Checks like counts for a list of X posts, to decide which belong in Notes.

    node tools/likes.mjs 1993035566959804646 https://x.com/mitch0z/status/1768009385668673748 ...

  Prints date, likes and the start of the text for each, highest first.
  Posts X hides from embeds (age-restricted) are listed as hidden.
*/
const token = (id) => ((Number(id) / 1e15) * Math.PI).toString(36).replace(/(0+|\.)/g, "");
const ids = [...new Set(process.argv.slice(2).map((a) => a.match(/(\d{15,})/)?.[1]).filter(Boolean))];

const rows = await Promise.all(ids.map(async (id) => {
  try {
    const r = await fetch(`https://cdn.syndication.twimg.com/tweet-result?id=${id}&token=${token(id)}&lang=en`);
    const j = await r.json();
    if (j.__typename === "TweetTombstone") return { id, hidden: true };
    if (!j.id_str) return { id, missing: true };
    return {
      id, user: j.user?.screen_name, date: j.created_at?.slice(0, 10), likes: j.favorite_count ?? 0,
      reply: Boolean(j.in_reply_to_status_id_str), text: j.text.replace(/\s+/g, " ").slice(0, 70),
    };
  } catch (e) {
    return { id, error: e.message };
  }
}));

rows.sort((a, b) => (b.likes ?? -1) - (a.likes ?? -1));
for (const r of rows) {
  if (r.hidden) console.log(`${r.id}  hidden by X (age-restricted)`);
  else if (r.missing || r.error) console.log(`${r.id}  not found ${r.error ?? ""}`);
  else console.log(`${r.likes >= 500 ? "*" : " "} ${String(r.likes).padStart(5)}  ${r.date}  @${r.user}${r.reply ? " (reply)" : ""}  ${r.id}  ${r.text}`);
}
