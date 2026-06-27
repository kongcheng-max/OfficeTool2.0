import client from './client';

export interface SourceInfo {
  document_id: string;
  document_name: string;
  chunk_text: string;
  page: number | null;
  score: number;
}

export interface QAResponse {
  answer: string;
  conversation_id: string;
  sources: SourceInfo[];
  confidence: number;
}

export interface QARequest {
  question: string;
}

export async function askQuestion(kbId: string, question: string): Promise<QAResponse> {
  return client.post(`/kb/${kbId}/qa`, { question });
}

/**
 * SSE streaming Q&A.
 * Returns an AbortController so the caller can cancel.
 */
export function askQuestionStream(
  kbId: string,
  question: string,
  onChunk: (text: string) => void,
  onDone: (sources: SourceInfo[], confidence: number, conversationId: string) => void,
  onError: (error: Error) => void,
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem('token');

  fetch(`/api/v1/kb/${kbId}/qa/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
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
