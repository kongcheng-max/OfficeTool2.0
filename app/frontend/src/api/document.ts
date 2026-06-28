import client from './client';
import type { TagItem } from './tag';

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
  tags?: TagItem[];
  chunk_count: number;
  error_message?: string;
  created_at: string;
}

export interface DocumentDetail extends DocumentItem {
  tags: TagItem[];
}

export interface DocumentVersion {
  id: string;
  document_id: string;
  version: number;
  file_size: number;
  file_md5: string;
  chunk_count: number;
  change_note: string;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages?: number;
}

export interface BatchItemResult {
  filename: string;
  document_id: string;
  status: string;   // "success" | "failed"
  message: string;
}

export interface BatchUploadResponse {
  success_count: number;
  failed_count: number;
  skipped_count: number;
  results: BatchItemResult[];
}

// ── Single ──

export async function getDocumentList(
  kbId: string,
  params?: { page?: number; page_size?: number; status?: DocStatus },
): Promise<DocumentListResponse> {
  return client.get(`/kb/${kbId}/documents`, { params });
}

export async function getDocumentDetail(
  kbId: string,
  docId: string,
): Promise<DocumentDetail> {
  return client.get(`/kb/${kbId}/documents/${docId}`);
}

export async function getDocumentVersions(
  kbId: string,
  docId: string,
): Promise<DocumentVersion[]> {
  return client.get(`/kb/${kbId}/documents/${docId}/versions`);
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

// ── Batch ──

export async function batchUploadDocuments(
  kbId: string,
  files: File[],
): Promise<BatchUploadResponse> {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  return client.post(`/kb/${kbId}/documents/batch`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  });
}

export async function replaceDocument(
  kbId: string,
  docId: string,
  file: File,
  changeNote?: string,
): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append('file', file);
  return client.post(`/kb/${kbId}/documents/${docId}/replace`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { change_note: changeNote || '' },
  });
}

export async function importZip(
  kbId: string,
  file: File,
): Promise<BatchUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  return client.post(`/kb/${kbId}/documents/import-zip`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  });
}
