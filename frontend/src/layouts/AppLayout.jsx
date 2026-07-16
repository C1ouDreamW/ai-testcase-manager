import {
  AppstoreOutlined,
  BookOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FolderOutlined,
  SettingOutlined,
  ThunderboltFilled,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Spin } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { Link, Outlet, useLocation, useParams } from 'react-router-dom';
import { getHomeOverview, getProject } from '../services/api';
import { getProjectWorkAction } from '../utils/projectAction';

const PROJECT_NAV = [
  { key: 'overview', suffix: '', label: '项目概览', icon: AppstoreOutlined },
  { key: 'generate', suffix: '/generate', label: 'AI 生成', icon: ThunderboltOutlined },
];

export default function AppLayout() {
  const { projectId } = useParams();
  const location = useLocation();
  const [project, setProject] = useState(null);
  const [overview, setOverview] = useState(null);
  const [loadingProject, setLoadingProject] = useState(false);
  const [loadingOverview, setLoadingOverview] = useState(false);

  useEffect(() => {
    setLoadingOverview(true);
    getHomeOverview()
      .then(setOverview)
      .catch(() => setOverview(null))
      .finally(() => setLoadingOverview(false));
  }, [location.pathname]);

  useEffect(() => {
    if (!projectId) {
      setProject(null);
      return;
    }
    setLoadingProject(true);
    getProject(projectId)
      .then(setProject)
      .catch(() => setProject(null))
      .finally(() => setLoadingProject(false));
  }, [projectId]);

  const basePath = projectId ? `/projects/${projectId}` : '';
  const isHome = location.pathname === '/';
  const isSettings = location.pathname === '/settings';
  const isTestcases = location.pathname === '/testcases';
  const isKnowledge = location.pathname === '/knowledge';
  const isEvaluation = location.pathname === '/evaluation';

  const recentProjects = useMemo(() => (overview?.projects || []).slice(0, 8), [overview]);

  const continueProject = useMemo(() => {
    if (!overview?.latest_active_project_id) return recentProjects[0] || null;
    return recentProjects.find((p) => p.id === overview.latest_active_project_id) || recentProjects[0] || null;
  }, [overview, recentProjects]);

  const continueAction = continueProject ? getProjectWorkAction(continueProject) : null;

  return (
    <div className="app-layout">
      <div className="app-body">
        <aside className="app-sidebar">
          <Link to="/" className="app-brand">
            <div className="app-brand-icon"><ThunderboltFilled /></div>
            <span className="app-brand-copy">
              <span className="app-brand-title">AI用例管理平台</span>
              <span className="app-brand-subtitle">测试智能工作台</span>
            </span>
          </Link>

          <div className="sidebar-section-label sidebar-section-label-main">工作台</div>
          <nav className="sidebar-nav">
            <Link to="/" className={`sidebar-link${isHome ? ' active' : ''}`}>
              <AppstoreOutlined />
              我的项目
            </Link>
            <Link to="/testcases" className={`sidebar-link${isTestcases ? ' active' : ''}`}>
              <DatabaseOutlined />
              测试用例
            </Link>
            <Link to="/knowledge" className={`sidebar-link${isKnowledge ? ' active' : ''}`}>
              <BookOutlined />
              知识库
            </Link>
            <Link to="/evaluation" className={`sidebar-link${isEvaluation ? ' active' : ''}`}>
              <ExperimentOutlined />
              AI 评测
            </Link>
          </nav>

          {!projectId && continueProject && continueAction && (
            <>
              <div className="sidebar-divider" />
              <Link to={continueAction.path} className="sidebar-continue-link">
                <span className="sidebar-continue-icon"><ThunderboltOutlined /></span>
                <span className="sidebar-continue-content">
                  <span className="sidebar-continue-eyebrow">继续上次工作</span>
                  <span className="sidebar-continue-text">{continueProject.name}</span>
                </span>
                <span className="sidebar-continue-arrow" aria-hidden="true">›</span>
              </Link>
            </>
          )}

          {projectId ? (
            <>
              <div className="sidebar-divider" />
              <div className="sidebar-section-label">当前项目</div>
              <div className="sidebar-project">
                <span className="sidebar-project-icon"><FolderOutlined /></span>
                <span className="sidebar-project-copy">
                  <span className="sidebar-project-meta">正在处理</span>
                  <span className="sidebar-project-name">
                    {loadingProject ? <Spin size="small" /> : project?.name || '加载中...'}
                  </span>
                </span>
              </div>
              <nav className="sidebar-nav">
                {PROJECT_NAV.map(({ key, suffix, label, icon: Icon }) => {
                  const path = `${basePath}${suffix}`;
                  const active = location.pathname === path
                    || (suffix && location.pathname.startsWith(path));
                  return (
                    <Link
                      key={key}
                      to={path}
                      className={`sidebar-link${active ? ' active' : ''}`}
                    >
                      <Icon />
                      {label}
                    </Link>
                  );
                })}
              </nav>
            </>
          ) : (
            <>
              <div className="sidebar-divider" />
              <div className="sidebar-section-label">最近项目</div>
              {loadingOverview ? (
                <div className="sidebar-loading"><Spin size="small" /></div>
              ) : recentProjects.length === 0 ? (
                <div className="sidebar-empty">暂无项目，请先创建</div>
              ) : (
                <nav className="sidebar-nav sidebar-nav-compact">
                  {recentProjects.map((p) => {
                    const active = location.pathname.startsWith(`/projects/${p.id}`);
                    return (
                      <Link
                        key={p.id}
                        to={`/projects/${p.id}`}
                        className={`sidebar-link sidebar-link-compact${active ? ' active' : ''}`}
                        title={p.name}
                      >
                        <FolderOutlined />
                        <span className="sidebar-link-text">{p.name}</span>
                      </Link>
                    );
                  })}
                </nav>
              )}
            </>
          )}

          <div className="sidebar-footer">
            <Link to="/settings" className={`sidebar-link${isSettings ? ' active' : ''}`}>
              <SettingOutlined />
              设置
            </Link>
          </div>
        </aside>

        <main className="app-content">
          <div className="app-content-inner">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
