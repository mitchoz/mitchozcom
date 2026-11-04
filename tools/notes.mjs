#!/usr/bin/env node
/*
  Fills in notes.json (the Tweets section) from X post links.

  notes.json groups posts into stories. A story's first post is how it started;
  the rest are what followed:
    { "stories": [
        { "posts": ["https://x.com/mitch0z/status/1993035566959804646", "...follow-up link..."] },
        ...
    ] }

  This script replaces every link with the post's data (date, text, likes, replies,
  photos, video thumbnail, quoted post) from X's public embed endpoint and sorts each
  story's posts by date. Posts that are already filled in are left alone.
  Check a post's likes before adding it with tools/likes.mjs.

    node tools/notes.mjs            fill in new links
    node tools/notes.mjs --refresh  re-fetch every post (updates like counts)
*/
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const FILE = fileURLToPath(new URL("../notes.json", import.meta.url));
const refresh = process.argv.includes("--refresh");

// Same token the official embed widget computes from the post ID.
const token = (id) => ((Number(id) / 1e15) * Math.PI).toString(36).replace(/(0+|\.)/g, "");
const idOf = (post) => (typeof post === "string" ? post.match(/status\/(\d+)/)?.[1] : post.id);

async function fetchPost(id) {
  const url = `https://cdn.syndication.twimg.com/tweet-result?id=${id}&token=${token(id)}&lang=en`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const j = await res.json();
  if (j.__typename === "TweetTombstone") {
    throw new Error("X hides this post from embeds (age-restricted or sensitive). Write its fields in notes.json by hand.");
  }
  if (!j.id_str) throw new Error("post not found (deleted or private?)");
  return j;
}

// X sends text HTML-escaped ("&amp;"); the page inserts it as plain text, so decode it here.
const unescape = (s) =>
  s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");

// Drop t.co links to attached media; expand all other t.co links.
function cleanText(j) {
  let text = j.text;
  for (const m of j.entities?.media ?? []) text = text.replace(m.url, "");
  for (const u of j.entities?.urls ?? []) text = text.replace(u.url, u.expanded_url);
  return unescape(text.trim());
}

function toPost(j) {
  const video = (j.mediaDetails ?? []).find((m) => m.type !== "photo");
  const post = {
    id: j.id_str,
    url: `https://x.com/${j.user.screen_name}/status/${j.id_str}`,
    date: new Date(j.created_at).toISOString().replace(".000", ""),
    text: cleanText(j),
    likes: j.favorite_count ?? 0,
    replies: j.conversation_count ?? 0,
    photos: (j.photos ?? []).map((p) => p.url),
  };
  if (video) post.video = video.media_url_https;
  if (j.quoted_tweet) {
    const q = j.quoted_tweet;
    post.quote = { user: q.user?.screen_name, url: `https://x.com/${q.user?.screen_name}/status/${q.id_str}`, text: cleanText(q) };
  }
  return post;
}

// Strip a byte-order mark if an editor added one; JSON.parse rejects it.
const data = JSON.parse((await readFile(FILE, "utf8")).replace(/^﻿/, ""));
let fetched = 0, failed = 0;

async function fill(entry) {
  const id = idOf(entry);
  if (!id) { console.warn(`  ? can't read a post ID from ${JSON.stringify(entry)}`); return entry; }
  // Hand-written entries for posts X hides ("hidden": true) can't be fetched, so leave them as written.
  if (typeof entry === "object" && (!refresh || entry.hidden)) return entry;
  try {
    const post = toPost(await fetchPost(id));
    fetched++;
    console.log(`  ok ${id}`);
    return post;
  } catch (e) {
    failed++;
    console.warn(`  FAILED ${id}: ${e.message}`);
    return entry;
  }
}

for (const story of data.stories) {
  const posts = [];
  for (const entry of story.posts) posts.push(await fill(entry));
  // Oldest first, so the first post is how the story started.
  const dated = posts.filter((p) => typeof p === "object" && p.date).sort((a, b) => a.date.localeCompare(b.date));
  story.posts = [...dated, ...posts.filter((p) => !dated.includes(p))];
}
data.stories.sort((a, b) => (a.posts[0]?.date ?? "").localeCompare(b.posts[0]?.date ?? ""));

await writeFile(FILE, JSON.stringify(data, null, 2) + "\n");
console.log(`notes.json: ${fetched} fetched, ${failed} failed.`);
if (failed) process.exitCode = 1;
