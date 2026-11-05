# Sources

How to reach each source in `SKILL.md`, the files each search agent writes and the board settings. Before searching, ask whether to connect each of Pond, marked.dev, Are.na, Cosmos, Pinterest and Mobbin that is missing. When none are connected, wait for the answer.

## Queries

Give each search agent the brief, its parts with their synonyms, the platform and the urls already on the board. Per part, run three to five short queries built from the synonyms, plus one image search. A long query can return nothing while its short parts match.

| Brief part | Queries |
| --- | --- |
| Top bar | `"top bar"`, `"app header"`, `"toolbar"`, `"navigation bar"` |
| Empty state | `"empty state"`, `"blank slate"`, `"zero state"`, `"no results"` |
| Row density | `"dense table"`, `"compact list"`, `"data grid"` |

## Candidates

Each agent writes one file, `.gather/<brief>/candidates/<source>.json`, holding an array:

```json
[
  {
    "title": "Linear",
    "source": "Mobbin",
    "url": "https://mobbin.com/screens/4c03063e",
    "media": "https://bytescale.mobbin.com/…/4c03063e.webp",
    "kind": "image",
    "group": "Grouping",
    "note": "Take the grouped list, not the colours.",
    "details": { "Kind": "Shipped" }
  }
]
```

- `url` is the original and identifies the item, so each one is unique.
- `media` is a full URL, an absolute local path or a path inside `.gather/<brief>/`. The collector downloads or copies it into `img/`.
- `kind` is `image` or `video`. Without it, the file extension decides.
- `poster` is optional, a still for a video.
- `source` puts › between a library and the board inside it, such as `Pond › Are.na`. Items from Pond and marked.dev lead each group, except `marked.dev › Explore`.
- `details` adds rows to the viewer, such as `{ "Creator": "Kevin", "Style": ["Minimal", "Clean"] }`.

## Board

`.gather/<brief>/board.json` sets what the candidates cannot:

```json
{
  "title": "Settings Page",
  "brief": "Desktop settings page, looking for grouping and density.",
  "groups": [{ "title": "Grouping", "description": "How long lists of options are split up." }],
  "cut": ["https://mobbin.com/screens/9f12ab07"]
}
```

The board title takes Title Case. Groups appear in this order, and any group named only by a candidate follows them. A url under `cut` stays off the board.

Run the collector from anywhere:

| Command | Does |
| --- | --- |
| `node collect.mjs .gather/<brief>` | Builds the board once |
| `node collect.mjs .gather/<brief> --serve` | Serves it, rebuilds on every change and keeps the board reloading |
| `node collect.mjs .gather/<brief> --done` | Builds it a last time and stops the reloading |

Downloads run 8 at a time and are cached under a hash of the media url, so a second run fetches only what is new. A download that fails is named in the output and left off the board.

## What the user gave

| Input | Reach it with |
| --- | --- |
| Open browser tabs | List the tabs and read each page |
| Screenshots in the thread | Read the images |
| Design files | The Figma MCP `get_screenshot` on the linked node |
| Live sites | Open the page. For exact values, hand over to `match` |

## Live capture

When the best reference is a shipped product, open its page in the browser and screenshot the part the brief names. Use the screenshot's path as `media`, the live page as `url` and `Live` as `source`. Stop at a login and say so.

## Pond

The user's own library of saves from X, Instagram, Pinterest, Are.na, Cosmos, Savee, Dribbble, Behance, Threads, Bluesky, Tumblr, Reddit, TikTok, YouTube, Vimeo, Unsplash, GitHub, Substack, the web and local files. The Pond choice downloads from https://pond.raphaelsalaja.com and connects under Settings, Model Context Protocol. Connecting an account needs the Pond browser extension, from Browser Extension in the library menu. Pond runs as a local MCP server over stdio:

```json
{
  "mcpServers": {
    "pond": {
      "command": "/Applications/Pond.app/Contents/MacOS/Pond",
      "args": ["--mcp"]
    }
  }
}
```

Copy the exact command from Pond, under Settings, Model Context Protocol. The Search Saves switch under Access must be on.

| Tool | Use |
| --- | --- |
| `search_library` | Search by meaning, such as `{ "query": "website design" }` |
| `search_library` with `source` | Only one platform: `arena`, `cosmos`, `pinterest`, `savee`, `dribbble`, `behance`, `twitter` and the rest of the list above |
| `search_library` with `visual: { "kind": "saveId", "id" }` | Saves that look like one the user likes |
| `search_library` with `media: ["video"]` | Motion references only |
| `search_library` with `folderId` | Inside one of the user's folders, from `list_folders` |
| `query_library` | Exact filters: `keywords` limited by `keywordScopes`, and `scope` by source, folder, tag or `savedSince`, with a sort and `cursor` paging |
| `list_folders` | Find the user's own groupings before searching |
| `read_save` | Caption, text in images, note, link and metadata, or one part with `field`: `caption`, `ocr`, `transcript`, `notes` or `description` |
| `grep_library` | Exact words in `query` inside captions, transcripts, notes, titles and image text |
| `open_save`, `apply_filter` | Show a result in the Pond window |

`compress_images` replaces the originals in the library, so gathering never calls it.

For an image search, find the save closest to what the user gave, then pass its id as `visual`. Run it again from the best two or three results.

A save's files sit in `<Library>.pond/items/<id>.info/`, so `media` is the absolute path to the original file. The Local API also saves URLs with `POST /enqueue`, and `created: false` means the URL is already saved. Its token stays in Pond's settings and is never pasted into chat.

## marked.dev

The user's saved interfaces and motion from X, Pinterest and the web, each credited to its maker. It also holds Explore, a public catalogue browsed by what moves: hover, scroll and drag. It runs as a remote MCP server with no API key. Copy the config from https://marked.dev/mcp, then approve the connection in the browser.

| Tool | Use |
| --- | --- |
| `list_collections`, `get_collection` | The user's own collections, read before searching |
| `search_refs` | The user's saved refs, with `unsorted: true` for refs in no collection |
| `get_ref` | A saved ref's media, source and author |
| `search_explore`, `get_explore_ref` | Public refs, with `category: "motion"` for what moves |
| `search_refs` or `search_explore` with filters | `categories` (`app`, `saas`, `software`, `motion`), `platforms` (`x`, `pinterest`, `other`), `tags` and `authors` |
| `save_ref` | Save a pick into a collection, only when the user asks |

Search it by interaction when the brief is about motion, such as "hover card lift" or "scroll reveal". A ref's video is the `media`, with `kind: "video"`.

## Boards

| Source | Reach it with |
| --- | --- |
| Are.na | The user's channels in the logged-in browser |
| Cosmos | The user's clusters in the logged-in browser. Open an element and use its similar results for an image search |
| Pinterest | The user's boards in the logged-in browser or with computer use. A pin's More Ideas works as an image search |

With Pond connected, search these through Pond with `source` set to `arena`, `cosmos` or `pinterest`. Open the browser only for a channel Pond hasn't imported or for Cosmos's similar results.

Read the user's existing channel and board names before creating one. When the browser is signed out, ask the user to sign in, then read their boards.

## Pattern libraries

| Tool | Use |
| --- | --- |
| Mobbin `search_screens` | Single screens. Set `platform` to `web` for desktop and web work |
| Mobbin `search_flows` | Multi-step flows, such as onboarding or checkout |
| Mobbin `search_sections` | Sections of marketing sites |
| Mobbin `exclude_screen_ids` | Leave out screens already shown when the user asks for more |
| Mobbin `list_collections`, `get_collection_contents` | The user's own saved collections, searched first. `id: "all-saved"` reads everything saved, one `content_type` and `platform` per call |
| Mobbin `create_collection`, `save_content` | Save picks into a new or existing collection, only when the user asks |
| Mobbin `add_comment` | Note on a saved item why it was picked, only when the user asks |

A Mobbin result's `image_url` is the `media` and its `mobbin_url` is the `url`. The image link expires after 30 days, which the download covers.

## Curated galleries

Open them in the browser. Prefer galleries picked by hand to ones that take paid submissions. Dribbble and Behance are mostly concepts, so mark what comes from them.

| Gallery | What it holds |
| --- | --- |
| [Recent](https://recent.design) | High-end sites, branding, motion and type, picked daily. The Web filter shows sites only |
| [Refero](https://refero.design) | Real product screens, flows, patterns and elements, mostly web |
| [Savee](https://savee.com) | Graphic, brand, editorial and web work saved by designers. Searches by colour and image. Pond reads it as `savee` |
| [Cosmos](https://www.cosmos.so) | Visual similarity, colour and motion search, with AI images hidden on request |
| [Siteinspire](https://www.siteinspire.com) | Editorial, typographic sites, filtered by style, type and subject |
| [Minimal Gallery](https://minimal.gallery) | Restrained, functional sites |
| [Land-book](https://land-book.com) | Landing pages, filtered by page type and style |
| [Saaspo](https://saaspo.com) | Software landing, pricing and product pages |
| [Page Flows](https://pageflows.com) | Recorded flows from live web and mobile apps |
