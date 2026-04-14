/**
 * Helpers for deciding whether a media URL can be rendered inline as an
 * `<img>`/preview, or whether it needs to fall back to a link card because
 * the source gate the browser out (Slack file CDN, Discord attachments,
 * Teams blobs, etc.).
 */

/** Hosts whose media endpoints require bearer/cookie auth and will 403 the
 * browser regardless of the URL's query params. We render these as link
 * cards instead of broken images.
 *
 * Discord CDN hosts (`cdn.discordapp.com`, `media.discordapp.net`) are
 * NOT in this list: their URLs are publicly accessible for the lifetime
 * of the signed query string (`?ex=...&hm=...`). When they eventually
 * 403 (expired signature), the `<img> onError` handler handles it.
 */
const AUTH_GATED_HOSTS = [
  "files.slack.com",
  "slack-files.com",
  "graph.microsoft.com",
  "attachments.office.net",
];

export function isAuthGatedMediaUrl(url: string | undefined): boolean {
  if (!url) return false;
  try {
    const host = new URL(url).host.toLowerCase();
    return AUTH_GATED_HOSTS.some((h) => host === h || host.endsWith(`.${h}`));
  } catch {
    return false;
  }
}

export function mediaHostLabel(url: string | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).host;
  } catch {
    return null;
  }
}
