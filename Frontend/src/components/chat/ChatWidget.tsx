import { useState, useRef, useEffect } from "react";
import {
  MessageSquare,
  X,
  Send,
  Paperclip,
  AlertTriangle,
  Bot,
  ExternalLink,
  ChevronDown,
} from "lucide-react";
import { FaWhatsapp } from "react-icons/fa6";
import { useChatbot, MAX_MESSAGES } from "../../hooks/useChatbot";
import { useWhatsapp } from "../../hooks/useWhatsapp";
import { ENV_BOT_WHATSAPP_URL } from "../../lib/gemini";
import { cn } from "../../lib/utils";

/**
 * Formats plain text containing URLs or line breaks into readable elements with clickable links.
 */
function FormattedMessageText({ text }: { text: string }) {
  // Regex to detect URLs
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const lines = text.split("\n");

  return (
    <div className="space-y-1.5">
      {lines.map((line, lineIdx) => {
        if (!line.trim()) return <div key={lineIdx} className="h-1.5" />;

        const parts = line.split(urlRegex);
        return (
          <p key={lineIdx} className="break-words">
            {parts.map((part, partIdx) => {
              if (part.match(urlRegex)) {
                // Strip trailing punctuation (. , ! ? ) ] " ') that belonged to the sentence, not the URL
                const punctMatch = part.match(/([.,;:!?)"'>]+)$/);
                const trailingPunct = punctMatch ? punctMatch[1] : "";
                let cleanUrl = trailingPunct ? part.slice(0, -trailingPunct.length) : part;

                const isWa = cleanUrl.includes("wa.me") || cleanUrl.includes("whatsapp.com");
                if (isWa && cleanUrl.includes("wa.me/")) {
                  // Ensure wa.me URL has no trailing slash or stray characters on the phone number
                  cleanUrl = cleanUrl.replace(/wa\.me\/(\d+).*$/, "wa.me/$1");
                }

                return (
                  <span key={partIdx} className="inline">
                    <a
                      href={cleanUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={cn(
                        "inline-flex items-center gap-1 font-medium underline underline-offset-2 hover:opacity-80",
                        isWa ? "text-emerald-700 dark:text-emerald-400 font-semibold" : "text-sz-water"
                      )}
                    >
                      {isWa && <FaWhatsapp className="h-3 w-3 shrink-0" aria-hidden="true" />}
                      {isWa ? "Open SafeZone on WhatsApp" : cleanUrl.length > 36 ? `${cleanUrl.slice(0, 36)}...` : cleanUrl}
                      <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                    </a>
                    {trailingPunct}
                  </span>
                );
              }
              return <span key={partIdx}>{part}</span>;
            })}
          </p>
        );
      })}
    </div>
  );
}

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [inputVal, setInputVal] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const whatsapp = useWhatsapp();
  const activeWhatsappUrl = ENV_BOT_WHATSAPP_URL || whatsapp.url || "https://wa.me";

  const {
    messages,
    isLoading,
    error,
    remainingMessages,
    isRateLimited,
    attachedImage,
    attachImage,
    removeAttachedImage,
    sendMessage,
  } = useChatbot();

  // Scroll to bottom on new message
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading, isOpen]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputVal.trim() && !attachedImage) return;
    if (isLoading || isRateLimited) return;

    const currentText = inputVal;
    setInputVal("");
    await sendMessage(currentText);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      attachImage(file);
    }
    // Reset file input so selecting the same file again triggers change
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <>
      {/* Floating launcher button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={isOpen ? "Close SafeZone assistant" : "Ask SafeZone assistant"}
        className={cn(
          "fixed bottom-5 right-5 sm:bottom-6 sm:right-6 z-40 flex items-center gap-2.5 rounded-full px-4 py-3 shadow-lg transition-all duration-200 cursor-pointer",
          "border border-sz-header-line bg-sz-header text-sz-header-text hover:bg-sz-header/90 hover:scale-105 active:scale-95",
          isOpen && "ring-2 ring-sz-water/50"
        )}
      >
        <span className="relative flex h-3 w-3">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500" />
        </span>
        <span className="flex items-center gap-2 text-[14px] font-medium">
          {isOpen ? (
            <>
              <X className="h-4 w-4" />
              <span>Close Assistant</span>
            </>
          ) : (
            <>
              <MessageSquare className="h-4 w-4" />
              <span>Ask SafeZone</span>
            </>
          )}
        </span>
      </button>

      {/* Chat Popover Window */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="SafeZone Assistant Chat"
          className="fixed bottom-20 right-3 sm:right-6 z-40 flex h-[580px] max-h-[82vh] w-[calc(100vw-1.5rem)] sm:w-[420px] flex-col overflow-hidden rounded-2xl border border-sz-line bg-sz-panel text-sz-text shadow-2xl animate-in fade-in slide-in-from-bottom-4 duration-200"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-sz-line bg-sz-raised px-4 py-3 text-sz-text">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sz-header text-sz-header-accent">
                <Bot className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <h3 className="text-[14px] font-semibold tracking-tight">SafeZone Assistant</h3>
                  <span className="rounded bg-sz-line px-1.5 py-0.2 text-[10px] font-medium text-sz-text-2">
                    AI
                  </span>
                </div>
                <p className="text-[11px] text-sz-text-3">Ask about triage, coverage & protocols</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span
                title={`${remainingMessages} of ${MAX_MESSAGES} messages left this hour`}
                className={cn(
                  "rounded-full px-2 py-0.5 text-[11px] font-mono",
                  isRateLimited
                    ? "bg-red-500/10 text-red-600 dark:text-red-400 font-semibold"
                    : "bg-sz-line text-sz-text-2"
                )}
              >
                {remainingMessages}/{MAX_MESSAGES} left
              </span>

              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="rounded-lg p-1 text-sz-text-3 hover:bg-sz-line hover:text-sz-text transition-colors"
                aria-label="Minimize chat"
              >
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Sticky Emergency Warning Banner */}
          <div className="border-b border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-[12px] text-amber-900 dark:text-amber-200">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
              <div className="flex-1 leading-snug">
                <span>
                  <strong>Not an emergency channel.</strong> Nobody is dispatched here. For urgent
                  danger:
                </span>
                <a
                  href={activeWhatsappUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1.5 font-medium text-emerald-700 dark:text-emerald-400 underline underline-offset-2 hover:opacity-90 block"
                >
                  <FaWhatsapp className="h-3.5 w-3.5" />
                  Message SafeZone on WhatsApp
                </a>
              </div>
            </div>
          </div>

          {/* Messages list */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 sz-scroll bg-sz-base/20">
            {messages.map((msg) => {
              const isUser = msg.role === "user";
              return (
                <div
                  key={msg.id}
                  className={cn("flex flex-col gap-1.5", isUser ? "items-end" : "items-start")}
                >
                  {/* Attached photo in message bubble if present */}
                  {msg.imageUrl && (
                    <div className="relative mb-1 max-w-[240px] overflow-hidden rounded-xl border border-sz-line shadow-xs">
                      <img
                        src={msg.imageUrl}
                        alt="Disaster hazard attachment"
                        className="h-auto w-full max-h-48 object-cover"
                      />
                    </div>
                  )}

                  <div
                    className={cn(
                      "rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed shadow-xs",
                      isUser
                        ? "bg-sz-header text-sz-header-text rounded-br-xs max-w-[85%]"
                        : "bg-sz-panel border border-sz-line text-sz-text rounded-bl-xs max-w-[90%]"
                    )}
                  >
                    <FormattedMessageText text={msg.text} />
                  </div>

                  <span className="px-1 text-[10px] text-sz-text-3 font-mono">
                    {new Date(msg.timestamp).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              );
            })}

            {/* Loading indicator */}
            {isLoading && (
              <div className="flex items-start gap-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-sz-line text-sz-text-2">
                  <Bot className="h-3.5 w-3.5" />
                </div>
                <div className="rounded-2xl rounded-bl-xs border border-sz-line bg-sz-panel px-3.5 py-2 text-[12px] text-sz-text-2 shadow-xs">
                  <div className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sz-text-3 [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sz-text-3 [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-sz-text-3" />
                    <span className="ml-1 text-[11px] text-sz-text-3">Thinking...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Pending attached image preview */}
          {attachedImage && (
            <div className="border-t border-sz-line bg-sz-raised px-4 py-2 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <img
                  src={attachedImage.previewUrl}
                  alt="Attachment preview"
                  className="h-10 w-10 rounded-md object-cover border border-sz-line"
                />
                <div className="text-[12px]">
                  <p className="font-medium text-sz-text">Disaster Photo Attached</p>
                  <p className="text-[11px] text-sz-text-3">Assistant will analyze hazards</p>
                </div>
              </div>
              <button
                type="button"
                onClick={removeAttachedImage}
                className="rounded-full p-1 text-sz-text-3 hover:bg-sz-line hover:text-sz-text"
                aria-label="Remove image"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Error notice if any */}
          {error && !isLoading && (
            <div className="border-t border-red-500/30 bg-red-500/10 px-4 py-1.5 text-[11px] text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          {/* Input Box */}
          <div className="border-t border-sz-line bg-sz-panel p-3">
            {isRateLimited ? (
              <div className="rounded-lg border border-sz-line bg-sz-raised p-2.5 text-center text-[12px] text-sz-text-2">
                <p className="font-medium text-sz-text">Hourly Limit Reached ({MAX_MESSAGES}/{MAX_MESSAGES})</p>
                <p className="text-[11px] text-sz-text-3 mt-0.5">
                  Resets in an hour. For urgent assistance, please contact SafeZone on WhatsApp.
                </p>
              </div>
            ) : (
              <form onSubmit={handleSend} className="flex items-end gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png, image/jpeg, image/webp"
                  onChange={handleFileChange}
                  className="hidden"
                  id="safezone-chat-image-input"
                />

                <label
                  htmlFor="safezone-chat-image-input"
                  title="Attach disaster / hazard photo for safety precautions"
                  className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-sz-line bg-sz-raised text-sz-text-2 hover:bg-sz-line hover:text-sz-text transition-colors"
                >
                  <Paperclip className="h-4 w-4" />
                </label>

                <div className="relative flex-1">
                  <textarea
                    rows={1}
                    value={inputVal}
                    onChange={(e) => setInputVal(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      attachedImage
                        ? "Ask about this situation..."
                        : "Ask a question about SafeZone..."
                    }
                    className="w-full resize-none rounded-xl border border-sz-line bg-sz-raised px-3 py-2 text-[13px] text-sz-text placeholder:text-sz-text-3 focus:border-sz-water focus:outline-hidden focus:ring-1 focus:ring-sz-water max-h-24"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoading || (!inputVal.trim() && !attachedImage)}
                  aria-label="Send message"
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sz-header text-sz-header-text disabled:opacity-40 hover:bg-sz-header/90 transition-colors"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
            )}
            <p className="mt-1.5 text-center text-[10px] text-sz-text-3">
              Direct AI response • Prototype by Team NovaStrikers
            </p>
          </div>
        </div>
      )}
    </>
  );
}
