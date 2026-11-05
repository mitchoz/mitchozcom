(async () => {
  // For whoever opens the console. Same drawing as the comment at the top of each page (tools/ascii_logo.txt).
  console.log(
    [
      "",
      "       /     /\\      /\\      /\\",
      "      /     /  \\    /  \\    /  \\",
      "     /     /    \\  /    \\  /    \\",
      "    /     /      \\/      \\/      \\",
      "",
    ].join("\n"),
  );

  const el = (tag, attrs = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (k === "text") node.textContent = v;
      else if (k === "class") node.className = v;
      else node.setAttribute(k, v);
    }
    for (const c of [].concat(children)) if (c != null) node.append(c);
    // Every link opens in a new tab. Set it on the link itself: some in-app browsers ignore <base target>.
    if (tag === "a" && !node.hasAttribute("target")) {
      node.target = "_blank";
      node.rel = "noopener";
    }
    return node;
  };
  const num = new Intl.NumberFormat("en-US");
  const isoDay = (iso) => iso.slice(0, 10);
  // "01 JUN 2025": the same in the US and Europe (tools/format_dates.py does this for the static pages).
  const MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(" ");
  const dayLabel = (iso) => {
    const [y, m, d] = isoDay(iso).split("-");
    return `${d} ${MONTHS[Number(m) - 1]} ${y}`;
  };
  // pbs.twimg.com serves resized variants via ?name=
  const small = (src) => (src.includes("/media/") ? `${src}?name=small` : src);
  const oneLine = (s) => s.replace(/\s*\n+\s*/g, " ");

  /* ---------- ASCII scramble ----------
     On load, all text on the page starts as random ASCII and settles into the real text,
     character by character, in a quick top-to-bottom sweep across the screen. The whole page
     scrambles, not just the first screen, because the browser may restore the scroll position
     (e.g. back at the bottom after a reload) only after this has started.
     Skipped entirely when the visitor prefers reduced motion. */
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const GLYPHS = "/\\|_-=+*#%&@$<>[]{}()?!:;~^abcdefghijklmnopqrstuvwxyz0123456789";
  const glyph = () => GLYPHS[(Math.random() * GLYPHS.length) | 0];
  const noise = (length) => Array.from({ length }, glyph).join("");

  function scrambleIn(root, { duration = 900, sweep = 350 } = {}) {
    if (reduceMotion || !root) return;
    const vh = innerHeight;
    const items = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
    });
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const box = n.parentElement.getBoundingClientRect();
      if (!box.width) continue; // not rendered (e.g. inside a hidden element)
      const text = n.nodeValue;
      // Each character settles at its own moment; lines lower on the screen start a little later
      // (the sweep). Text below the screen settles last, with the bottom of the screen.
      const offset = (Math.min(Math.max(0, box.top), vh) / vh) * sweep;
      const at = Array.from(text, () => offset + Math.random() * (duration - sweep));
      items.push({ n, text, at });
    }
    if (!items.length) return;

    const render = (t) => {
      for (const { n, text, at } of items) {
        let out = "";
        for (let i = 0; i < text.length; i++) out += t >= at[i] || /\s/.test(text[i]) ? text[i] : glyph();
        n.nodeValue = out;
      }
    };
    root.setAttribute("aria-busy", "true");
    render(0);
    const start = performance.now();
    const finish = () => {
      clearInterval(tick);
      items.forEach(({ n, text }) => (n.nodeValue = text));
      root.removeAttribute("aria-busy");
    };
    // A timer rather than animation frames: frames pause in background tabs and hidden frames,
    // which would leave the text scrambled. ~25 updates a second reads as flicker, not blur.
    const tick = setInterval(() => {
      const t = performance.now() - start;
      t >= duration ? finish() : render(t);
    }, 40);
  }

  // Scramble the first screen, then let it show (the head snippet hid it to avoid a flash of real text).
  scrambleIn(document.querySelector("main"));
  document.documentElement.classList.remove("scramble-wait");

  /* ---------- Tweets ----------
     Stories told on X, newest first. Each story's first post is how it started (the header);
     the posts that followed are listed under it in order. */
  // Posts X hides from embeds (age-restricted) are hand-written with just a link and date.
  const stats = (p) => (p.hidden ? "Only visible on X" : `${num.format(p.likes)} likes · ${num.format(p.replies)} replies`);
  // Image- or video-only posts have no text; name the medium so the link has something to say.
  const postLink = (p) => {
    const text = p.text ? oneLine(p.text) : p.hidden ? "Age-restricted post on X" : p.video ? "Video" : "Image";
    return el("a", { href: p.url, text });
  };
  // The hover image for a post (its video frame or first photo); "" for text-only posts.
  // Every post row gets the attribute, so hovering a text-only follow-up doesn't show the story's image.
  const thumbOf = (p) => (p.video ? p.video : p.photos?.[0] ? small(p.photos[0]) : "");
  // Quoting another post in the same story repeats what's already on screen, so skip those.
  const quoteLine = (p, storyUrls) =>
    p.quote && !storyUrls.has(p.quote.url)
      ? el("p", {}, ["Quoting ", el("a", { href: p.quote.url, text: p.quote.text ? oneLine(p.quote.text) : "a post" })])
      : null;

  function renderStory(story) {
    const [start, ...followUps] = story.posts;
    const urls = new Set(story.posts.map((p) => p.url));
    return el("li", { class: "story", "data-thumb": thumbOf(start) }, [
      el("time", { datetime: isoDay(start.date), text: dayLabel(start.date) }),
      el("div", {}, [
        postLink(start),
        quoteLine(start, urls),
        el("p", { text: stats(start) }),
        followUps.length
          ? el("ol", { class: "story-posts" }, followUps.map((p) =>
              el("li", { "data-thumb": thumbOf(p) }, [
                postLink(p),
                quoteLine(p, urls),
                el("p", {}, [el("time", { datetime: isoDay(p.date), text: dayLabel(p.date) }), ` · ${stats(p)}`]),
              ])))
          : null,
      ]),
    ]);
  }

  const notesRoot = document.getElementById("notes-list");
  if (notesRoot) {
    // Skeleton: placeholder rows of shifting ASCII until the posts arrive.
    const lines = [[10, 46, 24], [10, 38, 22], [10, 52, 26]];
    const skeleton = lines.map(([d, a, b]) => {
      const parts = [el("time", { text: noise(d) }), el("span", { class: "skeleton-line", text: noise(a) }), el("span", { class: "skeleton-sub", text: noise(b) })];
      return { parts, li: el("li", { class: "skeleton", "aria-hidden": "true" }, [parts[0], el("div", {}, parts.slice(1))]) };
    });
    notesRoot.append(...skeleton.map((s) => s.li));
    notesRoot.setAttribute("aria-busy", "true");
    const flicker = reduceMotion ? 0 : setInterval(() => {
      for (const { parts } of skeleton) for (const p of parts) p.textContent = noise(p.textContent.length);
    }, 70);

    try {
      // Revalidate every time so newly added posts show up right away (a cheap 304 when unchanged).
      const { stories } = await (await fetch("notes.json", { cache: "no-cache" })).json();
      // Links the script hasn't filled in yet are skipped.
      const shown = stories
        .map((s) => ({ ...s, posts: s.posts.filter((p) => typeof p === "object" && p.date).sort((a, b) => a.date.localeCompare(b.date)) }))
        .filter((s) => s.posts.length)
        .sort((a, b) => b.posts[0].date.localeCompare(a.posts[0].date));
      clearInterval(flicker);
      notesRoot.replaceChildren(...shown.map(renderStory));
      notesRoot.removeAttribute("aria-busy");
      scrambleIn(notesRoot, { duration: 700, sweep: 250 });
    } catch (e) {
      clearInterval(flicker);
      notesRoot.replaceWith(el("p", { class: "meta", text: "The lore could not be loaded." }));
    }
  }

  /* ---------- Hover thumbnails ----------
     Every row with a data-thumb (writing, talks, press, tweets, projects) shows one image that
     follows the mouse, easing toward the cursor on every frame and gliding from one row to the
     next. On touch screens it shows above the finger while it rests on a row, and goes away on
     lift or when the page starts scrolling. An empty data-thumb means "no image for this row". */
  const rows = document.querySelectorAll("li[data-thumb]");
  if (rows.length) {
    const thumb = el("img", { class: "thumb", alt: "", hidden: "" });
    document.body.append(thumb);
    const EASE = 0.35; // share of the remaining distance covered per frame
    const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let pointer = { x: -1, y: -1, touch: false };
    let size = { w: 0, h: 0 };
    let pos = null; // drawn position; null snaps to the target on the next frame
    let frame = 0;

    const measure = () => { size = { w: thumb.offsetWidth, h: thumb.offsetHeight }; };

    // Where the image belongs for the current pointer position.
    const target = () => {
      const { x, y, touch } = pointer;
      const { w, h } = size;
      const vw = document.documentElement.clientWidth, vh = innerHeight;
      let left, top;
      if (touch) {
        // Centered above the finger, so it isn't hidden under it.
        left = x - w / 2;
        top = y - h - 28;
        if (top < 8) top = y + 28;
      } else {
        left = x + 16;
        top = y + 16;
        if (left + w > vw - 8) left = x - w - 16;
        if (top + h > vh - 8) top = y - h - 16;
      }
      return {
        left: Math.min(Math.max(8, left), vw - w - 8),
        top: Math.min(Math.max(8, top), vh - h - 8),
      };
    };

    const render = () => {
      frame = 0;
      if (thumb.hidden) return;
      const t = target();
      if (!pos || pointer.touch || reduceMotion) pos = t;
      else {
        pos.left += (t.left - pos.left) * EASE;
        pos.top += (t.top - pos.top) * EASE;
      }
      thumb.style.transform = `translate3d(${pos.left.toFixed(1)}px, ${pos.top.toFixed(1)}px, 0)`;
      if (Math.abs(t.left - pos.left) > 0.2 || Math.abs(t.top - pos.top) > 0.2) frame = requestAnimationFrame(render);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(render); };

    const show = (row) => {
      if (!row.dataset.thumb) return hideThumb();
      const changed = thumb.getAttribute("src") !== row.dataset.thumb;
      if (changed) thumb.src = row.dataset.thumb;
      if (thumb.hidden) {
        thumb.hidden = false;
        pos = null;
      }
      if (changed || !size.w) measure();
      schedule();
    };
    const hideThumb = () => {
      if (thumb.hidden) return;
      thumb.hidden = true;
      pos = null;
    };
    // Images differ in height; re-measure once the new one is in.
    thumb.addEventListener("load", () => { measure(); schedule(); });

    // One listener for the whole page, so moving between projects never drops the image.
    addEventListener("pointermove", (e) => {
      const touch = e.pointerType === "touch";
      if (touch && thumb.hidden) return;
      pointer = { x: e.clientX, y: e.clientY, touch };
      if (touch) return schedule();
      const row = e.target.closest?.("li[data-thumb]");
      row ? show(row) : hideThumb();
    }, { passive: true });
    document.documentElement.addEventListener("pointerleave", () => { if (!pointer.touch) hideThumb(); });

    for (const row of rows) {
      row.addEventListener("pointerdown", (e) => {
        if (e.pointerType !== "touch") return;
        pointer = { x: e.clientX, y: e.clientY, touch: true };
        show(row);
      });
      // A long press would otherwise open the browser's link menu over the image.
      row.addEventListener("contextmenu", (e) => { if (!thumb.hidden && pointer.touch) e.preventDefault(); });
    }
    for (const type of ["pointerup", "pointercancel"]) {
      addEventListener(type, (e) => { if (e.pointerType === "touch") hideThumb(); });
    }
    // Scrolling moves the list under a still mouse: pick up whichever project is now under it.
    addEventListener("scroll", () => {
      if (pointer.touch) return hideThumb();
      if (pointer.x < 0) return;
      const row = document.elementFromPoint(pointer.x, pointer.y)?.closest("li[data-thumb]");
      row ? show(row) : hideThumb();
    }, { passive: true });

    // Preload and decode every thumbnail once the page has loaded, so even the first hover
    // shows the image instantly.
    const preload = () => rows.forEach((r) => {
      if (!r.dataset.thumb) return;
      const img = new Image();
      img.src = r.dataset.thumb;
      img.decode().catch(() => {});
    });
    if (document.readyState === "complete") preload();
    else addEventListener("load", preload, { once: true });
  }

  /* ---------- Term previews ----------
     Links to a term show its definition in a small box. Pointer devices only: on touch,
     links just navigate. (Images use the hover thumbnails above.) */
  const preview = document.getElementById("preview");
  if (!preview || !matchMedia("(hover: hover)").matches) return;

  function contentFor(a) {
    const term = document.querySelector(a.getAttribute("href"));
    if (!term) return null;
    const name = term.querySelector(".term-name").textContent;
    const def = term.querySelector(".term-def").textContent;
    const src = `${term.querySelector("time").textContent}. ${term.querySelector(".term-src").textContent}`;
    return el("div", { class: "text" }, [el("strong", { text: name }), " ", def, el("span", { class: "src", text: src })]);
  }

  function show(a) {
    const content = contentFor(a);
    if (!content) return;
    preview.replaceChildren(content);
    preview.hidden = false;
    const r = a.getBoundingClientRect();
    const w = preview.offsetWidth;
    const left = Math.min(Math.max(16, r.left), document.documentElement.clientWidth - w - 16);
    preview.style.left = `${left + scrollX}px`;
    preview.style.top = `${r.bottom + scrollY + 8}px`;
    // Flip above the link if it would run off the bottom of the viewport.
    const h = preview.offsetHeight;
    if (r.bottom + 8 + h > innerHeight && r.top - 8 - h > 0) preview.style.top = `${r.top + scrollY - h - 8}px`;
  }
  const hide = () => { preview.hidden = true; };

  document.addEventListener("pointerover", (e) => {
    const a = e.target.closest("a.term-link");
    if (a) show(a);
  });
  document.addEventListener("pointerout", (e) => {
    const a = e.target.closest("a.term-link");
    if (a && !a.contains(e.relatedTarget)) hide();
  });
  document.addEventListener("focusin", (e) => {
    const a = e.target.closest?.("a.term-link");
    a ? show(a) : hide();
  });
  addEventListener("scroll", hide, { passive: true });
})();
