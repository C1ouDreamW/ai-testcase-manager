import { useEffect, useState } from 'react';
import {
  Alert, App, Button, Card, Col, Form, Input, Row, Select, Space, Switch, Tag,
} from 'antd';
import PageHeader from '../components/PageHeader';
import { getSettings, updateSettings } from '../services/api';

const PRESETS = [
  {
    label: 'DeepSeek',
    llm_base_url: 'https://api.deepseek.com/v1',
    llm_model: 'deepseek-chat',
  },
  {
    label: '智谱 GLM',
    llm_base_url: 'https://open.bigmodel.cn/api/paas/v4',
    llm_model: 'glm-4-plus',
  },
  {
    label: '通义千问',
    llm_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    llm_model: 'qwen-plus',
  },
  {
    label: '月之暗面 Kimi',
    llm_base_url: 'https://api.moonshot.cn/v1',
    llm_model: 'kimi-latest',
  },
  {
    label: '豆包（火山方舟）',
    llm_base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    llm_model: 'doubao-1-5-pro-32k-250115',
  },
  {
    label: '腾讯混元',
    llm_base_url: 'https://api.hunyuan.cloud.tencent.com/v1',
    llm_model: 'hunyuan-turbos-latest',
  },
  {
    label: '百度千帆',
    llm_base_url: 'https://qianfan.baidubce.com/v2',
    llm_model: 'ernie-4.0-turbo-8k',
  },
  {
    label: '讯飞星火',
    llm_base_url: 'https://spark-api-open.xf-yun.com/v1',
    llm_model: 'generalv3.5',
  },
  {
    label: 'MiniMax',
    llm_base_url: 'https://api.minimax.chat/v1',
    llm_model: 'MiniMax-Text-01',
  },
  {
    label: '阶跃星辰',
    llm_base_url: 'https://api.stepfun.com/v1',
    llm_model: 'step-2-16k',
  },
  {
    label: '零一万物',
    llm_base_url: 'https://api.lingyiwanwu.com/v1',
    llm_model: 'yi-lightning',
  },
  {
    label: '硅基流动 SiliconFlow',
    llm_base_url: 'https://api.siliconflow.cn/v1',
    llm_model: 'deepseek-ai/DeepSeek-V3',
  },
  {
    label: 'OpenAI',
    llm_base_url: 'https://api.openai.com/v1',
    llm_model: 'gpt-4o-mini',
  },
];

const EMBEDDING_PRESETS = [
  {
    label: '智谱 GLM',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    model: 'embedding-3',
  },
  {
    label: '通义千问',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'text-embedding-v3',
  },
  {
    label: '硅基流动 SiliconFlow',
    base_url: 'https://api.siliconflow.cn/v1',
    model: 'BAAI/bge-m3',
  },
  {
    label: 'OpenAI',
    base_url: 'https://api.openai.com/v1',
    model: 'text-embedding-3-small',
  },
];

export default function Settings() {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState({ use_mock_llm: true, llm_api_key_set: false, llm_api_key_masked: '' });

  const load = async () => {
    setLoading(true);
    try {
      const data = await getSettings();
      setStatus(data);
      form.setFieldsValue({
        llm_base_url: data.llm_base_url,
        llm_model: data.llm_model,
        llm_mock_mode: data.llm_mock_mode,
        llm_api_key: '',
        eval_llm_base_url: data.eval_llm_base_url,
        eval_llm_model: data.eval_llm_model,
        eval_llm_api_key: '',
        embedding_base_url: data.embedding_base_url,
        embedding_model: data.embedding_model,
        embedding_api_key: '',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // 根据当前 API 地址反查匹配的服务商预设，用于下拉框回显
  const llmBaseUrl = Form.useWatch('llm_base_url', form);
  const evalBaseUrl = Form.useWatch('eval_llm_base_url', form);
  const embeddingBaseUrl = Form.useWatch('embedding_base_url', form);
  const matchedPreset = PRESETS.find(p => p.llm_base_url === llmBaseUrl)?.label;
  const matchedEvalPreset = PRESETS.find(p => p.llm_base_url === evalBaseUrl)?.label;
  const matchedEmbeddingPreset = EMBEDDING_PRESETS.find(p => p.base_url === embeddingBaseUrl)?.label;

  const keyPlaceholder = (keySet, keyMasked) => (
    keySet ? `已配置 ${keyMasked}，输入新值可覆盖` : '输入 API Key'
  );

  const applyPreset = (label) => {
    const preset = PRESETS.find(p => p.label === label);
    if (preset) {
      form.setFieldsValue({
        llm_base_url: preset.llm_base_url,
        llm_model: preset.llm_model,
      });
    }
  };

  const applyEvalPreset = (label) => {
    const preset = PRESETS.find(p => p.label === label);
    if (preset) {
      form.setFieldsValue({
        eval_llm_base_url: preset.llm_base_url,
        eval_llm_model: preset.llm_model,
      });
    }
  };

  const applyEmbeddingPreset = (label) => {
    const preset = EMBEDDING_PRESETS.find(p => p.label === label);
    if (preset) {
      form.setFieldsValue({
        embedding_base_url: preset.base_url,
        embedding_model: preset.model,
      });
    }
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const payload = {
        llm_base_url: values.llm_base_url,
        llm_model: values.llm_model,
        llm_mock_mode: values.llm_mock_mode,
        eval_llm_base_url: values.eval_llm_base_url ?? '',
        eval_llm_model: values.eval_llm_model ?? '',
      };
      if (values.llm_api_key?.trim()) {
        payload.llm_api_key = values.llm_api_key.trim();
      }
      if (values.eval_llm_api_key?.trim()) {
        payload.eval_llm_api_key = values.eval_llm_api_key.trim();
      }
      payload.embedding_base_url = values.embedding_base_url ?? '';
      payload.embedding_model = values.embedding_model ?? '';
      if (values.embedding_api_key?.trim()) {
        payload.embedding_api_key = values.embedding_api_key.trim();
      }
      const data = await updateSettings(payload);
      setStatus(data);
      form.setFieldValue('llm_api_key', '');
      message.success('设置已保存');
    } finally {
      setSaving(false);
    }
  };

  const handleClearKey = async () => {
    setSaving(true);
    try {
      const data = await updateSettings({ llm_api_key: '' });
      setStatus(data);
      form.setFieldValue('llm_api_key', '');
      message.success('API Key 已清除');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="设置"
        description="配置用例生成、AI 评测与知识库检索（Embedding）三类模型接口"
      />

      <Alert
        type={status.use_mock_llm ? 'warning' : 'success'}
        showIcon
        style={{ marginBottom: 20 }}
        title={status.use_mock_llm ? '当前为 Mock 模式' : '当前为真实 LLM 模式'}
        description={
          status.use_mock_llm
            ? '未配置 API Key 或已开启 Mock 模式，生成结果为本地示例数据，不消耗 token。'
            : '已连接真实 LLM，AI 生成将调用配置的模型接口。'
        }
      />

      <Card className="surface-card" title="当前状态" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Tag color={status.use_mock_llm ? 'orange' : 'green'}>
            {status.use_mock_llm ? 'Mock 模式' : '真实 LLM'}
          </Tag>
          <Tag color={status.llm_api_key_set ? 'blue' : 'default'}>
            生成模型 Key {status.llm_api_key_set ? '已配置' : '未配置'}
          </Tag>
          <Tag color={status.eval_llm_api_key_set ? 'blue' : 'default'}>
            评测模型 Key {status.eval_llm_api_key_set ? '已配置' : '复用生成模型'}
          </Tag>
          <Tag color={status.embedding_api_key_set ? 'blue' : 'default'}>
            Embedding Key {status.embedding_api_key_set ? '已配置' : '未配置'}
          </Tag>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
      <Card className="surface-card" title="用例生成模型" loading={loading}>
        <Form form={form} layout="vertical">
          <Form.Item label="服务商预设">
            <Select
              placeholder="选择常用服务商，自动填充地址和模型"
              allowClear
              value={matchedPreset}
              onChange={applyPreset}
              options={PRESETS.map(p => ({ label: p.label, value: p.label }))}
            />
          </Form.Item>

          <Form.Item
            name="llm_base_url"
            label="API 地址"
            rules={[{ required: true, message: '请输入 API 地址' }]}
          >
            <Input placeholder="https://api.deepseek.com/v1" />
          </Form.Item>

          <Form.Item
            name="llm_model"
            label="模型名称"
            rules={[{ required: true, message: '请输入模型名称' }]}
          >
            <Input placeholder="deepseek-chat" />
          </Form.Item>

          <Form.Item name="llm_api_key" label="API Key">
            <Input.Password
              placeholder={keyPlaceholder(status.llm_api_key_set, status.llm_api_key_masked)}
              autoComplete="off"
            />
          </Form.Item>

          <Form.Item
            name="llm_mock_mode"
            label="Mock 模式"
            valuePropName="checked"
            extra="开启后即使配置了 Key 也使用本地示例数据"
          >
            <Switch checkedChildren="开" unCheckedChildren="关" />
          </Form.Item>

          <Space>
            <Button type="primary" loading={saving} onClick={handleSave}>
              保存设置
            </Button>
            {status.llm_api_key_set && (
              <Button danger loading={saving} onClick={handleClearKey}>
                清除 API Key
              </Button>
            )}
          </Space>
        </Form>
      </Card>
        </Col>

        <Col xs={24} lg={12}>
      <Card
        className="surface-card"
        title="评测模型（AI Judge / 召回率判定）"
        loading={loading}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          description="评测模型与生成模型分开，可避免“自己给自己打高分”的偏置。全部留空则复用生成模型配置。"
        />
        <Form form={form} layout="vertical">
          <Form.Item label="服务商预设">
            <Select
              placeholder="选择常用服务商，自动填充地址和模型"
              allowClear
              value={matchedEvalPreset}
              onChange={applyEvalPreset}
              options={PRESETS.map(p => ({ label: p.label, value: p.label }))}
            />
          </Form.Item>

          <Form.Item name="eval_llm_base_url" label="API 地址（留空复用生成模型）">
            <Input placeholder="留空则使用生成模型的 API 地址" />
          </Form.Item>

          <Form.Item name="eval_llm_model" label="模型名称（留空复用生成模型）">
            <Input placeholder="如 deepseek-reasoner / gpt-4o" />
          </Form.Item>

          <Form.Item name="eval_llm_api_key" label="API Key（留空复用生成模型）">
            <Input.Password
              placeholder={
                status.eval_llm_api_key_set
                  ? `已配置 ${status.eval_llm_api_key_masked}，输入新值可覆盖`
                  : '输入评测专用 API Key，留空复用生成模型'
              }
              autoComplete="off"
            />
          </Form.Item>

          <Space>
            <Button type="primary" loading={saving} onClick={handleSave}>
              保存设置
            </Button>
            {status.eval_llm_api_key_set && (
              <Button
                danger
                loading={saving}
                onClick={async () => {
                  setSaving(true);
                  try {
                    const data = await updateSettings({ eval_llm_api_key: '' });
                    setStatus(data);
                    form.setFieldValue('eval_llm_api_key', '');
                    message.success('评测 API Key 已清除');
                  } finally {
                    setSaving(false);
                  }
                }}
              >
                清除评测 API Key
              </Button>
            )}
          </Space>
        </Form>
      </Card>
        </Col>

        <Col xs={24} lg={12}>
      <Card
        className="surface-card"
        title="Embedding 模型（知识库检索）"
        loading={loading}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          description="知识库向量化和检索使用的模型，走 /embeddings 接口，与 Chat 模型类型不同，需单独配置。不配置则知识库（RAG）功能不可用。"
        />
        <Form form={form} layout="vertical">
          <Form.Item label="服务商预设">
            <Select
              placeholder="选择常用服务商，自动填充地址和模型"
              allowClear
              value={matchedEmbeddingPreset}
              onChange={applyEmbeddingPreset}
              options={EMBEDDING_PRESETS.map(p => ({ label: p.label, value: p.label }))}
            />
          </Form.Item>

          <Form.Item name="embedding_base_url" label="API 地址">
            <Input placeholder="https://open.bigmodel.cn/api/paas/v4" />
          </Form.Item>

          <Form.Item name="embedding_model" label="模型名称">
            <Input placeholder="如 embedding-3 / BAAI/bge-m3" />
          </Form.Item>

          <Form.Item name="embedding_api_key" label="API Key">
            <Input.Password
              placeholder={keyPlaceholder(status.embedding_api_key_set, status.embedding_api_key_masked)}
              autoComplete="off"
            />
          </Form.Item>

          <Space>
            <Button type="primary" loading={saving} onClick={handleSave}>
              保存设置
            </Button>
            {status.embedding_api_key_set && (
              <Button
                danger
                loading={saving}
                onClick={async () => {
                  setSaving(true);
                  try {
                    const data = await updateSettings({ embedding_api_key: '' });
                    setStatus(data);
                    form.setFieldValue('embedding_api_key', '');
                    message.success('Embedding API Key 已清除');
                  } finally {
                    setSaving(false);
                  }
                }}
              >
                清除 Embedding API Key
              </Button>
            )}
          </Space>
        </Form>
      </Card>
        </Col>
      </Row>
    </div>
  );
}
