/**
 * Talk view: conversation orb driven by the RPC activity stream.
 * Audio I/O runs entirely in Python; the orb doubles as the mic toggle.
 * Robot stays live, tapping the orb only mutes or unmutes the user's mic.
 */

import { applyPersonality, experimentLog, getMicState, getResearchStatus, listPersonalities, setMicMuted, subscribe } from "../api.js";
import { ORB_STATES } from "../constants.js";
import { createOrb, mapActivityToState } from "../orb.js";
import { consumePendingApply } from "../pending-apply.js";
import { setPersonality } from "../personality-badge.js";
import { h, prettifyProfileName } from "../ui.js";

const CAPTION_BY_STATE = Object.freeze({
  [ORB_STATES.MUTED]: "Muted",
  [ORB_STATES.IDLE]: "Ready",
  [ORB_STATES.CONNECTING]: "Connecting to the backend...",
  [ORB_STATES.LISTENING]: "Listening",
  [ORB_STATES.THINKING]: "Thinking",
  [ORB_STATES.SPEAKING]: "Speaking",
  [ORB_STATES.ERROR]: "Connection error",
});

export async function mountTalkView({ outlet, signal }) {
  const pending = consumePendingApply();
  const micStatePromise = getMicState().catch((error) => {
    console.warn("Failed to load microphone state", error);
    return null;
  });
  let muted = false;
  let micReady = false;
  let togglePending = false;
  let activePersonality = null;
  let subscription = null;
  let researchSubscription = null;
  let researchRefresh = 0;
  const references = h("aside", { class: "talk__references", hidden: true, "aria-label": "Research references" });
  const logStatus = h("p", { class: "talk__log-status", role: "status", "aria-live": "polite" }, "Checking recording…");
  const downloadLog = h("button", { class: "btn btn--ghost", type: "button", onclick: onDownloadLog }, "Download data");
  const clearLog = h("button", { class: "btn btn--ghost", type: "button", onclick: onClearLog }, "Clear data…");
  let logBusy = false;

  const caption = h(
    "p",
    { class: "talk__caption", role: "status", "aria-live": "polite" },
    CAPTION_BY_STATE[ORB_STATES.CONNECTING]
  );
  const defaultAction = document.querySelector('[data-component="default-personality-action"]');
  if (defaultAction) {
    defaultAction.hidden = true;
    defaultAction.addEventListener("click", onSetDefault);
  }
  const orb = createOrb({
    initialState: ORB_STATES.CONNECTING,
    onStateChange: (state) => {
      caption.textContent = CAPTION_BY_STATE[state] || "";
    },
  });
  orb.root.disabled = true;
  orb.root.addEventListener("click", onMicTap);
  syncMicAria();

  signal.addEventListener("abort", cleanup, { once: true });

  const view = h(
    "section",
    { class: "view view--talk" },
    h("div", { class: "talk__orb-wrap" }, orb.root),
    caption,
    references,
    h("div", { class: "talk__log", "aria-label": "Experiment recording" },
      logStatus,
      h("div", { class: "talk__log-actions" }, downloadLog, clearLog)
    )
  );
  outlet.replaceChildren(view);
  researchSubscription = subscribe("conversation.activity", ({ reason } = {}) => {
    if (reason === "research_updated") void refreshResearch();
  });
  void refreshResearch();
  void refreshLog();
  const logTimer = setInterval(refreshLog, 10000);

  if (pending) {
    caption.textContent = `Applying "${prettifyProfileName(pending.name)}"…`;
    try {
      await pending.promise;
    } catch (error) {
      if (signal.aborted) return;
      orb.setState(ORB_STATES.ERROR);
      caption.textContent = `Failed to apply personality: ${error?.message || error}`;
      return;
    }
    if (signal.aborted) return;
    // The activity subscription will flip the orb to its resting state next tick.
    caption.textContent = CAPTION_BY_STATE[ORB_STATES.CONNECTING];
    void refreshPersonalityState();
  } else {
    // Deep link to /talk with no pending apply: refresh the header badge.
    void refreshPersonalityState();
  }

  const micState = await micStatePromise;
  if (micState) muted = Boolean(micState.muted);
  if (signal.aborted) return;
  micReady = true;
  orb.root.disabled = false;
  syncMicAria();

  subscription = subscribeConversationEvents({
    // Re-sync mic state after subscribing: another tab may have toggled it.
    onReady: async () => {
      if (!togglePending) {
        try {
          muted = Boolean((await getMicState())?.muted);
        } catch {
          // keep the last known mute state
        }
      }
      if (signal.aborted) return;
      orb.setState(restingState());
      caption.textContent = CAPTION_BY_STATE[restingState()];
      syncMicAria();
    },
    onActivity: (reason) => {
      if (muted) return;
      const next = mapActivityToState(reason);
      if (next == null) return;
      orb.setState(next);
    },
  });

  function cleanup() {
    clearInterval(logTimer);
    subscription?.close();
    researchSubscription?.();
    orb.dispose();
    if (defaultAction) {
      defaultAction.hidden = true;
      defaultAction.removeEventListener("click", onSetDefault);
    }
  }

  async function refreshLog() {
    if (logBusy) return;
    try {
      const log = await experimentLog();
      if (signal.aborted || logBusy) return;
      logStatus.textContent = log.error || `Text recording on · ${(log.bytes / 1024).toFixed(1)} KB saved`;
      logStatus.title = log.path;
      downloadLog.disabled = !log.bytes;
      clearLog.disabled = !log.bytes && !log.error;
    } catch (error) {
      if (!signal.aborted && !logBusy) logStatus.textContent = `Recording status unavailable: ${error.message}`;
    }
  }

  async function onDownloadLog() {
    if (logBusy) return;
    logBusy = true;
    downloadLog.disabled = clearLog.disabled = true;
    try {
      const log = await experimentLog();
      if (!log.bytes) throw new Error("No recorded conversation yet.");
      const chunks = [];
      let offset = 0;
      while (offset < log.bytes) {
        if (signal.aborted) return;
        const chunk = await experimentLog({ action: "read", offset, limit: log.bytes, generation: log.generation });
        if (chunk.next_offset <= offset) throw new Error("Download stopped. Please try again.");
        chunks.push(Uint8Array.from(atob(chunk.content), (char) => char.charCodeAt(0)));
        offset = chunk.next_offset;
        logStatus.textContent = `Downloading data… ${Math.round(offset / log.bytes * 100)}%`;
      }
      if (signal.aborted) return;
      const url = URL.createObjectURL(new Blob(chunks, { type: "application/gzip" }));
      const link = h("a", { href: url, download: log.filename, hidden: true });
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      logStatus.textContent = "Downloaded. Recording continues in the same file.";
    } catch (error) {
      if (!signal.aborted) logStatus.textContent = `Could not download: ${error.message}`;
    } finally {
      logBusy = false;
      downloadLog.disabled = clearLog.disabled = false;
    }
  }

  async function onClearLog() {
    if (logBusy || !window.confirm("Permanently clear all saved experiment data? Download it first if you need a copy. New conversation will continue recording.")) return;
    logBusy = true;
    downloadLog.disabled = clearLog.disabled = true;
    try {
      await experimentLog({ action: "clear", confirm: true });
      if (!signal.aborted) logStatus.textContent = "Saved data cleared. New conversation will continue recording.";
    } catch (error) {
      if (!signal.aborted) logStatus.textContent = `Could not clear data: ${error.message}`;
    } finally {
      logBusy = false;
      downloadLog.disabled = clearLog.disabled = false;
    }
  }

  async function refreshResearch() {
    const refresh = ++researchRefresh;
    try {
      const research = await getResearchStatus();
      if (signal.aborted || refresh !== researchRefresh) return;
      references.replaceChildren();
      const sources = (research.sources || []).filter((source) => {
        try {
          const url = new URL(source.url);
          return ["http:", "https:"].includes(url.protocol) && !url.username;
        } catch {
          return false;
        }
      });
      references.hidden = false;
      const snippets = research.snippets || [];
      if (research.status === "researching") {
        references.append(h("strong", {}, "Research running"));
        references.append(h("p", {}, research.question || "Checking your question while we talk…"));
      } else if (["unavailable", "disabled"].includes(research.status)) {
        references.append(h("p", {}, research.error || "Background research is unavailable right now."));
      } else if (snippets.length || sources.length) {
        references.append(h("strong", {}, research.web_search_calls > 0 ? "Research complete · web searched" : "Research complete · no web search used"));
        for (const snippet of snippets) {
          references.append(h("p", {}, snippet.replace(/\[([^\]]+)\]\(https?:\/\/[^\s)]+\)/g, "$1")));
        }
        references.append(h("ul", {}, sources.map((source) => h("li", {},
          h("a", { href: source.url, target: "_blank", rel: "noopener noreferrer" }, source.title || source.url)
        ))));
      } else {
        references.append(h("p", {}, research.web_search_enabled ? "Research ready · web search available" : "Research ready · web search off"));
      }
      if (research.model) references.append(h("small", {}, `Research model: ${research.model}`));
    } catch (error) {
      if (!signal.aborted) console.warn("Could not load research references", error);
    }
  }

  function restingState() {
    return muted ? ORB_STATES.MUTED : ORB_STATES.IDLE;
  }

  async function onMicTap() {
    if (!micReady || togglePending) return;
    togglePending = true;
    try {
      const data = await setMicMuted(!muted);
      muted = Boolean(data?.muted);
    } catch (error) {
      if (!signal.aborted) {
        caption.textContent = `Failed to toggle the microphone: ${error?.message || error}`;
      }
      return;
    } finally {
      togglePending = false;
    }
    if (signal.aborted) return;
    orb.setState(restingState());
    // setState skips unchanged states, so set the caption explicitly
    caption.textContent = CAPTION_BY_STATE[restingState()];
    syncMicAria();
  }

  async function refreshPersonalityState() {
    const personalityState = await fetchPersonalityState();
    if (signal.aborted || personalityState == null) return;
    activePersonality = personalityState.current;
    setPersonality(personalityState.current);
    const shouldHide = personalityState.locked || personalityState.current === personalityState.startup;
    if (defaultAction) {
      defaultAction.hidden = shouldHide;
    }
  }

  async function onSetDefault() {
    if (!defaultAction || !activePersonality) return;
    defaultAction.disabled = true;
    caption.textContent = `Saving "${prettifyProfileName(activePersonality)}" as default...`;
    try {
      await applyPersonality(activePersonality, { persist: true });
      if (signal.aborted) return;
      defaultAction.hidden = true;
      caption.textContent = `"${prettifyProfileName(activePersonality)}" will be used at startup.`;
    } catch (error) {
      if (!signal.aborted) {
        caption.textContent = `Failed to save default: ${error?.message || error}`;
      }
    } finally {
      defaultAction.disabled = false;
    }
  }

  function syncMicAria() {
    if (!micReady) {
      orb.root.setAttribute("aria-pressed", "false");
      orb.root.setAttribute("aria-label", "Loading microphone state");
      return;
    }
    orb.root.setAttribute("aria-pressed", String(!muted));
    orb.root.setAttribute("aria-label", muted ? "Unmute microphone" : "Mute microphone");
  }
}

async function fetchPersonalityState() {
  try {
    const data = await listPersonalities();
    const current = data?.current;
    if (!current) return null;
    return {
      current,
      startup: data?.startup || "default",
      locked: Boolean(data?.locked),
    };
  } catch {
    return null;
  }
}

function subscribeConversationEvents({ onActivity, onReady } = {}) {
  if (typeof onActivity !== "function") {
    throw new TypeError("subscribeConversationEvents: onActivity is required");
  }

  // Activity reasons now arrive as conversation.activity notifications over the
  // /rpc WebSocket; the shared client (api.js) owns reconnection.
  const unsubscribe = subscribe("conversation.activity", (params) => {
    const reason = (params?.reason || "").trim();
    if (reason) onActivity(reason);
  });

  // The socket connects lazily, so schedule the initial mic and orb sync.
  if (typeof onReady === "function") Promise.resolve().then(onReady);

  return {
    close() {
      unsubscribe();
    },
  };
}
