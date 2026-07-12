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
import { useTheme } from '../../theme/ThemeProvider';
import { entityColors } from '../../theme/tokens';
import { Stagger, StaggerItem } from '../../components/motion/FadeIn';

const { Title, Text } = Typography;
const { Search } = Input;

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
  const { mode } = useTheme();
  const currentKB = list.find((kb) => kb.id === kbId);

  // 校准后的实体色（随主题变化，G6 需真实 hex）
  const ENTITY_COLORS = entityColors[mode];

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

    // 主题相关色（G6 需真实值，不能用 CSS 变量）
    const labelFill = mode === 'dark' ? 'rgba(255,255,255,0.85)' : '#1F2329';
    const edgeStroke = mode === 'dark' ? '#3A3D42' : '#DEE0E3';
    const edgeLabel = mode === 'dark' ? 'rgba(255,255,255,0.45)' : '#8F959E';
    const brand = mode === 'dark' ? '#4E83FD' : '#3370FF';

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
            fill: ENTITY_COLORS[type] || ENTITY_COLORS.TERM,
            labelText: datum.label as string,
            labelFill,
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
          stroke: edgeStroke,
          endArrow: true,
          labelText: (datum: Record<string, unknown>) => datum.label as string || '',
          labelFontSize: 10,
          labelFill: edgeLabel,
        },
        state: {
          active: {
            stroke: brand,
            labelFill: brand,
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

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

  // ── BUG-053: 窗口缩放时自动调整图谱画布 ──
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => {
      if (graphRef.current && container) {
        const w = container.clientWidth;
        const h = container.clientHeight || 500;
        graphRef.current.setSize(w, h);
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // ── Cleanup ────────────────────────────────────────────
  useEffect(() => {
    return () => {
      graphRef.current?.destroy();
    };
  }, []);

  return (
    <div style={{ height: '100%', display: 'flex', gap: 16, padding: 16, minHeight: 0 }}>
      {/* ── Left: Entity List ── */}
      <div
        style={{
          width: 280,
          flexShrink: 0,
          background: 'var(--paper)',
          borderRadius: 14,
          border: '1px solid var(--line)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--divider)' }}>
          <div style={{ fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 15, margin: '0 0 10px 0' }}>
            知识图谱
          </div>
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
            <Stagger>
              {entities.map((ent) => (
                <StaggerItem key={ent.name}>
                <div
                  onClick={() => handleEntityClick(ent.name)}
                  style={{
                    padding: '8px 12px',
                    cursor: 'pointer',
                    borderRadius: 9,
                    marginBottom: 3,
                    background:
                      selectedEntity?.entity?.name === ent.name
                        ? 'var(--active)'
                        : 'transparent',
                    transition: 'background 0.14s',
                  }}
                >
                  <Space>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: ENTITY_COLORS[ent.type] || 'var(--ink-3)',
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
                </StaggerItem>
              ))}
            </Stagger>
          )}
        </div>

        {/* Legend */}
        <div style={{ padding: '10px 16px', borderTop: '1px solid var(--divider)' }}>
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 6 }}>
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
            position: 'relative',
            flex: 1,
            background: 'var(--paper)',
            borderRadius: 14,
            border: '1px solid var(--line)',
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
              <AimOutlined style={{ fontSize: 48, color: 'var(--ink-3)', marginBottom: 12 }} />
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
            background: 'var(--paper)',
            borderRadius: 14,
            border: '1px solid var(--line)',
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
