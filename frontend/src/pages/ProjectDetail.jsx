import {
  ApartmentOutlined,
  DatabaseOutlined,
  HistoryOutlined,
  RightOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Card, Col, Row, Spin, Tabs, Tag } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import GenerationHistory from '../components/GenerationHistory';
import TestCaseMindmap from '../components/TestCaseMindmap';
import { getGenerations, getProject, getTestcases } from '../services/api';

const TYPE_META = [
  { key: 'functional', label: '功能', color: 'var(--type-functional)' },
  { key: 'boundary', label: '边界', color: 'var(--type-boundary)' },
  { key: 'exception', label: '异常', color: 'var(--type-exception)' },
];
const PRIORITY_META = [
  { key: 'P0', label: 'P0', color: 'var(--priority-p0)' },
  { key: 'P1', label: 'P1', color: 'var(--priority-p1)' },
  { key: 'P2', label: 'P2', color: 'var(--priority-p2)' },
];

function hasRealDescription(desc) {
  const text = desc?.trim();
  return text && text.length > 2 && !/^\d+$/.test(text);
}

function StatCard({ icon, label, value, color }) {
  return (
    <Card className="stat-card" styles={{ body: { padding: 24 } }}>
      <div className="stat-card-icon" style={{ background: `${color}18`, color }}>
        {icon}
      </div>
      <div className="stat-card-value">{value}</div>
      <div className="stat-card-label">{label}</div>
    </Card>
  );
}

function DistRow({ label, segments, total }) {
  return (
    <div className="dist-row">
      <div className="dist-head">
        <span className="dist-label">{label}</span>
      </div>
      <div className="dist-bar">
        {total === 0 ? (
          <div className="dist-seg dist-seg-empty" style={{ width: '100%' }} />
        ) : (
          segments.map((s) => s.value > 0 && (
            <div
              key={s.label}
              className="dist-seg"
              style={{ width: `${(s.value / total) * 100}%`, background: s.color }}
              title={`${s.label} ${s.value}`}
            />
          ))
        )}
      </div>
      <div className="dist-legend">
        {segments.map((s) => (
          <span key={s.label} className="dist-legend-item">
            <i className="dist-dot" style={{ background: s.color }} />
            {s.label} <strong>{s.value}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function ProjectDetail() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const [project, setProject] = useState(null);
  const [cases, setCases] = useState([]);
  const [generations, setGenerations] = useState([]);
  const [stats, setStats] = useState({ testcases: 0, generations: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [p, tc, gen] = await Promise.all([
          getProject(projectId),
          getTestcases(projectId),
          getGenerations(projectId),
        ]);
        setProject(p);
        setCases(tc);
        setGenerations(gen);
        setStats({ testcases: tc.length, generations: gen.length });
      } finally {
        setLoading(false);
      }
    })();
  }, [projectId]);

  // 汇总所有已评审任务的信号：采纳率 / 编辑率 / 驳回率
  const reviewSummary = useMemo(() => {
    const reviewed = generations.filter((g) => g.review_stats?.reviewed);
    if (!reviewed.length) return null;
    const sum = reviewed.reduce(
      (acc, g) => {
        acc.total += g.review_stats.total;
        acc.adopted += g.review_stats.adopted;
        acc.rejected += g.review_stats.rejected;
        acc.editedAdopted += g.review_stats.edited_adopted;
        return acc;
      },
      { total: 0, adopted: 0, rejected: 0, editedAdopted: 0 },
    );
    const rate = (part, whole) => (whole ? Math.round((part / whole) * 1000) / 10 : 0);
    return {
      taskCount: reviewed.length,
      total: sum.total,
      adopted: sum.adopted,
      adoptionRate: rate(sum.adopted, sum.total),
      editRate: rate(sum.editedAdopted, sum.adopted),
      rejectionRate: rate(sum.rejected, sum.total),
    };
  }, [generations]);

  const composition = useMemo(() => {
    const byType = { functional: 0, boundary: 0, exception: 0 };
    const byPriority = { P0: 0, P1: 0, P2: 0 };
    let ai = 0;
    cases.forEach((c) => {
      if (byType[c.case_type] !== undefined) byType[c.case_type] += 1;
      if (byPriority[c.priority] !== undefined) byPriority[c.priority] += 1;
      if (c.source === 'ai_generated') ai += 1;
    });
    const total = cases.length;
    return {
      typeSegments: TYPE_META.map((m) => ({ label: m.label, color: m.color, value: byType[m.key] })),
      prioritySegments: PRIORITY_META.map((m) => ({ label: m.label, color: m.color, value: byPriority[m.key] })),
      aiRatio: total ? Math.round((ai / total) * 100) : 0,
      total,
    };
  }, [cases]);

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;
  }

  if (!project) return null;

  return (
    <div>
      <PageHeader
        title={project.name}
        description={hasRealDescription(project.description) ? project.description : '暂无项目描述'}
        extra={<Tag color="processing">进行中</Tag>}
      />

      <Tabs
        defaultActiveKey={searchParams.get('tab') || 'overview'}
        items={[
          {
            key: 'overview',
            label: '概览',
            children: (
              <>
                <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
                  <Col xs={24} sm={12} lg={8}>
                    <StatCard
                      icon={<DatabaseOutlined />}
                      label="用例总数"
                      value={stats.testcases}
                      color="#2563EB"
                    />
                  </Col>
                  <Col xs={24} sm={12} lg={8}>
                    <StatCard
                      icon={<ThunderboltOutlined />}
                      label="生成任务"
                      value={stats.generations}
                      color="#06b6d4"
                    />
                  </Col>
                  <Col xs={24} sm={24} lg={8}>
                    <StatCard
                      icon={<RobotOutlined />}
                      label="AI 生成占比"
                      value={`${composition.aiRatio}%`}
                      color="#0891B2"
                    />
                  </Col>
                </Row>

                {reviewSummary && (
                  <Card
                    className="surface-card"
                    title="AI 生成质量（近期评审信号）"
                    style={{ marginBottom: 24 }}
                  >
                    <Row gutter={[16, 16]}>
                      <Col xs={8}>
                        <div className="review-metric">
                          <div className="review-metric-value" style={{ color: '#16a34a' }}>{reviewSummary.adoptionRate}%</div>
                          <div className="review-metric-label">采纳率</div>
                          <div className="review-metric-sub">{reviewSummary.adopted} / {reviewSummary.total} 条被采纳</div>
                        </div>
                      </Col>
                      <Col xs={8}>
                        <div className="review-metric">
                          <div className="review-metric-value" style={{ color: '#ea580c' }}>{reviewSummary.editRate}%</div>
                          <div className="review-metric-label">编辑率</div>
                          <div className="review-metric-sub">采纳前需人工修改的比例</div>
                        </div>
                      </Col>
                      <Col xs={8}>
                        <div className="review-metric">
                          <div className="review-metric-value" style={{ color: '#dc2626' }}>{reviewSummary.rejectionRate}%</div>
                          <div className="review-metric-label">驳回率</div>
                          <div className="review-metric-sub">完全不可用的比例</div>
                        </div>
                      </Col>
                    </Row>
                    <div className="review-metric-note">
                      基于 {reviewSummary.taskCount} 次已评审的生成任务汇总，反映 AI 生成用例的实际可用程度
                    </div>
                  </Card>
                )}

                <Row gutter={[16, 16]}>
                  <Col xs={24} md={12}>
                    <Card className="surface-card" title="用例构成" style={{ height: '100%' }}>
                      {composition.total === 0 ? (
                        <div className="dist-empty">暂无用例，生成并采纳后展示构成</div>
                      ) : (
                        <>
                          <DistRow label="按类型" segments={composition.typeSegments} total={composition.total} />
                          <DistRow label="按优先级" segments={composition.prioritySegments} total={composition.total} />
                        </>
                      )}
                    </Card>
                  </Col>
                  <Col xs={24} md={12}>
                    <div className="action-card-stack">
                      <Link to={`/projects/${projectId}/generate`} className="action-card">
                        <div className="action-card-icon"><ThunderboltOutlined /></div>
                        <div className="action-card-text">
                          <h4>开始 AI 生成</h4>
                          <p>导入需求文档，按功能点生成候选用例</p>
                        </div>
                        <RightOutlined style={{ marginLeft: 'auto', color: '#94a3b8' }} />
                      </Link>
                      <Link to={`/testcases?project=${projectId}`} className="action-card">
                        <div className="action-card-icon"><DatabaseOutlined /></div>
                        <div className="action-card-text">
                          <h4>查看测试用例</h4>
                          <p>浏览已采纳入库的测试用例</p>
                        </div>
                        <RightOutlined style={{ marginLeft: 'auto', color: '#94a3b8' }} />
                      </Link>
                    </div>
                  </Col>
                </Row>
              </>
            ),
          },
          {
            key: 'mindmap',
            label: <span><ApartmentOutlined /> 用例脑图</span>,
            children: <TestCaseMindmap cases={cases} projectName={project.name} />,
          },
          {
            key: 'generations',
            label: <span><HistoryOutlined /> 生成记录</span>,
            children: <GenerationHistory projectId={projectId} />,
          },
        ]}
      />
    </div>
  );
}
