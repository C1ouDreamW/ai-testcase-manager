import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  App, Button, Drawer, Dropdown, Space, Spin, Table, Tag, Tooltip, Typography,
} from 'antd';
import {
  QUALITY_COLOR, QUALITY_LABEL, REVIEW_COLOR, REVIEW_LABEL, SKILL_LABEL, STATUS_LABEL, STRATEGY_LABEL, TYPE_LABEL,
} from '../pages/generate/constants';
import { CaseDetail, judgeScoreCell, priorityTag } from '../pages/generate/DetailPanels';
import { exportGenerationDrafts, getGeneration, getGenerationSummaries } from '../services/api';

const { Text } = Typography;

function adoptionCell(stats) {
  if (!stats?.total) return <span style={{ color: '#94a3b8' }}>—</span>;
  if (!stats.reviewed) return <Tag>待评审</Tag>;
  const color = stats.adoption_rate >= 70 ? '#16a34a' : stats.adoption_rate >= 40 ? '#ea580c' : '#dc2626';
  return (
    <Tooltip title={`共 ${stats.total} 条：采纳 ${stats.adopted}（其中编辑后采纳 ${stats.edited_adopted}）、驳回 ${stats.rejected}、未处理 ${stats.pending}`}>
      <span style={{ color, fontWeight: 600 }}>{stats.adoption_rate}%</span>
      <span style={{ color: '#94a3b8', marginLeft: 4 }}>({stats.adopted}/{stats.total})</span>
    </Tooltip>
  );
}

const draftColumns = [
  { title: '用例标题', dataIndex: 'title', ellipsis: true },
  {
    title: '用例集',
    dataIndex: 'is_smoke',
    width: 80,
    render: v => (v ? <Tag color="green">冒烟</Tag> : <Tag>完整</Tag>),
  },
  { title: '类型', dataIndex: 'case_type', width: 80, render: v => <Tag>{TYPE_LABEL[v] || v}</Tag> },
  { title: '优先级', dataIndex: 'priority', width: 80, render: priorityTag },
  { title: '质量', dataIndex: 'quality_status', width: 90, render: v => <Tag color={QUALITY_COLOR[v]}>{QUALITY_LABEL[v] || v}</Tag> },
  { title: 'AI 评分', dataIndex: 'judge_score', width: 100, render: judgeScoreCell },
  {
    title: '评审',
    dataIndex: 'review_status',
    width: 90,
    render: (v, r) => {
      const tag = <Tag color={REVIEW_COLOR[v]}>{REVIEW_LABEL[v] || v}</Tag>;
      return v === 'rejected' && r.reject_reason
        ? <Tooltip title={`驳回原因：${r.reject_reason}`}>{tag}</Tooltip>
        : tag;
    },
  },
];

export default function GenerationHistory({ projectId }) {
  const { message } = App.useApp();
  const [summaries, setSummaries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeSummary, setActiveSummary] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setLoading(true);
    getGenerationSummaries(projectId)
      .then(setSummaries)
      .catch(() => message.error('加载生成记录失败'))
      .finally(() => setLoading(false));
  }, [projectId]);

  const openDetail = async (record) => {
    setActiveSummary(record);
    setDetailLoading(true);
    try {
      setDetail(await getGeneration(projectId, record.id));
    } catch {
      message.error('加载任务详情失败');
      setActiveSummary(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setActiveSummary(null);
    setDetail(null);
  };

  const handleExport = async (format) => {
    if (!activeSummary) return;
    setExporting(true);
    try {
      const res = await exportGenerationDrafts(projectId, activeSummary.id, format, false);
      const ext = format === 'md' ? 'md' : 'xlsx';
      const url = URL.createObjectURL(res.data);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = `${activeSummary.document_title || 'task'}-任务${activeSummary.id}-用例.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      message.error(err.response?.data?.detail || '导出失败');
    } finally {
      setExporting(false);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '需求文档', dataIndex: 'document_title', ellipsis: true, render: v => v || '—' },
    {
      title: '策略',
      dataIndex: 'strategy',
      width: 180,
      render: (v, r) => (
        <Space size={4} wrap>
          <Tag color="blue">{STRATEGY_LABEL[v] || v}</Tag>
          {(r.specialist_skills || []).map(s => <Tag key={s}>{SKILL_LABEL[s] || s}</Tag>)}
        </Space>
      ),
    },
    {
      title: '用例数',
      dataIndex: 'draft_count',
      width: 110,
      render: (v, r) => (v ? <span>{v}<Text type="secondary" style={{ marginLeft: 4 }}>(冒烟 {r.smoke_count})</Text></span> : '—'),
    },
    { title: '采纳率', dataIndex: 'review_stats', width: 130, render: adoptionCell },
    {
      title: '覆盖率',
      dataIndex: 'coverage_rate',
      width: 90,
      render: v => (v === null || v === undefined ? '—' : `${v}%`),
    },
    { title: '状态', dataIndex: 'status', width: 90, render: v => <Tag>{STATUS_LABEL[v] || v}</Tag> },
    { title: '时间', dataIndex: 'created_at', width: 160, render: v => new Date(v).toLocaleString() },
    {
      title: '操作',
      width: 80,
      render: (_, record) => (
        <Button type="link" size="small" onClick={() => openDetail(record)}>查看</Button>
      ),
    },
  ];

  const pendingCount = detail?.review_stats?.pending || 0;

  return (
    <>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={summaries}
        columns={columns}
        pagination={summaries.length > 10 ? { pageSize: 10 } : false}
        locale={{ emptyText: '暂无生成记录，去「AI 用例生成」发起第一次生成' }}
      />

      <Drawer
        title={activeSummary ? `生成记录 #${activeSummary.id} · ${activeSummary.document_title || '未知文档'}` : ''}
        open={!!activeSummary}
        onClose={closeDetail}
        width={880}
        extra={
          <Space>
            {pendingCount > 0 && (
              <Link to={`/projects/${projectId}/generate?task=${activeSummary?.id}`}>
                <Button type="primary">继续评审 ({pendingCount})</Button>
              </Link>
            )}
            <Dropdown
              menu={{
                items: [
                  { key: 'xlsx', label: '导出用例（.xlsx）' },
                  { key: 'md', label: '导出用例（.md）' },
                ],
                onClick: ({ key }) => handleExport(key),
              }}
              disabled={!detail?.drafts?.length}
            >
              <Button loading={exporting} disabled={!detail?.drafts?.length}>导出用例</Button>
            </Dropdown>
          </Space>
        }
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 60 }}><Spin /></div>
        ) : detail && (
          <>
            {detail.status === 'failed' && detail.error_message && (
              <div style={{ marginBottom: 16, padding: 12, background: '#fef2f2', borderRadius: 8, color: '#dc2626' }}>
                {detail.error_message}
              </div>
            )}

            {detail.quality_report && (
              <div className="quality-stats" style={{ marginBottom: 16 }}>
                <div className="quality-stat"><div className="quality-stat-value">{detail.quality_report.total_cases}</div><div className="quality-stat-label">总计</div></div>
                <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#16a34a' }}>{detail.review_stats?.adopted ?? 0}</div><div className="quality-stat-label">已采纳</div></div>
                <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#dc2626' }}>{detail.review_stats?.rejected ?? 0}</div><div className="quality-stat-label">已驳回</div></div>
                <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#ea580c' }}>{detail.review_stats?.pending ?? 0}</div><div className="quality-stat-label">未处理</div></div>
                <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#2563EB' }}>{detail.quality_report.coverage_rate}%</div><div className="quality-stat-label">覆盖率</div></div>
                {detail.quality_report.avg_judge_score != null && (
                  <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#0891B2' }}>{detail.quality_report.avg_judge_score}</div><div className="quality-stat-label">AI 均分</div></div>
                )}
                {detail.tokens_used > 0 && (
                  <div className="quality-stat"><div className="quality-stat-value">{detail.tokens_used >= 1000 ? `${(detail.tokens_used / 1000).toFixed(1)}k` : detail.tokens_used}</div><div className="quality-stat-label">Token</div></div>
                )}
              </div>
            )}

            {detail.quality_report?.suggestions && (
              <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f8fafc', borderRadius: 8, whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.7, color: '#475569' }}>
                {detail.quality_report.suggestions}
              </div>
            )}

            <Table
              rowKey="id"
              size="small"
              dataSource={detail.drafts || []}
              columns={draftColumns}
              pagination={(detail.drafts || []).length > 20 ? { pageSize: 20 } : false}
              expandable={{ expandedRowRender: (r) => <CaseDetail record={r} /> }}
            />
          </>
        )}
      </Drawer>
    </>
  );
}
