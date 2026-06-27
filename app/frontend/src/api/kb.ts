import client from './client';

export interface KnowledgeBaseItem {
  id: string;  // uuid hex from BE
  name: string;
  description?: string;
  doc_count: number;      // matches BE KBResponse.doc_count
  document_count?: number;  // alias for backward compat
  qa_count?: number;
  chunk_count?: number;
  created_at: string;
  updated_at?: string;
}

export interface CreateKBRequest {
  name: string;
  description?: string;
}

export async function getKBList(): Promise<KnowledgeBaseItem[]> {
  return client.get('/knowledge-bases');
}

export async function getKBDetail(id: string): Promise<KnowledgeBaseItem> {
  return client.get(`/knowledge-bases/${id}`);
}

export async function createKB(data: CreateKBRequest): Promise<KnowledgeBaseItem> {
  return client.post('/knowledge-bases', data);
}

export async function deleteKB(id: string): Promise<void> {
  return client.delete(`/knowledge-bases/${id}`);
}
