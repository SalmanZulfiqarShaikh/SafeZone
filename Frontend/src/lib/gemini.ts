/**
 * The website assistant, client side.
 *
 * This file used to hold the Gemini API key, the model name and the entire
 * system prompt, and called Google directly from the browser. Vite inlines
 * `VITE_*` values into the bundle it ships, so the key was readable by anyone
 * who opened devtools -- and scrapers crawl deployed bundles for `AIza...`
 * strings automatically. The realistic cost was not drama but a burned quota,
 * which means the assistant dying in the middle of a demo.
 *
 * So the key, the model choice and the prompt all moved to the backend
 * (`Backend/services/assistant.py`, `Backend/routes/chat.py`). What is left
 * here is the part that genuinely belongs in the browser: shaping a request
 * and turning a failure into something a worried person can act on.
 *
 * The exported surface is unchanged on purpose -- `useChatbot` and the widget
 * did not have to be touched.
 */

/** Kept for compatibility with `useChatbot`. The number now comes from the
 *  backend's own config via `useWhatsapp`, so there is nothing to read from
 *  the environment here and nothing worth putting in the bundle. */
export const ENV_BOT_WHATSAPP_URL = "";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  imageUrl?: string;
  timestamp: number;
}

export interface AttachedImageData {
  base64: string;
  mimeType: string;
  previewUrl: string;
}

interface GenerateReplyOptions {
  history: ChatMessage[];
  currentMessage: string;
  image?: AttachedImageData | null;
  /** Accepted so the call site keeps working. The server fills the WhatsApp
   *  link into the prompt from its own config, so a page cannot steer which
   *  number the assistant hands out. */
  whatsappUrl?: string;
}

/** The server answers failures with a sentence meant for a visitor, so it is
 *  shown as-is. This is only the fallback for when the request never arrived. */
const OFFLINE =
  "I can't reach the assistant right now. Message SafeZone on WhatsApp and someone will see it.";

/**
 * Ask the SafeZone backend to answer one question.
 *
 * Never throws a provider error at the UI: whatever goes wrong, the message
 * that comes back points at WhatsApp, because the number works whether or not
 * this endpoint does.
 */
export async function generateGeminiReply({
  history,
  currentMessage,
  image,
}: GenerateReplyOptions): Promise<string> {
  // Only role and text travel. Ids, timestamps and blob preview URLs are of no
  // use to the model and the preview URLs are not valid anywhere but this tab.
  const body = {
    message: currentMessage.trim(),
    history: history.map((message) => ({
      role: message.role,
      text: message.text,
    })),
    image: image?.base64
      ? { base64: image.base64, mimeType: image.mimeType || "image/jpeg" }
      : null,
  };

  let response: Response;
  try {
    response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    // The backend is not running, or the network went. Both are the same
    // thing to the person reading it.
    throw new Error(OFFLINE);
  }

  if (!response.ok) {
    let detail = "";
    try {
      detail = (await response.json())?.detail ?? "";
    } catch {
      detail = "";
    }
    throw new Error(detail || OFFLINE);
  }

  const data = await response.json();
  const reply = typeof data?.reply === "string" ? data.reply.trim() : "";
  return (
    reply ||
    "I wasn't able to answer that. Message SafeZone on WhatsApp and someone will see it."
  );
}
