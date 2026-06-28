import client from './client';

export interface TagItem {
  id: string;
  name: string;
  color: string;
  kb_id: string;
  created_at: string;
}

export interface TagStat extends TagItem {
  document_count: number;
}

export interface TagCreateRequest {
  name: string;
  color?: string;
}

export async function getTags(kbId: string): Promise<TagItem[]> {
  return client.get(`/kb/${kbId}/tags`);
}

export async function getTagStats(kbId: string): Promise<TagStat[]> {
  return client.get(`/kb/${kbId}/tags/stats`);
}

export async function createTag(kbId: string, data: TagCreateRequest): Promise<TagItem> {
  return client.post(`/kb/${kbId}/tags`, data);
}

export async function deleteTag(kbId: string, tagId: string): Promise<void> {
  return client.delete(`/kb/${kbId}/tags/${tagId}`);
}

export async function assignTags(
  kbId: string,
  tagIds: string[],
  documentIds: string[],
): Promise<void> {
  return client.post(`/kb/${kbId}/tags/assign`, { tag_ids: tagIds, document_ids: documentIds });
}

export async function unassignTags(
  kbId: string,
  tagIds: string[],
  documentIds: string[],
): Promise<void> {
  return client.post(`/kb/${kbId}/tags/unassign`, { tag_ids: tagIds, document_ids: documentIds });
}
