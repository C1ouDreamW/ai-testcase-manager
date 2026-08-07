import {
  DeleteOutlined, EyeOutlined, LinkOutlined, LoadingOutlined, PictureOutlined, ReloadOutlined,
} from '@ant-design/icons';
import {
  App, Button, Card, Checkbox, Empty, Image, Input, Popconfirm, Space, Table, Tag, Typography, Upload,
} from 'antd';
import { useEffect, useMemo, useState } from 'react';
import {
  addFigmaDesign, deleteDesignAsset, getDesignContent, getDesigns, mergeDesignInsights,
  parseDesignAsset, updateDesignInsight, uploadDesignAsset,
} from '../../services/api';
import FlowActionBar from './FlowActionBar';

const { Dragger } = Upload;
const { Text } = Typography;

const STATUS_META = {
  uploaded: { color: 'default', text: '待解析' },
  parsing: { color: 'processing', text: '解析中' },
  parsed: { color: 'success', text: '已解析' },
  failed: { color: 'error', text: '解析失败' },
  not_design: { color: 'warning', text: '非设计稿' },
  linked: { color: 'blue', text: '已关联' },
};

function DesignThumbnail({ projectId, asset }) {
  const [src, setSrc] = useState('');

  useEffect(() => {
    let active = true;
    let objectUrl = '';
    if (asset.asset_type === 'image') {
      getDesignContent(projectId, asset.id).then((response) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(response.data);
        setSrc(objectUrl);
      }).catch(() => {});
    }
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId, asset.id, asset.asset_type]);

  if (asset.asset_type === 'figma') {
    return (
      <a href={asset.figma_url} target="_blank" rel="noreferrer">
        <LinkOutlined /> 打开 Figma
      </a>
    );
  }
  return src ? (
    <Image
      src={src}
      width={112}
      height={72}
      style={{ objectFit: 'cover', borderRadius: 8 }}
      preview={{ mask: <><EyeOutlined /> 预览</> }}
    />
  ) : <div style={{ width: 112, height: 72, display: 'grid', placeItems: 'center' }}><LoadingOutlined /></div>;
}

export default function StepDesignImport({ projectId, document, onBack, onContinue }) {
  const { message } = App.useApp();
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [merging, setMerging] = useState(false);
  const [figmaUrl, setFigmaUrl] = useState('');
  const [figmaTitle, setFigmaTitle] = useState('');

  const loadAssets = async () => {
    setLoading(true);
    try {
      setAssets(await getDesigns(projectId, document.id));
    } catch (err) {
      message.error(err.response?.data?.detail || '加载设计稿失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAssets(); }, [projectId, document.id]);

  const insights = useMemo(
    () => assets.flatMap(asset => (asset.insights || []).map(item => ({
      ...item,
      assetTitle: asset.title,
    }))),
    [assets],
  );
  const selectedIds = insights.filter(item => item.selected && !item.merged).map(item => item.id);

  const replaceAsset = (updated) => {
    setAssets(prev => prev.map(item => (item.id === updated.id ? updated : item)));
  };

  const uploadImage = async (file) => {
    setUploading(true);
    try {
      const asset = await uploadDesignAsset(projectId, document.id, file);
      setAssets(prev => [...prev, asset]);
      try {
        replaceAsset(await parseDesignAsset(projectId, asset.id));
        message.success(`${file.name} 解析完成`);
      } catch (err) {
        await loadAssets();
        message.error(err.response?.data?.detail || `${file.name} 解析失败`);
      }
    } catch (err) {
      message.error(err.response?.data?.detail || '设计稿上传失败');
    } finally {
      setUploading(false);
    }
    return false;
  };

  const addFigma = async () => {
    if (!figmaUrl.trim()) return message.warning('请输入 Figma 链接');
    try {
      const asset = await addFigmaDesign(projectId, {
        document_id: document.id,
        url: figmaUrl.trim(),
        title: figmaTitle.trim(),
      });
      setAssets(prev => [...prev, asset]);
      setFigmaUrl('');
      setFigmaTitle('');
      message.success('Figma 链接已关联');
    } catch (err) {
      message.error(err.response?.data?.detail || 'Figma 链接添加失败');
    }
  };

  const retryParse = async (asset) => {
    replaceAsset({ ...asset, status: 'parsing', error_message: '' });
    try {
      replaceAsset(await parseDesignAsset(projectId, asset.id));
    } catch (err) {
      await loadAssets();
      message.error(err.response?.data?.detail || '解析失败');
    }
  };

  const removeAsset = async (assetId) => {
    try {
      await deleteDesignAsset(projectId, assetId);
      setAssets(prev => prev.filter(item => item.id !== assetId));
      message.success('设计稿已删除');
    } catch (err) {
      message.error(err.response?.data?.detail || '删除失败');
    }
  };

  const patchInsight = async (insight, changes) => {
    try {
      const updated = await updateDesignInsight(projectId, insight.id, changes);
      setAssets(prev => prev.map(asset => ({
        ...asset,
        insights: (asset.insights || []).map(item => (item.id === updated.id ? updated : item)),
      })));
    } catch (err) {
      message.error(err.response?.data?.detail || '更新设计功能点失败');
    }
  };

  const continueFlow = async () => {
    if (!selectedIds.length) {
      onContinue(document);
      return;
    }
    setMerging(true);
    try {
      const updatedDocument = await mergeDesignInsights(projectId, document.id, selectedIds);
      message.success(`已合并 ${selectedIds.length} 个设计功能点`);
      onContinue(updatedDocument);
    } catch (err) {
      message.error(err.response?.data?.detail || '合并设计功能点失败');
    } finally {
      setMerging(false);
    }
  };

  const columns = [
    {
      title: '采用',
      width: 60,
      render: (_, item) => (
        <Checkbox
          checked={item.selected}
          disabled={item.merged}
          onChange={event => patchInsight(item, { selected: event.target.checked })}
        />
      ),
    },
    { title: '来源', dataIndex: 'assetTitle', width: 120, ellipsis: true },
    {
      title: '页面 / 模块',
      width: 150,
      render: (_, item) => [item.page, item.module].filter(Boolean).join(' · ') || '—',
    },
    {
      title: '设计功能点',
      dataIndex: 'feature',
      width: 180,
      render: (value, item) => (
        <Input
          defaultValue={value}
          disabled={item.merged}
          onBlur={event => {
            const next = event.target.value.trim();
            if (next && next !== value) patchInsight(item, { feature: next });
          }}
        />
      ),
    },
    {
      title: '可测试说明',
      dataIndex: 'description',
      render: (value, item) => (
        <Input
          defaultValue={value}
          disabled={item.merged}
          onBlur={event => {
            if (event.target.value !== value) patchInsight(item, { description: event.target.value });
          }}
        />
      ),
    },
  ];

  return (
    <>
      <Card
        className="surface-card"
        title="导入设计稿"
        extra={<Text type="secondary">可跳过；图片会由视觉模型解析</Text>}
      >
        <Dragger
          accept=".png,.jpg,.jpeg,.webp"
          multiple
          showUploadList={false}
          beforeUpload={uploadImage}
          disabled={uploading}
          style={{ marginBottom: 16 }}
        >
          <p className="ant-upload-drag-icon"><PictureOutlined /></p>
          <p className="ant-upload-text">点击或拖拽 PNG、JPG、WebP 设计稿到此处</p>
          <p className="ant-upload-hint">最多 8 张，单张不超过 10MB；上传后自动提取页面功能和交互</p>
        </Dragger>

        <Card size="small" title="关联 Figma 链接" style={{ marginBottom: 16 }}>
          <Space.Compact block>
            <Input
              value={figmaTitle}
              onChange={event => setFigmaTitle(event.target.value)}
              placeholder="标题（可选）"
              style={{ width: 180 }}
            />
            <Input
              value={figmaUrl}
              onChange={event => setFigmaUrl(event.target.value)}
              placeholder="https://www.figma.com/design/..."
            />
            <Button icon={<LinkOutlined />} onClick={addFigma}>关联</Button>
          </Space.Compact>
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            首版仅保存并展示链接；如需 AI 解析，请同时上传对应页面截图。
          </Text>
        </Card>

        <Card size="small" title={`设计稿（${assets.length}）`} loading={loading} style={{ marginBottom: 16 }}>
          {assets.length ? (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {assets.map(asset => {
                const status = STATUS_META[asset.status] || STATUS_META.uploaded;
                const hasMergedInsight = (asset.insights || []).some(item => item.merged);
                return (
                  <div key={asset.id} style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                    <DesignThumbnail projectId={projectId} asset={asset} />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <Space wrap>
                        <Text strong>{asset.title}</Text>
                        <Tag color={status.color}>{status.text}</Tag>
                        {asset.status === 'parsed' && asset.parse_source === 'mock' && (
                          <Tag color="orange">Mock 示例</Tag>
                        )}
                        {asset.status === 'parsed' && asset.parse_source?.startsWith('vision:') && (
                          <Tag color="cyan">{asset.parse_source.slice('vision:'.length) || '视觉模型'}</Tag>
                        )}
                      </Space>
                      {asset.error_message && (
                        <Text type="danger" ellipsis={{ tooltip: asset.error_message }} style={{ display: 'block' }}>
                          {asset.error_message}
                        </Text>
                      )}
                      {asset.status === 'parsed' && asset.parse_source === 'mock' && (
                        <Text type="warning" style={{ display: 'block' }}>
                          未调用视觉模型，为示例数据。配置视觉模型后请重新解析。
                        </Text>
                      )}
                      {asset.status === 'not_design' && (
                        <Text type="warning" style={{ display: 'block' }}>
                          这张图不像产品设计稿{asset.image_summary ? `：${asset.image_summary}` : ''}。
                          已跳过，未生成功能点。请上传真实页面截图或原型图。
                        </Text>
                      )}
                    </div>
                    {asset.asset_type === 'image' && ['failed', 'uploaded', 'parsed', 'not_design'].includes(asset.status) && (
                      <Button icon={<ReloadOutlined />} onClick={() => retryParse(asset)}>重新解析</Button>
                    )}
                    <Popconfirm
                      title="删除这份设计稿及其解析结果？"
                      disabled={hasMergedInsight}
                      onConfirm={() => removeAsset(asset.id)}
                    >
                      <Button
                        danger
                        type="text"
                        disabled={hasMergedInsight}
                        title={hasMergedInsight ? '设计功能点已合并，需保留来源设计稿' : '删除设计稿'}
                        icon={<DeleteOutlined />}
                      />
                    </Popconfirm>
                  </div>
                );
              })}
            </Space>
          ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未导入设计稿" />}
        </Card>

        <Card size="small" title={`设计功能点（${insights.length}）`}>
          <Table
            rowKey="id"
            dataSource={insights}
            columns={columns}
            pagination={false}
            size="small"
            locale={{ emptyText: '上传图片并解析后，将在这里展示可确认的设计功能点' }}
          />
        </Card>
      </Card>

      <FlowActionBar
        meta={<span>已选择 <strong>{selectedIds.length}</strong> 个待合并设计功能点</span>}
      >
        <Button onClick={onBack}>上一步</Button>
        <Button onClick={() => onContinue(document)}>跳过设计稿</Button>
        <Button type="primary" loading={merging} onClick={continueFlow}>
          {selectedIds.length ? '确认并合并' : '继续'}
        </Button>
      </FlowActionBar>
    </>
  );
}
