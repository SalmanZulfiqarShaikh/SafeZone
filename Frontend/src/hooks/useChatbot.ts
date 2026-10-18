import { useState, useEffect, useCallback } from "react";
import {
  generateGeminiReply,
  ENV_BOT_WHATSAPP_URL,
  type ChatMessage,
  type AttachedImageData,
} from "../lib/gemini";
import { useWhatsapp } from "./useWhatsapp";

const STORAGE_KEY = "devex_chatbot_rate_limit";
export const MAX_MESSAGES = 10;
export const RESET_TIME = 60 * 60 * 1000; // 1 hour

const INITIAL_GREETING: ChatMessage = {
  id: "greeting",
  role: "assistant",
  text: "Hello! I am the SafeZone website assistant. I can answer questions about how SafeZone works, coverage in Karachi, and our volunteer triage protocol.\n\nPlease note: I cannot dispatch rescue teams or open an emergency case. For urgent emergencies, please message SafeZone on WhatsApp directly or call official emergency services.",
  timestamp: Date.now(),
};

export function useChatbot() {
  const whatsapp = useWhatsapp();
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_GREETING]);
  const [messageCount, setMessageCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [attachedImage, setAttachedImage] = useState<AttachedImageData | null>(null);

  // Check rate limit on load
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const { count, timestamp } = JSON.parse(stored);
        if (Date.now() - timestamp > RESET_TIME) {
          setMessageCount(0);
          localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({ count: 0, timestamp: Date.now() })
          );
        } else {
          setMessageCount(typeof count === "number" ? count : 0);
        }
      }
    } catch {
      // Storage fallback
      setMessageCount(0);
    }
  }, []);

  // Update count on successful response
  const updateRateLimit = useCallback(() => {
    setMessageCount((prev) => {
      const newCount = prev + 1;
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            count: newCount,
            timestamp: Date.now(),
          })
        );
      } catch {
        // Ignore localStorage error
      }
      return newCount;
    });
  }, []);

  const attachImage = useCallback((file: File) => {
    if (!file.type.startsWith("image/")) {
      setError("Please attach a valid image file (JPEG, PNG, WEBP).");
      return;
    }
    // Limit to 5MB to avoid oversized payloads
    if (file.size > 5 * 1024 * 1024) {
      setError("Image is too large. Please select an image under 5MB.");
      return;
    }

    setError(null);
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      const previewUrl = URL.createObjectURL(file);
      setAttachedImage({
        base64,
        mimeType: file.type,
        previewUrl,
      });
    };
    reader.onerror = () => {
      setError("Failed to read image file. Please try again.");
    };
    reader.readAsDataURL(file);
  }, []);

  const removeAttachedImage = useCallback(() => {
    if (attachedImage?.previewUrl) {
      URL.revokeObjectURL(attachedImage.previewUrl);
    }
    setAttachedImage(null);
  }, [attachedImage]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() && !attachedImage) return;

      if (messageCount >= MAX_MESSAGES) {
        setError(
          `You have reached the hourly limit of ${MAX_MESSAGES} messages. For emergency help, contact SafeZone on WhatsApp.`
        );
        return;
      }

      setError(null);
      setIsLoading(true);

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        text: text.trim(),
        imageUrl: attachedImage?.previewUrl,
        timestamp: Date.now(),
      };

      const pendingImage = attachedImage;
      removeAttachedImage();

      setMessages((prev) => [...prev, userMsg]);

      try {
        // Exclude the initial greeting from history passed to LLM if needed,
        // or pass user and assistant interactions.
        const historyForApi = messages
          .filter((m) => m.id !== "greeting")
          .map((m) => ({
            ...m,
          }));

        const activeWhatsappUrl = ENV_BOT_WHATSAPP_URL || whatsapp.url || "https://wa.me";

        const replyText = await generateGeminiReply({
          history: historyForApi,
          currentMessage: text,
          image: pendingImage,
          whatsappUrl: activeWhatsappUrl,
        });

        const assistantMsg: ChatMessage = {
          id: `asst-${Date.now()}`,
          role: "assistant",
          text: replyText,
          timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, assistantMsg]);
        updateRateLimit();
      } catch (err: unknown) {
        const errorMsg =
          err instanceof Error
            ? err.message
            : "An unexpected error occurred while communicating with the assistant.";
        setError(errorMsg);

        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            text: `⚠️ ${errorMsg}\n\nIf you need immediate assistance, please message SafeZone on WhatsApp: ${
              ENV_BOT_WHATSAPP_URL || whatsapp.url || "https://wa.me"
            }`,
            timestamp: Date.now(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [
      attachedImage,
      messageCount,
      messages,
      removeAttachedImage,
      updateRateLimit,
      whatsapp.url,
    ]
  );

  const remainingMessages = Math.max(0, MAX_MESSAGES - messageCount);
  const isRateLimited = remainingMessages === 0;

  return {
    messages,
    isLoading,
    error,
    messageCount,
    remainingMessages,
    isRateLimited,
    attachedImage,
    attachImage,
    removeAttachedImage,
    sendMessage,
    clearError: () => setError(null),
  };
}
