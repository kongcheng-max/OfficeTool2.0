import client from './client';

export interface EntityNode {
  name: string;
  type: string;         // PERSON / ORG / DATE / MONEY / LOCATION / TERM
  kb_id?: string;
  doc_count?: number;
  properties?: Record<string, unknown>;
}

export interface EntityRelation {
  source: string;
  target: string;
  type: string;         // e.g. "任职于", "签署", "涉及金额", "位于"
  doc_ids?: string[];
}

export interface EntityDetail {
  entity: EntityNode;
  relations: EntityRelation[];
  source_docs: Array<{ doc_id: string; doc_name: string; page?: number }>;
}

export interface EntityNetwork {
  nodes: Array<{ id: string; label: string; type: string }>;
  edges: Array<{ source: string; target: string; label: string }>;
}

export async function searchEntities(
  kbId: string,
  q?: string,
  limit?: number,
): Promise<EntityNode[]> {
  return client.get(`/kb/${kbId}/graph/entities`, { params: { q, limit } });
}

export async function getEntityDetail(
  kbId: string,
  entityName: string,
): Promise<EntityDetail> {
  return client.get(`/kb/${kbId}/graph/entity/${encodeURIComponent(entityName)}`);
}

export async function getEntityNetwork(
  kbId: string,
  entityName: string,
  depth?: number,
): Promise<EntityNetwork> {
  return client.get(
    `/kb/${kbId}/graph/entity/${encodeURIComponent(entityName)}/network`,
    { params: { depth } },
  );
}
