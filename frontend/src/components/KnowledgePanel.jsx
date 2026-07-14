import { InboxOutlined, SearchOutlined } from '@ant-design/icons';
import {
  Alert, App, Button, Card, Drawer, Empty, Input, List, Popconfirm, Space, Table, Tag, Upload,
} from 'antd';
import { useCallback, useEffect, useState } from 'react';
import {
  deleteKnowledgeDoc,
  getKnowledgeChunks,
  getKnowledgeDocs,
  searchKnowledge,
  uploadKnowledgeDoc,
} from '../services/api';

const SOURCE_LABEL = { doc: '业务文档', case: '历史用例', defect: '缺陷记录' };
const STATUS_META = {
  ready: { color: 'green', label: '已入库' },
  processing: { color: 'blue', label: '处理中' },
  failed: { color: 'red', label: '失败' },
};

export default function KnowledgePanel({ projectId, projectName }) {
  const { message } = App.useApp();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  const [chunkDrawer, setChunkDrawer] = useState({ open: false, doc: null, chunks: [], loading: false });

  const [searchQuery, setSearchQuery] = useState('');
  const [searchHits, setSearchHits] = useState(null);
  const [searching, setSearching] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDocs(await getKnowledgeDocs(projectId));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const handleUpload = async (file) => {
    setUploading(true);
    try {
      await uploadKnowledgeDoc(projectId, file);
      message.success(`「${file.name}」已入库`);
      load();
    } catch (err) {
      message.error(err.response?.data?.detail || '入库失败，请检查 Embedding 模型配置');
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleDelete = async (doc) => {
    await deleteKnowledgeDoc(projectId, doc.id);
    message.success('已删除');
    load();
  };

  const openChunks = async (doc) => {
    setChunkDrawer({ open: true, doc, chunks: [], loading: true });
    try {
      const chunks = await getKnowledgeChunks(projectId, doc.id);
      setChunkDrawer((prev) => ({ ...prev, chunks, loading: false }));
    } catch {
      setChunkDrawer((prev) => ({ ...prev, loading: false }));
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      setSearchHits(await searchKnowledge(projectId, searchQuery.trim()));
    } catch (err) {
      message.error(err.response?.data?.detail || '检索失败');
    } finally {
      setSearching(false);
    }
  };

  const columns = [
    { title: '标题', dataIndex: 'title', ellipsis: true },
    {
      title: '类型',
      dataIndex: 'source_type',
      width: 100,
      render: (v) => <Tag>{SOURCE_LABEL[v] || v}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (v, record) => {
        const meta = STATUS_META[v] || { color: 'default', label: v };
        return (
          <Tag color={meta.color} title={record.error_message || ''}>{meta.label}</Tag>
        );
      },
    },
    { title: '分块数', dataIndex: 'chunk_count', width: 80 },
    {
      title: '入库时间',
      dataIndex: 'created_at',
      width: 170,
      render: (v) => (v ? new Date(v).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button size="small" type="link" onClick={() => openChunks(record)}>查看分块</Button>
          <Popconfirm title="删除该知识文档及其向量？" onConfirm={() => handleDelete(record)}>
            <Button size="small" type="link" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message={projectName ? <>正在管理「<strong>{projectName}</strong>」的知识库</> : undefined}
        description="上传业务规则、接口文档、缺陷记录等资料构建项目知识库。开启「知识库检索」后，AI 生成用例前会检索相关知识注入提示词，补充 PRD 缺失的业务背景并减少幻觉。"
      />

      <Card className="surface-card" title="上传知识文档" style={{ marginBottom: 16 }}>
        <Upload.Dragger
          className="requirement-upload"
          accept=".md,.txt,.docx"
          showUploadList={false}
          disabled={uploading}
          beforeUpload={handleUpload}
        >
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">{uploading ? '正在向量化入库...' : '点击或拖拽文件上传'}</p>
          <p className="ant-upload-hint">支持 Markdown / Word / 文本，按标题层级自动分块并向量化</p>
        </Upload.Dragger>
      </Card>

      <Card
        className="surface-card"
        title="知识文档"
        style={{ marginBottom: 16 }}
        extra={(
          <Space.Compact style={{ width: 320 }}>
            <Input
              placeholder="输入问题测试检索效果"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
            <Button icon={<SearchOutlined />} loading={searching} onClick={handleSearch}>检索</Button>
          </Space.Compact>
        )}
      >
        {searchHits !== null && (
          <div style={{ marginBottom: 16 }}>
            {searchHits.length === 0 ? (
              <Alert type="warning" showIcon description="没有命中相关知识（相似度均低于阈值）" />
            ) : (
              <List
                size="small"
                bordered
                dataSource={searchHits}
                renderItem={(hit) => (
                  <List.Item>
                    <div style={{ width: '100%' }}>
                      <Space style={{ marginBottom: 4 }}>
                        <Tag color="blue">相似度 {(hit.score * 100).toFixed(0)}%</Tag>
                        <span style={{ fontWeight: 600 }}>
                          《{hit.title}》{hit.heading ? ` · ${hit.heading}` : ''}
                        </span>
                      </Space>
                      <div style={{ color: 'var(--muted)', fontSize: 13 }}>{hit.content}</div>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </div>
        )}

        <Table
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={docs}
          locale={{ emptyText: <Empty description="暂无知识文档，上传后 AI 生成可引用" /> }}
          pagination={false}
        />
      </Card>

      <Drawer
        title={chunkDrawer.doc ? `分块预览：${chunkDrawer.doc.title}` : '分块预览'}
        open={chunkDrawer.open}
        width={560}
        onClose={() => setChunkDrawer({ open: false, doc: null, chunks: [], loading: false })}
      >
        <List
          size="small"
          loading={chunkDrawer.loading}
          dataSource={chunkDrawer.chunks}
          renderItem={(chunk, idx) => (
            <List.Item>
              <div style={{ width: '100%' }}>
                <div style={{ marginBottom: 4, fontWeight: 600, fontSize: 13 }}>
                  #{idx + 1}
                  {chunk.heading && <Tag style={{ marginLeft: 8 }}>{chunk.heading}</Tag>}
                </div>
                <div style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{chunk.content}</div>
              </div>
            </List.Item>
          )}
        />
      </Drawer>
    </div>
  );
}
