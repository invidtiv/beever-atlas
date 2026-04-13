# Media Gallery Template

Render image/file attachments returned by `search_media_references` as a markdown gallery.

## Format

```
## Media: <topic or query>

- ![<caption>](<thumbnail_or_url>)
  **<caption>** — <one-line context> [src:src_xxx inline]
- ![<caption>](<thumbnail_or_url>)
  **<caption>** — <one-line context> [src:src_xxx inline]
```

## Rules

- Use the `inline` variant of the src tag (`[src:src_xxx inline]`) so the UI renders the attachment beside the citation.
- Caption = filename or short descriptive label from the tool result.
- Context line ≤ 80 characters; describes *why* this media is relevant.
- Group related media under one `##` heading; if ≥ 6 items, split into sub-headings by topic.
- If the tool returned no media, state "No media attachments found for this query." and do NOT fabricate entries.

## Example

```
## Media: login screen mockups

- ![login-v1.png](https://.../login-v1.png)
  **login-v1.png** — first mockup from @alice, August. [src:src_aaa1111111 inline]
- ![login-v2-final.png](https://.../login-v2-final.png)
  **login-v2-final.png** — final design shipped to prod. [src:src_bbb2222222 inline]
```
