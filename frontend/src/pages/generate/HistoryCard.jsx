import { Button, Card, Table, Tag, Tooltip } from 'antd';
import { STATUS_LABEL, STRATEGY_LABEL } from './constants';

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

export default function HistoryCard({ history, onViewTask }) {
  return (
    <Card className="surface-card" title="历史任务" style={{ marginTop: 24 }}>
      <Table rowKey="id" dataSource={history} pagination={false} columns={[
        { title: 'ID', dataIndex: 'id', width: 60 },
        { title: '策略', dataIndex: 'strategy', render: v => STRATEGY_LABEL[v] || v },
        { title: '状态', dataIndex: 'status', render: v => <Tag>{STATUS_LABEL[v] || v}</Tag> },
        { title: '采纳率', dataIndex: 'review_stats', width: 140, render: adoptionCell },
        { title: '时间', dataIndex: 'created_at', render: v => new Date(v).toLocaleString() },
        {
          title: '操作', width: 80,
          render: (_, r) => (
            <Button type="link" onClick={() => onViewTask(r.id)}>查看</Button>
          ),
        },
      ]} />
    </Card>
  );
}
