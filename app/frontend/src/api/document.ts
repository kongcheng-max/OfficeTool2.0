import client from './client';

export type DocStatus = 'uploaded' | 'processing' | 'ready' | 'error';

export interface DocumentItem {
  id: string;        // uuid hex from BE
  kb_id?: string;
  filename: string;
  original_filename: string;  // user-facing name
  file_size: number;
  mime_type: string;          // matches BE DocumentResponse.mime_type
  file_type?: string;         // alias for backward compat
  status: DocStatus;
  chunk_count: number;
  error_message?: string;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages?: number;
}

export async function getDocumentList(
  kbId: string,
  params?: { page?: number; page_size?: number; status?: DocStatus },
): Promise<DocumentListResponse> {
  return client.get(`/kb/${kbId}/documents`, { params });
}

export async function uploadDocument(
  kbId: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append('file', file);
  return client.post(`/kb/${kbId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (event.total && onProgress) {
        onProgress(Math.round((event.loaded * 100) / event.total));
      }
    },
  });
}

export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  return client.delete(`/kb/${kbId}/documents/${docId}`);
}
