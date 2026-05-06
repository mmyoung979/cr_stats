// Single source of truth for the active player's tag. Stored canonical with
// a leading "#" (e.g. "#PPJU2YGP0"). Components subscribe to "cr-stats-tag-change"
// on `window` so the navbar input and consumers stay in sync without a router-
// level context.

const KEY = "cr_stats_player_tag";
const EVENT_NAME = "cr-stats-tag-change";

export function getPlayerTag() {
    return localStorage.getItem(KEY);
}

export function setPlayerTag(raw) {
    const stripped = (raw || "").trim().replace(/^#/, "");
    if (!stripped) {
        clearPlayerTag();
        return;
    }
    localStorage.setItem(KEY, `#${stripped}`);
    window.dispatchEvent(new Event(EVENT_NAME));
}

export function clearPlayerTag() {
    localStorage.removeItem(KEY);
    window.dispatchEvent(new Event(EVENT_NAME));
}

export function subscribePlayerTag(handler) {
    window.addEventListener(EVENT_NAME, handler);
    return () => window.removeEventListener(EVENT_NAME, handler);
}

export function encodePlayerTag(tag) {
    // The Clash Royale player tag's "#" must be %23 in URLs.
    return encodeURIComponent(tag);
}
