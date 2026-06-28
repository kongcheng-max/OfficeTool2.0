import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Input,
  Typography,
  Spin,
  Empty,
  Space,
  Tag,
  Card,
  Descriptions,
  List,
  App,
} from 'antd';
import { SearchOutlined, AimOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { Graph as G6Graph } from '@antv/g6';
import {
  searchEntities,
  getEntityDetail,
  getEntityNetwork,
  type EntityNode,
  type EntityDetail,
  type EntityNetwork,
} from '../../api/graph';
import { useKBStore } from '../../stores/kbStore';

const { Title, Text } = Typography;
const { Search } = Input;

// Entity type → color mapping
const ENTITY_COLORS: Record<string, string> = {
  PERSON: '#FF6B6B',
  ORG: '#4ECDC4',
  DATE: '#FFD93D',
  MONEY: '#6BCB77',
  LOCATION: '#4D96FF',
  TERM: '#9B59B6',
};

const ENTITY_LABELS: Record<string, string> = {
  PERSON: '人物',
  ORG: '组织',
  DATE: '日期',
  MONEY: '金额',
  LOCATION: '地点',
  TERM: '术语',
};

const GraphPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const kbId = id || '';
  const { message } = App.useApp();
  const { list } = useKBStore();
  const currentKB = list.find((kb) => kb.id === kbId);

  const [entities, setEntities] = useState<EntityNode[]>([]);
  const [searchText, setSearchText] = useState('');
  const [loading, setLoading] = useState(false);
  const [networkLoading, setNetworkLoading] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<EntityDetail | null>(null);
  const [network, setNetwork] = useState<EntityNetwork | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<G6Graph | null>(null);

  // ── Load entities ──────────────────────────────────────
  useEffect(() => {
    if (!kbId) return;
    setLoading(true);
    searchEntities(kbId, undefined, 100)
      .then(setEntities)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [kbId]);

  const handleSearch = useCallback(
    async (value: string) => {
      setSearchText(value);
      if (!value.trim()) {
        searchEntities(kbId, undefined, 100)
          .then(setEntities)
          .catch(() => {});
        return;
      }
      setLoading(true);
      try {
        const result = await searchEntities(kbId, value, 100);
        setEntities(result);
      } catch {
        // handled
      }
      setLoading(false);
    },
    [kbId],
  );

  // ── Graph rendering ────────────────────────────────────
  const renderGraph = useCallback((data: EntityNetwork) => {
    if (!containerRef.current) return;

    // Destroy previous
    graphRef.current?.destroy();
    graphRef.current = null;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight || 500;

    const g6 = new G6Graph({
      container: containerRef.current,
      width,
      height,
      autoFit: 'view',
      animation: true,
      layout: {
        type: 'force',
        preventOverlap: true,
        linkDistance: 150,
        nodeStrength: -200,
      },
      behaviors: [
        'drag-canvas',
        'zoom-canvas',
        'drag-element',
        { type: 'hover-activate', degree: 1 },
      ],
      node: {
        style: (datum: Record<string, unknown>) => {
          const type = (datum.type as string) || 'TERM';
          return {
            fill: ENTITY_COLORS[type] || '#9B59B6',
            labelText: datum.label as string,
            labelFill: '#262626',
            labelFontSize: 12,
            labelPlacement: 'bottom',
            labelOffsetY: 6,
          };
        },
        state: {
          active: {
            halo: true,
            haloLineWidth: 3,
          },
        },
      },
      edge: {
        style: {
          stroke: '#d9d9d9',
          endArrow: true,
          labelText: (datum: Record<string, unknown>) => datum.label as string || '',
          labelFontSize: 10,
          labelFill: '#8c8c8c',
        },
        state: {
          active: {
            stroke: '#1677FF',
            labelFill: '#1677FF',
          },
        },
      },
    });

    g6.setData({ nodes: data.nodes, edges: data.edges });
    g6.render();

    // Click node → load entity detail
    g6.on('node:click', (evt: unknown) => {
      const e = evt as { target: { id: string } };
      const nodeId = e.target?.id;
      if (nodeId) handleEntityClick(nodeId);
    });

    graphRef.current = g6;
  }, []);

  // ── Entity click ───────────────────────────────────────
  const handleEntityClick = useCallback(
    async (entityName: string) => {
      setNetworkLoading(true);
      try {
        const [detail, net] = await Promise.all([
          getEntityDetail(kbId, entityName),
          getEntityNetwork(kbId, entityName, 2),
        ]);
        setSelectedEntity(detail);
        setNetwork(net);
        // Re-render graph after a tick (container may resize)
        setTimeout(() => renderGraph(net), 100);
      } catch {
        message.error('获取实体详情失败');
      }
      setNetworkLoading(false);
    },
    [kbId, message, renderGraph],
  );

  // ── Cleanup ────────────────────────────────────────────
  useEffect(() => {
    return () => {
      graphRef.current?.destroy();
    };
  }, []);

  return (
    <div style={{ height: `calc(100vh - 64px - 48px - 48px)`, display: 'flex', gap: 16 }}>
      {/* ── Left: Entity List ── */}
      <div
        style={{
          width: 280,
          flexShrink: 0,
          background: '#fff',
          borderRadius: 8,
          border: '1px solid #f0f0f0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
          <Title level={5} style={{ margin: '0 0 8px 0' }}>
            知识图谱 — {currentKB?.name || `知识库 #${kbId}`}
          </Title>
          <Search
            placeholder="搜索实体…"
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={handleSearch}
          />
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
          {loading ? (
            <Spin style={{ display: 'block', padding: 40 }} />
          ) : entities.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无实体数据"
            />
          ) : (
            <List
              size="small"
              dataSource={entities}
              renderItem={(ent) => (
                <div
                  onClick={() => handleEntityClick(ent.name)}
                  style={{
                    padding: '8px 12px',
                    cursor: 'pointer',
                    borderRadius: 6,
                    marginBottom: 4,
                    border: '1px solid #fafafa',
                    background:
                      selectedEntity?.entity?.name === ent.name
                        ? '#e6f4ff'
                        : 'transparent',
                    transition: 'all 0.2s',
                  }}
                >
                  <Space>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: ENTITY_COLORS[ent.type] || '#999',
                        display: 'inline-block',
                      }}
                    />
                    <Text strong style={{ fontSize: 13 }}>
                      {ent.name}
                    </Text>
                    <Tag
                      color={ENTITY_COLORS[ent.type] || 'default'}
                      style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}
                    >
                      {ENTITY_LABELS[ent.type] || ent.type}
                    </Tag>
                  </Space>
                </div>
              )}
            />
          )}
        </div>

        {/* Legend */}
        <div style={{ padding: '8px 16px', borderTop: '1px solid #f0f0f0' }}>
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
            图例：
          </Text>
          <Space wrap size={[4, 4]}>
            {Object.entries(ENTITY_LABELS).map(([type, label]) => (
              <Tag
                key={type}
                color={ENTITY_COLORS[type]}
                style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}
              >
                {label}
              </Tag>
            ))}
          </Space>
        </div>
      </div>

      {/* ── Center: Graph Canvas ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div
          ref={containerRef}
          style={{
            flex: 1,
            background: '#fff',
            borderRadius: 8,
            border: '1px solid #f0f0f0',
            overflow: 'hidden',
            minHeight: 400,
          }}
        >
          {!network && !networkLoading && (
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                textAlign: 'center',
                pointerEvents: 'none',
              }}
            >
              <AimOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 12 }} />
              <br />
              <Text type="secondary">点击左侧实体查看关系网络</Text>
            </div>
          )}
          {networkLoading && (
            <Spin
              size="large"
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
              }}
            />
          )}
        </div>
      </div>

      {/* ── Right: Entity Detail Panel ── */}
      {selectedEntity && (
        <div
          style={{
            width: 320,
            flexShrink: 0,
            background: '#fff',
            borderRadius: 8,
            border: '1px solid #f0f0f0',
            overflowY: 'auto',
            padding: 16,
          }}
        >
          <Title level={5} style={{ marginBottom: 12 }}>
            {selectedEntity.entity.name}
          </Title>

          <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="类型">
              <Tag color={ENTITY_COLORS[selectedEntity.entity.type] || 'default'}>
                {ENTITY_LABELS[selectedEntity.entity.type] || selectedEntity.entity.type}
              </Tag>
            </Descriptions.Item>
            {selectedEntity.entity.properties &&
              Object.entries(selectedEntity.entity.properties).map(([k, v]) => (
                <Descriptions.Item key={k} label={k}>
                  {String(v)}
                </Descriptions.Item>
              ))}
          </Descriptions>

          {/* Relations */}
          <Title level={5} style={{ fontSize: 14, marginBottom: 8 }}>
            关联关系 ({selectedEntity.relations?.length || 0})
          </Title>
          {selectedEntity.relations?.length > 0 ? (
            <List
              size="small"
              dataSource={selectedEntity.relations}
              style={{ marginBottom: 16 }}
              renderItem={(rel) => (
                <List.Item>
                  <Space>
                    <Text>{rel.type}</Text>
                    <Tag>{rel.target}</Tag>
                  </Space>
                </List.Item>
              )}
            />
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无关联"
              style={{ marginBottom: 16 }}
            />
          )}

          {/* Source Docs */}
          <Title level={5} style={{ fontSize: 14, marginBottom: 8 }}>
            来源文档 ({selectedEntity.source_docs?.length || 0})
          </Title>
          {selectedEntity.source_docs?.length > 0 ? (
            <List
              size="small"
              dataSource={selectedEntity.source_docs}
              renderItem={(doc) => (
                <List.Item>
                  <Space>
                    <Text>{doc.doc_name}</Text>
                    {doc.page && (
                      <Tag color="blue" style={{ fontSize: 10 }}>
                        P{doc.page}
                      </Tag>
                    )}
                  </Space>
                </List.Item>
              )}
            />
          ) : (
            <Text type="secondary">—</Text>
          )}
        </div>
      )}
    </div>
  );
};

export default GraphPage;
