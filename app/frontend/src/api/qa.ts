import client from './client';

export interface SourceInfo {
  document_id: string;
  document_name: string;
  chunk_text: string;
  page: number | null;
  section?: string | null;
  score: number;
  sources?: string[];       // e.g. ["vector","bm25","kg"]
  chunk_index?: number | null;
}

export interface QAResponse {
  answer: string;
  conversation_id: string;
  sources: SourceInfo[];
  confidence: number;
}

export interface ChatResponse extends QAResponse {
  context_rounds: number;   // multi-turn rounds so far
}

export interface QARequest {
  question: string;
}

export async function askQuestion(kbId: string, question: string): Promise<QAResponse> {
  return client.post(`/kb/${kbId}/qa`, { question });
}

// ── SSE helpers ────────────────────────────────────────────

function _sseFetch(
  endpoint: string,
  body: Record<string, unknown>,
  onChunk: (text: string) => void,
  onDone: (sources: SourceInfo[], confidence: number, conversationId: string) => void,
  onError: (error: Error) => void,
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem('token');

  fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      let streamEnded = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          streamEnded = true;
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (!data) continue;

            try {
              const parsed = JSON.parse(data);
              if (parsed.type === 'chunk') {
                onChunk(parsed.text);
              } else if (parsed.type === 'done') {
                onDone(
                  parsed.sources || [],
                  parsed.confidence || 0,
                  parsed.conversation_id || '',
                );
                return; // done event received, stop reading
              }
            } catch {
              // If not JSON, treat as plain text chunk (backward compat)
              onChunk(data);
            }
          }
        }
      }

      // Stream ended without a done event — call onDone with empty data
      // so the UI can reset loading state
      if (streamEnded) {
        onDone([], 0, '');
      }
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        onError(error);
      }
    });

  return controller;
}

// ── Public API ──────────────────────────────────────────────

/**
 * Single-turn streaming Q&A.
 * Uses /qa/stream endpoint (no multi-turn context).
 */
export function askQuestionStream(
  kbId: string,
  question: string,
  onChunk: (text: string) => void,
  onDone: (sources: SourceInfo[], confidence: number, conversationId: string) => void,
  onError: (error: Error) => void,
): AbortController {
  return _sseFetch(
    `/api/v1/kb/${kbId}/qa/stream`,
    { question },
    onChunk,
    onDone,
    onError,
  );
}

/**
 * Multi-turn streaming Q&A.
 * Uses /chat/stream endpoint. Pass conversation_id to continue a conversation.
 */
export function chatStream(
  kbId: string,
  question: string,
  conversationId: string | undefined,
  onChunk: (text: string) => void,
  onDone: (sources: SourceInfo[], confidence: number, conversationId: string) => void,
  onError: (error: Error) => void,
): AbortController {
  return _sseFetch(
    `/api/v1/kb/${kbId}/chat/stream`,
    { question, conversation_id: conversationId ?? null },
    onChunk,
    onDone,
    onError,
  );
}
