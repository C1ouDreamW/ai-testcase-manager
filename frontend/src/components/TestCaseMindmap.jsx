import { CaretDownOutlined, CaretRightOutlined, FullscreenExitOutlined, FullscreenOutlined, WarningOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons';
import { Button, Drawer, Empty, Segmented, Space, Tag, Tooltip } from 'antd';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { stepsToText } from '../utils/caseText';

const TYPE_LABEL = { functional: '功能', boundary: '边界', exception: '异常' };
const TYPE_CLASS = { functional: 'mm-type-functional', boundary: 'mm-type-boundary', exception: 'mm-type-exception' };
const PRIORITY_CLASS = { P0: 'tag-p0', P1: 'tag-p1', P2: 'tag-p2' };
const ZOOM_MIN = 0.25;
const ZOOM_MAX = 2.5;
const ZOOM_STEP = 0.1;

function groupCasesByModuleFeature(cases) {
  const modules = {};
  cases.forEach((c) => {
    const mod = c.module?.trim() || '未分类';
    const feat = c.feature?.trim() || '未关联功能点';
    if (!modules[mod]) modules[mod] = {};
    if (!modules[mod][feat]) modules[mod][feat] = [];
    modules[mod][feat].push(c);
  });
  return modules;
}

function buildModuleNodes(modules, keyPrefix = '') {
  return Object.entries(modules).map(([mod, feats]) => {
    const featureNodes = Object.entries(feats).map(([feat, list]) => {
      const types = new Set(list.map((c) => c.case_type));
      const missing = [];
      if (!types.has('boundary')) missing.push('边界');
      if (!types.has('exception')) missing.push('异常');
      return {
        key: `${keyPrefix}m:${mod}|f:${feat}`,
        type: 'feature',
        label: feat,
        count: list.length,
        missing,
        children: list.map((c) => ({
          key: `case:${c.id}`,
          type: 'case',
          label: c.title,
          data: c,
          leaf: true,
        })),
      };
    });
    const modCount = featureNodes.reduce((n, f) => n + f.count, 0);
    return {
      key: `${keyPrefix}m:${mod}`,
      type: 'module',
      label: mod,
      count: modCount,
      children: featureNodes,
    };
  });
}

function buildMindmap(cases, rootLabel, multiProject = false) {
  if (multiProject) {
    const projects = {};
    cases.forEach((c) => {
      const pid = c.project_id;
      const pname = c.project_name || `项目 #${pid}`;
      if (!projects[pid]) projects[pid] = { name: pname, cases: [] };
      projects[pid].cases.push(c);
    });

    const projectNodes = Object.entries(projects).map(([pid, proj]) => {
      const modules = groupCasesByModuleFeature(proj.cases);
      const moduleNodes = buildModuleNodes(modules, `p:${pid}|`);
      const count = proj.cases.length;
      return {
        key: `p:${pid}`,
        type: 'project',
        label: proj.name,
        count,
        children: moduleNodes,
      };
    });

    return {
      key: 'root',
      type: 'root',
      label: rootLabel || '全部用例',
      count: cases.length,
      children: projectNodes,
    };
  }

  const modules = groupCasesByModuleFeature(cases);
  const moduleNodes = buildModuleNodes(modules);

  return {
    key: 'root',
    type: 'root',
    label: rootLabel || '当前项目',
    count: cases.length,
    children: moduleNodes,
  };
}

function collectKeysByType(node, type, acc = []) {
  if (node.type === type) acc.push(node.key);
  (node.children || []).forEach((child) => collectKeysByType(child, type, acc));
  return acc;
}

function Branch({ node, collapsed, onToggle, colorBy, onSelectCase }) {
  const hasChildren = node.children && node.children.length > 0;
  const isCollapsed = collapsed.has(node.key);

  return (
    <div className="mm-subtree">
      <NodeCard
        node={node}
        collapsible={hasChildren}
        isCollapsed={isCollapsed}
        onToggle={onToggle}
        colorBy={colorBy}
        onSelectCase={onSelectCase}
      />
      {hasChildren && !isCollapsed && (
        <div className="mm-children">
          {node.children.map((child) => (
            <div className="mm-child-conn" key={child.key}>
              <Branch
                node={child}
                collapsed={collapsed}
                onToggle={onToggle}
                colorBy={colorBy}
                onSelectCase={onSelectCase}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function NodeCard({ node, collapsible, isCollapsed, onToggle, colorBy, onSelectCase }) {
  if (node.type === 'case') {
    const c = node.data;
    const colorClass = colorBy === 'type' ? TYPE_CLASS[c.case_type] : '';
    return (
      <button
        type="button"
        className={`mm-node mm-node-case ${colorClass}`}
        onClick={() => onSelectCase(c)}
      >
        <span className="mm-case-title">{node.label || '未命名用例'}</span>
        <span className="mm-case-tags">
          <Tag className={PRIORITY_CLASS[c.priority] || ''} variant="filled">{c.priority}</Tag>
          <Tag variant="filled">{TYPE_LABEL[c.case_type] || c.case_type}</Tag>
        </span>
      </button>
    );
  }

  return (
    <div
      className={`mm-node mm-node-${node.type}${collapsible ? ' mm-clickable' : ''}`}
      onClick={collapsible ? () => onToggle(node.key) : undefined}
    >
      {collapsible && (
        <span className="mm-caret">
          {isCollapsed ? <CaretRightOutlined /> : <CaretDownOutlined />}
        </span>
      )}
      <span className="mm-node-label">{node.label}</span>
      <span className="mm-node-count">{node.count}</span>
      {node.type === 'feature' && node.missing && node.missing.length > 0 && (
        <Tooltip title={`缺少${node.missing.join('、')}用例`}>
          <WarningOutlined className="mm-node-warn" />
        </Tooltip>
      )}
    </div>
  );
}

function defaultCollapsedKeys(tree, multiProject) {
  const keys = collectKeysByType(tree, 'feature');
  if (multiProject) {
    collectKeysByType(tree, 'project').forEach((k) => keys.push(k));
  }
  return new Set(keys);
}

export default function TestCaseMindmap({
  cases = [],
  projectName = '',
  rootLabel,
  multiProject = false,
  showFullMapButton = false,
  onEditCase,
}) {
  const [collapsed, setCollapsed] = useState(() => new Set());
  const [colorBy, setColorBy] = useState('priority');
  const [activeCase, setActiveCase] = useState(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [contentSize, setContentSize] = useState({ w: 0, h: 0 });
  const canvasRef = useRef(null);
  const innerRef = useRef(null);

  const label = rootLabel || projectName || '当前项目';
  const tree = useMemo(
    () => buildMindmap(cases, label, multiProject),
    [cases, label, multiProject],
  );

  useEffect(() => {
    setCollapsed(defaultCollapsedKeys(tree, multiProject));
    setFullscreen(false);
    setZoom(1);
  }, [tree, multiProject]);

  const updateContentSize = useCallback(() => {
    if (!innerRef.current) return;
    setContentSize({
      w: innerRef.current.offsetWidth,
      h: innerRef.current.offsetHeight,
    });
  }, []);

  useEffect(() => {
    updateContentSize();
  }, [tree, collapsed, updateContentSize]);

  useEffect(() => {
    const el = innerRef.current;
    if (!el) return undefined;
    const observer = new ResizeObserver(updateContentSize);
    observer.observe(el);
    return () => observer.disconnect();
  }, [updateContentSize, tree, collapsed]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const onWheel = (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      setZoom((z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, +(z + delta).toFixed(2))));
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, []);

  const zoomIn = () => setZoom((z) => Math.min(ZOOM_MAX, +(z + ZOOM_STEP).toFixed(2)));
  const zoomOut = () => setZoom((z) => Math.max(ZOOM_MIN, +(z - ZOOM_STEP).toFixed(2)));
  const zoomReset = () => setZoom(1);

  useEffect(() => {
    if (!activeCase) return;
    const latest = cases.find((c) => c.id === activeCase.id);
    if (latest) setActiveCase(latest);
  }, [cases, activeCase?.id]);

  const exitFullscreen = useCallback(() => {
    setFullscreen(false);
    setZoom(1);
    setCollapsed(defaultCollapsedKeys(tree, multiProject));
  }, [tree, multiProject]);

  useEffect(() => {
    if (!fullscreen) return undefined;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKeyDown = (e) => {
      if (e.key === 'Escape') exitFullscreen();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [fullscreen, exitFullscreen]);

  const toggle = (key) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const expandAll = () => setCollapsed(new Set());
  const collapseToProject = () => setCollapsed(new Set(collectKeysByType(tree, 'project')));
  const collapseToModule = () => setCollapsed(new Set(collectKeysByType(tree, 'module')));
  const collapseToFeature = () => setCollapsed(defaultCollapsedKeys(tree, multiProject));

  const toggleFullscreen = () => {
    setFullscreen((prev) => {
      const next = !prev;
      if (next) {
        setCollapsed(new Set());
        setZoom(1);
      } else {
        setCollapsed(defaultCollapsedKeys(tree, multiProject));
        setZoom(1);
      }
      return next;
    });
  };

  if (!cases.length) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div>
            <div className="empty-state-title">暂无用例</div>
            <div className="empty-state-desc">采纳 AI 生成的用例入库后，会在此以脑图呈现结构</div>
          </div>
        }
      />
    );
  }

  return (
    <div className={`mm-wrap${fullscreen ? ' mm-wrap-fullscreen' : ''}`}>
      <div className="mm-toolbar">
        <Space size={8} wrap>
          {showFullMapButton && (
            <button type="button" className={`mm-toolbar-btn${fullscreen ? ' mm-toolbar-btn-active' : ''}`} onClick={toggleFullscreen}>
              {fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              {fullscreen ? '退出全图' : '全图展示'}
            </button>
          )}
          <button type="button" className="mm-toolbar-btn" onClick={expandAll}>展开全部</button>
          {multiProject && (
            <button type="button" className="mm-toolbar-btn" onClick={collapseToProject}>折叠到项目</button>
          )}
          <button type="button" className="mm-toolbar-btn" onClick={collapseToFeature}>折叠到功能点</button>
          <button type="button" className="mm-toolbar-btn" onClick={collapseToModule}>折叠到模块</button>
          <Space size={4} className="mm-zoom-controls">
            <Tooltip title="缩小">
              <button type="button" className="mm-toolbar-btn mm-toolbar-btn-icon" onClick={zoomOut} disabled={zoom <= ZOOM_MIN}>
                <ZoomOutOutlined />
              </button>
            </Tooltip>
            <button type="button" className="mm-toolbar-btn mm-zoom-label" onClick={zoomReset}>
              {Math.round(zoom * 100)}%
            </button>
            <Tooltip title="放大">
              <button type="button" className="mm-toolbar-btn mm-toolbar-btn-icon" onClick={zoomIn} disabled={zoom >= ZOOM_MAX}>
                <ZoomInOutlined />
              </button>
            </Tooltip>
          </Space>
        </Space>
        <Space size={8} align="center">
          <span className="mm-toolbar-label">用例着色</span>
          <Segmented
            size="small"
            value={colorBy}
            onChange={setColorBy}
            options={[{ label: '优先级', value: 'priority' }, { label: '类型', value: 'type' }]}
          />
        </Space>
      </div>

      <div ref={canvasRef} className={`mm-canvas${fullscreen ? ' mm-canvas-fullscreen' : ''}`}>
        <div
          className="mm-canvas-scaler"
          style={{
            width: contentSize.w ? contentSize.w * zoom : undefined,
            height: contentSize.h ? contentSize.h * zoom : undefined,
          }}
        >
          <div
            ref={innerRef}
            className="mm-canvas-inner"
            style={{
              transform: zoom === 1 ? undefined : `scale(${zoom})`,
              transformOrigin: 'top left',
            }}
          >
            <Branch
              node={tree}
              collapsed={collapsed}
              onToggle={toggle}
              colorBy={colorBy}
              onSelectCase={setActiveCase}
            />
          </div>
        </div>
      </div>

      <Drawer
        title={activeCase?.title || '用例详情'}
        width={460}
        open={!!activeCase}
        onClose={() => setActiveCase(null)}
        extra={onEditCase && activeCase ? (
          <Button type="link" onClick={() => onEditCase(activeCase)}>编辑</Button>
        ) : null}
      >
        {activeCase && (
          <div className="mm-detail">
            <div className="mm-detail-tags">
              <Tag className={PRIORITY_CLASS[activeCase.priority] || ''} variant="filled">{activeCase.priority}</Tag>
              <Tag variant="filled">{TYPE_LABEL[activeCase.case_type] || activeCase.case_type}</Tag>
              {activeCase.project_name && <Tag variant="filled">{activeCase.project_name}</Tag>}
              {activeCase.module && <Tag variant="filled">{activeCase.module}</Tag>}
              {activeCase.feature && <Tag variant="filled">{activeCase.feature}</Tag>}
            </div>
            <div className="case-detail">
              <div className="case-detail-row">
                <span className="case-detail-label">前置条件</span>{activeCase.precondition || '无'}
              </div>
              <div className="case-detail-row">
                <span className="case-detail-label">操作步骤</span>
                <span style={{ whiteSpace: 'pre-wrap' }}>{stepsToText(activeCase.steps)}</span>
              </div>
              <div className="case-detail-row">
                <span className="case-detail-label">预期结果</span>{activeCase.expected_result || '无'}
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
