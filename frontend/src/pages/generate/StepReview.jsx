import { useState } from 'react';
import { Button, Card, Dropdown, Input, Modal, Progress, Radio, Segmented, Space, Table, Tag, Typography } from 'antd';
import {
  QUALITY_COLOR, QUALITY_LABEL, REJECT_REASONS, REVIEW_COLOR, REVIEW_LABEL, SKILL_LABEL, TYPE_LABEL,
} from './constants';
import { CaseDetail, judgeScoreCell, priorityTag } from './DetailPanels';

const { Text } = Typography;

export default function StepReview({
  task,
  draftSuiteFilter,
  setDraftSuiteFilter,
  draftExporting,
  selectedDrafts,
  setSelectedDrafts,
  pendingDraftCount,
  onExportDrafts,
  onEditDraft,
  onSelectAllDrafts,
  onAdopt,
  onReject,
  onFinish,
  onBack,
  onNewTask,
}) {
  const selectedPendingCount = selectedDrafts.filter(id => {
    const d = task.drafts?.find(x => x.id === id);
    return d && !['adopted', 'rejected'].includes(d.review_status);
  }).length;
  const reviewedCount = (task.drafts || []).filter(d => ['adopted', 'rejected'].includes(d.review_status)).length;

  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState(REJECT_REASONS[0]);
  const [rejectCustom, setRejectCustom] = useState('');

  const confirmReject = () => {
    const reason = rejectReason === '其他' ? (rejectCustom.trim() || '其他') : rejectReason;
    setRejectModalOpen(false);
    setRejectCustom('');
    onReject(reason);
  };
  const draftColumns = [
    { title: '用例标题', dataIndex: 'title', ellipsis: true },
    {
      title: '用例集',
      dataIndex: 'is_smoke',
      width: 80,
      render: v => (v ? <Tag color="green">冒烟</Tag> : <Tag>完整</Tag>),
    },
    { title: '类型', dataIndex: 'case_type', width: 80, render: v => <Tag>{TYPE_LABEL[v] || v}</Tag> },
    { title: '来源 Skill', dataIndex: 'skill_name', width: 110, ellipsis: true, render: v => <Tag>{SKILL_LABEL[v] || v || '—'}</Tag> },
    { title: '优先级', dataIndex: 'priority', width: 80, render: priorityTag },
    { title: '质量', dataIndex: 'quality_status', width: 90, render: v => <Tag color={QUALITY_COLOR[v]}>{QUALITY_LABEL[v] || v}</Tag> },
    { title: 'AI 评分', dataIndex: 'judge_score', width: 100, render: judgeScoreCell },
    { title: '状态', dataIndex: 'review_status', width: 90, render: v => <Tag color={REVIEW_COLOR[v]}>{REVIEW_LABEL[v] || v}</Tag> },
    {
      title: '操作',
      width: 80,
      render: (_, record) => (
        <Button type="link" size="small" onClick={() => onEditDraft(record)} disabled={record.review_status === 'adopted'}>
          编辑
        </Button>
      ),
    },
  ];

  return (
    <Card className="surface-card" title="生成结果与评审">
      {task.status === 'generating' && (
        <div style={{ marginBottom: 20 }}>
          <Progress percent={task.progress} status="active" strokeColor="#2563EB" />
          <Text type="secondary" style={{ marginTop: 8, display: 'block' }}>
            {task.stage || 'AI 正在按功能点生成用例...'}
          </Text>
        </div>
      )}
      {task.status === 'failed' && (
        <div style={{ marginBottom: 16, padding: 12, background: '#fef2f2', borderRadius: 8, color: '#dc2626' }}>
          {task.error_message}
        </div>
      )}

      {task.quality_report && (
        <>
          <div className="quality-stats">
            <div className="quality-stat"><div className="quality-stat-value">{task.quality_report.total_cases}</div><div className="quality-stat-label">总计</div></div>
            <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#16a34a' }}>{task.quality_report.pass_count}</div><div className="quality-stat-label">通过</div></div>
            <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#ea580c' }}>{task.quality_report.warning_count}</div><div className="quality-stat-label">警告</div></div>
            <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#dc2626' }}>{task.quality_report.fail_count}</div><div className="quality-stat-label">不合格</div></div>
            <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#2563EB' }}>{task.quality_report.coverage_rate}%</div><div className="quality-stat-label">覆盖率</div></div>
            {task.quality_report.avg_judge_score != null && (
              <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#0891B2' }}>{task.quality_report.avg_judge_score}</div><div className="quality-stat-label">AI 均分</div></div>
            )}
            {task.quality_report.hallucination_count > 0 && (
              <div className="quality-stat"><div className="quality-stat-value" style={{ color: '#dc2626' }}>{task.quality_report.hallucination_count}</div><div className="quality-stat-label">疑似幻觉</div></div>
            )}
          </div>
          {task.quality_report.suggestions && (
            <Card size="small" className="surface-card" title="AI 评测建议" style={{ marginBottom: 20 }}>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.7, color: '#475569' }}>{task.quality_report.suggestions}</div>
            </Card>
          )}
        </>
      )}

      {(() => {
        let refs = null;
        try {
          refs = task.knowledge_refs ? JSON.parse(task.knowledge_refs) : null;
        } catch { refs = null; }
        const entries = refs ? Object.values(refs).flat() : [];
        if (!entries.length) return null;
        const unique = [...new Map(entries.map(r => [`${r.title}|${r.heading}`, r])).values()];
        return (
          <Card size="small" className="surface-card" title="本次生成引用的知识库内容" style={{ marginBottom: 20 }}>
            <Space wrap>
              {unique.map((r, i) => (
                <Tag key={i} color="cyan">
                  《{r.title}》{r.heading ? ` · ${r.heading}` : ''}
                </Tag>
              ))}
            </Space>
          </Card>
        );
      })()}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 12 }}>
        <Segmented
          value={draftSuiteFilter}
          onChange={setDraftSuiteFilter}
          options={[
            { label: `全部 (${task.drafts?.length || 0})`, value: 'all' },
            { label: `冒烟 (${(task.drafts || []).filter(d => d.is_smoke).length})`, value: 'smoke' },
          ]}
        />
        <Dropdown
          menu={{
            items: [
              { key: 'xlsx', label: '导出用例（.xlsx）' },
              { key: 'md', label: '导出用例（.md）' },
            ],
            onClick: ({ key }) => onExportDrafts(key),
          }}
          disabled={!task.drafts?.length}
        >
          <Button loading={draftExporting} disabled={!task.drafts?.length}>
            导出用例{draftSuiteFilter === 'smoke' ? '（仅冒烟）' : ''}
          </Button>
        </Dropdown>
      </div>
      <Table
        rowKey="id"
        dataSource={(task.drafts || []).filter(d => draftSuiteFilter === 'all' || d.is_smoke)}
        columns={draftColumns}
        rowSelection={{
          selectedRowKeys: selectedDrafts,
          onChange: setSelectedDrafts,
          getCheckboxProps: (record) => ({
            disabled: record.review_status === 'adopted' || record.review_status === 'rejected',
          }),
        }}
        expandable={{ expandedRowRender: (r) => <CaseDetail record={r} /> }}
      />
      <Space style={{ marginTop: 20 }} wrap>
        <Button onClick={onBack}>上一步</Button>
        <Button onClick={onSelectAllDrafts} disabled={!pendingDraftCount}>
          一键全选 ({pendingDraftCount})
        </Button>
        <Button type="primary" size="large" onClick={onAdopt}>
          采纳选中 ({selectedPendingCount})
        </Button>
        <Button danger disabled={!selectedPendingCount} onClick={() => setRejectModalOpen(true)}>
          驳回选中 ({selectedPendingCount})
        </Button>
        {reviewedCount > 0 && (
          <Button onClick={onFinish}>
            完成评审{pendingDraftCount > 0 ? `（跳过剩余 ${pendingDraftCount} 条）` : ''}
          </Button>
        )}
        <Button onClick={onNewTask}>新建任务</Button>
      </Space>

      <Modal
        title={`驳回选中的 ${selectedPendingCount} 条用例`}
        open={rejectModalOpen}
        onOk={confirmReject}
        onCancel={() => setRejectModalOpen(false)}
        okText="确认驳回"
        okButtonProps={{ danger: true }}
        cancelText="取消"
        width={440}
      >
        <div style={{ marginBottom: 12, color: '#64748b', fontSize: 13 }}>
          驳回后不可再采纳，将计入驳回率。选择原因可帮助归因分析：
        </div>
        <Radio.Group
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          {REJECT_REASONS.map((r) => <Radio key={r} value={r}>{r}</Radio>)}
        </Radio.Group>
        {rejectReason === '其他' && (
          <Input.TextArea
            rows={2}
            style={{ marginTop: 12 }}
            placeholder="补充说明（可选）"
            value={rejectCustom}
            onChange={(e) => setRejectCustom(e.target.value)}
            maxLength={100}
          />
        )}
      </Modal>
    </Card>
  );
}
