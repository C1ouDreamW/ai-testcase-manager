import {
  CloseOutlined, DownOutlined, EnterOutlined, EyeOutlined, FileTextOutlined, LinkOutlined,
  LoadingOutlined, PaperClipOutlined, PictureOutlined, SendOutlined, ToolOutlined,
} from '@ant-design/icons';
import { App, Button, Dropdown, Empty, Image, Input, Spin, Tag, Upload } from 'antd';
import {
  forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState,
} from 'react';
import { useNavigate } from 'react-router-dom';
import {
  addFigmaDesign, clearAgentMessages, getAgentMessages, getDesignContent, getRequirements,
  mergeDesignInsights, streamAgentChat, uploadDesignAsset, uploadRequirementFile,
} from '../services/api';

// 解析 [文本](链接) 为可点击节点：站内路径走 SPA 跳转，外链新开页
const MD_LINK_RE = /\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]*)\)/g;

function renderRichText(text, navigate, isUser) {
  const value = text || '';
  const nodes = [];
  let lastIndex = 0;
  let match;
  MD_LINK_RE.lastIndex = 0;
  let key = 0;
  while ((match = MD_LINK_RE.exec(value)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(value.slice(lastIndex, match.index));
    }
    const [, label, href] = match;
    const isInternal = href.startsWith('/');
    const linkColor = isUser ? '#fff' : 'var(--ant-color-primary, #4f46e5)';
    if (isInternal) {
      nodes.push(
        <a
          key={`lnk-${key}`}
          href={href}
          onClick={(e) => { e.preventDefault(); navigate(href); }}
          style={{ color: linkColor, textDecoration: 'underline' }}
        >
          {label}
        </a>,
      );
    } else {
      nodes.push(
        <a
          key={`lnk-${key}`}
          href={href}
          target="_blank"
          rel="noreferrer"
          style={{ color: linkColor, textDecoration: 'underline' }}
        >
          {label}
        </a>,
      );
    }
    lastIndex = match.index + match[0].length;
    key += 1;
  }
  if (lastIndex < value.length) {
    nodes.push(value.slice(lastIndex));
  }
  return nodes.length ? nodes : [value];
}

const TOOL_LABEL = {
  search_knowledge: '检索知识库',
  list_testcases: '查询用例列表',
  get_testcase_detail: '查询用例详情',
  get_coverage_summary: '统计需求覆盖',
  get_test_task_stats: '查询测试进度',
  list_defects: '查询缺陷记录',
  list_requirement_documents: '查询需求文档',
  list_design_assets: '查询设计稿',
  parse_design_asset: '解析设计稿',
  get_design_insights: '查看设计功能点',
  merge_design_insights: '合并设计功能点',
};

const toolLabel = (name) => TOOL_LABEL[name] || name;
const DEFAULT_PARSE_QUESTION = '请解析这些设计稿并列出功能点，等待我确认后再合并。';
const FIGMA_URL_RE = /https:\/\/(?:www\.)?figma\.com\/[^\s]+/gi;
const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const DOC_EXT_RE = /\.(docx|md|markdown)$/i;
const MAX_ATTACHMENTS = 8;
const MAX_DOC_UPLOADS = 3;

/** 从输入正文里识别 Figma 链接，省掉单独的链接输入框。 */
function extractFigmaUrls(text) {
  const matches = (text || '').match(FIGMA_URL_RE) || [];
  const cleaned = matches.map((url) => url.replace(/[)\]}>，。；、,.;]+$/, ''));
  return [...new Set(cleaned)].slice(0, MAX_ATTACHMENTS);
}

function snippet(text, max = 80) {
  const value = (text || '').trim().replace(/\s+/g, ' ');
  if (!value) return '（无文字内容）';
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

/** 已上传设计稿缩略图：鉴权拉取 blob 后展示，支持预览。 */
function DesignImageThumb({ projectId, asset, size = 72 }) {
  const [src, setSrc] = useState('');

  useEffect(() => {
    let active = true;
    let objectUrl = '';
    if (asset?.asset_type === 'image' && asset.asset_id && projectId) {
      getDesignContent(projectId, asset.asset_id).then((response) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(response.data);
        setSrc(objectUrl);
      }).catch(() => {});
    }
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId, asset?.asset_id, asset?.asset_type]);

  if (asset?.asset_type === 'figma') {
    return (
      <a
        href={asset.figma_url}
        target="_blank"
        rel="noreferrer"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          padding: '4px 8px',
          borderRadius: 8,
          background: '#eff6ff',
          color: '#2563eb',
          fontSize: 12,
        }}
      >
        <LinkOutlined />
        {asset.title || '打开 Figma'}
      </a>
    );
  }

  if (!src) {
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: 8,
          background: '#f1f5f9',
          display: 'grid',
          placeItems: 'center',
        }}
      >
        <LoadingOutlined />
      </div>
    );
  }

  return (
    <Image
      src={src}
      width={size}
      height={size}
      style={{ objectFit: 'cover', borderRadius: 8 }}
      preview={{ mask: <><EyeOutlined /> 预览</> }}
    />
  );
}

/** 本地待发送文件预览。 */
function LocalFileThumb({ file, onRemove, size = 56 }) {
  const [src, setSrc] = useState('');
  useEffect(() => {
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      {src ? (
        <Image
          src={src}
          width={size}
          height={size}
          style={{ objectFit: 'cover', borderRadius: 8 }}
          preview={{ mask: <><EyeOutlined /> 预览</> }}
        />
      ) : (
        <div style={{
          width: size, height: size, borderRadius: 8, background: '#f1f5f9',
          display: 'grid', placeItems: 'center',
        }}
        >
          <PictureOutlined />
        </div>
      )}
      {onRemove && (
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={onRemove}
          style={{
            position: 'absolute', top: -6, right: -6, width: 20, height: 20,
            minWidth: 20, padding: 0, borderRadius: '50%', background: '#fff',
            boxShadow: '0 0 0 1px #e2e8f0',
          }}
        />
      )}
    </div>
  );
}

function AttachmentGallery({ projectId, attachments, size = 72 }) {
  if (!attachments?.length) return null;
  return (
    <div style={{ marginBottom: 6, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      <Image.PreviewGroup>
        {attachments.map((a) => (
          <DesignImageThumb
            key={a.asset_id}
            projectId={projectId}
            asset={a}
            size={size}
          />
        ))}
      </Image.PreviewGroup>
    </div>
  );
}

function ReplyQuote({ replyTo, isUser, onClear, compact }) {
  if (!replyTo) return null;
  const roleLabel = replyTo.role === 'user' ? '用户' : '助手';
  return (
    <div
      style={{
        marginBottom: compact ? 6 : 8,
        padding: '6px 10px',
        borderRadius: 8,
        borderLeft: `3px solid ${isUser ? 'rgba(255,255,255,0.65)' : '#818cf8'}`,
        background: isUser ? 'rgba(255,255,255,0.15)' : '#eef2ff',
        color: isUser ? 'rgba(255,255,255,0.92)' : '#4338ca',
        fontSize: 12,
        lineHeight: 1.5,
        display: 'flex',
        gap: 8,
        alignItems: 'flex-start',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, marginBottom: 2 }}>回复 {roleLabel}</div>
        <div style={{ opacity: 0.9, wordBreak: 'break-word' }}>{snippet(replyTo.content)}</div>
      </div>
      {onClear && (
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={onClear}
          style={{ color: 'inherit', flexShrink: 0 }}
        />
      )}
    </div>
  );
}

function ConfirmMergeCard({ msg, projectId, onMerged }) {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  if (!msg.pendingInsightIds?.length || msg.mergeDone || msg.role !== 'assistant') return null;

  const handleMerge = async () => {
    if (!msg.documentId) {
      message.warning('缺少目标需求文档，无法合并');
      return;
    }
    setLoading(true);
    try {
      await mergeDesignInsights(projectId, msg.documentId, msg.pendingInsightIds);
      message.success('已合并到需求，请重新确认功能点后再生成');
      onMerged?.();
    } catch (err) {
      message.error(err.response?.data?.detail || err.message || '合并失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        marginTop: 8,
        padding: 10,
        borderRadius: 8,
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
      }}
    >
      <div style={{ fontSize: 12, color: '#475569', marginBottom: 8 }}>
        解析出 {msg.pendingInsightIds.length} 个待确认功能点。确认无误后再合并到需求。
      </div>
      <Button type="primary" size="small" loading={loading} onClick={handleMerge}>
        确认合并
      </Button>
    </div>
  );
}

function MessageBubble({ msg, projectId, onMerged, onReply, canReply, navigate }) {
  const isUser = msg.role === 'user';
  return (
    <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
      <div style={{ maxWidth: '85%' }}>
        {!isUser && msg.toolCalls?.length > 0 && (
          <div style={{ marginBottom: 4 }}>
            {msg.toolCalls.map((name, i) => (
              <Tag key={`${name}-${i}`} icon={<ToolOutlined />} style={{ marginBottom: 2 }}>
                {toolLabel(name)}
              </Tag>
            ))}
          </div>
        )}
        <div
          style={{
            padding: '8px 12px',
            borderRadius: 10,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontSize: 13,
            lineHeight: 1.7,
            background: isUser ? 'var(--ant-color-primary, #4f46e5)' : '#f5f5f7',
            color: isUser ? '#fff' : 'inherit',
          }}
        >
          <ReplyQuote replyTo={msg.replyTo} isUser={isUser} compact />
          <AttachmentGallery projectId={projectId} attachments={msg.attachments} />
          {msg.content
            ? renderRichText(msg.content, navigate, isUser)
            : (msg.streaming ? '' : '（无回答内容）')}
          {msg.streaming && (
            <span style={{ color: isUser ? 'rgba(255,255,255,0.8)' : '#888', fontSize: 12 }}>
              <LoadingOutlined style={{ marginRight: 6 }} />
              {msg.activity || '思考中…'}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', marginTop: 4 }}>
          {canReply && msg.id && !msg.streaming && (
            <Button
              type="text"
              size="small"
              icon={<EnterOutlined />}
              onClick={() => onReply?.(msg)}
              style={{ fontSize: 12, color: '#64748b', height: 24, padding: '0 6px' }}
            >
              回复
            </Button>
          )}
        </div>
        <ConfirmMergeCard
          msg={msg}
          projectId={projectId}
          onMerged={() => onMerged?.(msg)}
        />
        {msg.error && (
          <div style={{ color: '#dc2626', fontSize: 12, marginTop: 4 }}>{msg.error}</div>
        )}
      </div>
    </div>
  );
}

/**
 * 测试助手对话核心：消息列表 + 输入框 + SSE 流式渲染。
 * 悬浮抽屉与全局页面共用；active 为 false 时暂不加载历史（如抽屉未打开）。
 * ref 暴露 clear()；onMetaChange 上报 { hasMessages, streaming } 供外部按钮联动。
 */
const AgentChat = forwardRef(function AgentChat({
  projectId, active = true, onMetaChange, style,
}, ref) {
  const { message, modal } = App.useApp();
  const navigate = useNavigate();
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [docs, setDocs] = useState([]);
  const [documentId, setDocumentId] = useState(null);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [pendingDocs, setPendingDocs] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [replyTo, setReplyTo] = useState(null);
  const listRef = useRef(null);
  const abortRef = useRef(null);

  const figmaUrls = useMemo(() => extractFigmaUrls(input), [input]);
  const hasAttachments = pendingFiles.length > 0 || figmaUrls.length > 0;
  const hasPendingDocs = pendingDocs.length > 0;
  const targetDoc = docs.find((d) => d.id === documentId);

  useEffect(() => {
    abortRef.current?.abort();
    setLoaded(false);
    setMessages([]);
    setInput('');
    setStreaming(false);
    setDocs([]);
    setDocumentId(null);
    setPendingFiles([]);
    setPendingDocs([]);
    setReplyTo(null);
  }, [projectId]);

  useEffect(() => {
    if (!active || !projectId) return;
    getRequirements(projectId)
      .then((rows) => {
        setDocs(rows || []);
        setDocumentId((prev) => prev || rows?.[0]?.id || null);
      })
      .catch(() => {});
  }, [active, projectId]);

  useEffect(() => {
    if (!active || loaded || !projectId) return;
    (async () => {
      setLoading(true);
      try {
        const rows = await getAgentMessages(projectId);
        setMessages(rows.map((r) => ({
          id: r.id,
          role: r.role,
          content: r.content,
          toolCalls: (r.tool_calls || []).map((t) => t.name),
          attachments: r.attachments || [],
          documentId: r.document_id,
          pendingInsightIds: r.pending_insight_ids || [],
          replyToId: r.reply_to_id || null,
          replyTo: r.reply_to || null,
        })));
        setLoaded(true);
      } finally {
        setLoading(false);
      }
    })();
  }, [active, loaded, projectId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  useEffect(() => {
    onMetaChange?.({ hasMessages: messages.length > 0, streaming });
  }, [messages.length, streaming]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => abortRef.current?.abort(), []);

  const patchLast = (patch) => {
    setMessages((prev) => {
      const next = [...prev];
      next[next.length - 1] = { ...next[next.length - 1], ...(
        typeof patch === 'function' ? patch(next[next.length - 1]) : patch
      ) };
      return next;
    });
  };

  const patchUserMessage = (patch) => {
    setMessages((prev) => {
      const next = [...prev];
      // 倒数第二条通常是刚发出的 user 消息
      const idx = next.length >= 2 ? next.length - 2 : -1;
      if (idx < 0 || next[idx]?.role !== 'user') return prev;
      next[idx] = { ...next[idx], ...(typeof patch === 'function' ? patch(next[idx]) : patch) };
      return next;
    });
  };

  const addFiles = (files) => {
    const images = files.filter((f) => IMAGE_TYPES.includes(f.type));
    const docFiles = files.filter((f) => DOC_EXT_RE.test(f.name || ''));
    if (!images.length && !docFiles.length) {
      if (files.length) message.warning('支持 PNG/JPG/WebP 截图，或 .docx/.md 需求文档');
      return;
    }
    if (images.length) setPendingFiles((prev) => [...prev, ...images].slice(0, MAX_ATTACHMENTS));
    if (docFiles.length) setPendingDocs((prev) => [...prev, ...docFiles].slice(0, MAX_DOC_UPLOADS));
  };

  const prepareAttachments = async (targetDocId) => {
    if (!hasAttachments) return [];
    if (!targetDocId) {
      throw new Error(docs.length ? '请先选择目标需求' : '当前项目还没有需求文档，请先导入需求');
    }
    const created = [];
    for (const file of pendingFiles) {
      const asset = await uploadDesignAsset(projectId, targetDocId, file);
      created.push({
        asset_id: asset.id,
        asset_type: asset.asset_type,
        title: asset.title || '',
        filename: asset.filename || file.name,
        figma_url: '',
      });
    }
    for (const url of figmaUrls) {
      const asset = await addFigmaDesign(projectId, {
        document_id: targetDocId,
        url,
        title: 'Figma 设计稿',
      });
      created.push({
        asset_id: asset.id,
        asset_type: asset.asset_type,
        title: asset.title || '',
        filename: '',
        figma_url: asset.figma_url || url,
      });
    }
    return created;
  };

  const send = async () => {
    const question = input.trim();
    if ((!question && !hasAttachments && !hasPendingDocs) || streaming || !projectId) return;

    setUploading(true);
    let attachments = [];
    const importedDocs = [];
    let targetDocId = documentId;
    try {
      // 先导入需求文档：新导入的文档自动成为默认合并目标
      for (const file of pendingDocs) {
        const doc = await uploadRequirementFile(projectId, file);
        importedDocs.push(doc);
      }
      if (importedDocs.length) {
        const latest = importedDocs[importedDocs.length - 1];
        targetDocId = latest.id;
        setDocs((prev) => [...[...importedDocs].reverse(), ...prev]);
        setDocumentId(latest.id);
      }
      attachments = await prepareAttachments(targetDocId);
    } catch (err) {
      message.error(err.response?.data?.detail || err.message || '上传失败');
      setUploading(false);
      return;
    }
    setUploading(false);

    const docNote = importedDocs.length
      ? `我上传了需求文档${importedDocs.map((d) => `《${d.title || `需求 #${d.id}`}》`).join('、')}，已导入并设为默认合并目标。`
      : '';
    let finalQuestion = question || (attachments.length ? DEFAULT_PARSE_QUESTION : '');
    if (docNote) {
      finalQuestion = finalQuestion
        ? `${docNote}\n${finalQuestion}`
        : `${docNote}请确认导入结果，并告诉我下一步可以做什么。`;
    }
    const currentReply = replyTo;
    setInput('');
    setPendingFiles([]);
    setPendingDocs([]);
    setReplyTo(null);
    setStreaming(true);
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content: finalQuestion,
        attachments,
        documentId: targetDocId,
        replyToId: currentReply?.id || null,
        replyTo: currentReply ? {
          id: currentReply.id,
          role: currentReply.role,
          content: currentReply.content,
        } : null,
      },
      {
        role: 'assistant',
        content: '',
        toolCalls: [],
        streaming: true,
        activity: '思考中…',
        documentId: targetDocId,
      },
    ]);

    const handle = streamAgentChat(
      projectId,
      {
        question: finalQuestion,
        document_id: targetDocId || undefined,
        asset_ids: attachments.map((a) => a.asset_id),
        attachments,
        reply_to_id: currentReply?.id || undefined,
      },
      (event) => {
        if (event.type === 'user_message') {
          patchUserMessage({ id: event.id });
        } else if (event.type === 'tool_start') {
          patchLast((m) => ({
            activity: `正在${toolLabel(event.name)}…`,
            toolCalls: [...(m.toolCalls || []), event.name],
          }));
        } else if (event.type === 'tool_end') {
          patchLast({ activity: '思考中…' });
        } else if (event.type === 'token') {
          patchLast((m) => ({ content: (m.content || '') + event.content }));
        } else if (event.type === 'done') {
          patchLast({
            id: event.id,
            streaming: false,
            activity: '',
            pendingInsightIds: event.pending_insight_ids || [],
            documentId: targetDocId || undefined,
          });
          if (event.user_message_id) {
            patchUserMessage({ id: event.user_message_id });
          }
        } else if (event.type === 'error') {
          patchLast({ streaming: false, activity: '', error: event.message });
        }
      },
    );
    abortRef.current = handle;
    try {
      await handle.promise;
    } catch (err) {
      if (err.name !== 'AbortError') {
        patchLast({ streaming: false, activity: '', error: err.message || '请求失败，请稍后重试' });
      }
    } finally {
      setStreaming(false);
      patchLast((m) => (m.streaming ? { streaming: false, activity: '' } : {}));
    }
  };

  const clear = () => {
    modal.confirm({
      title: '清空对话记录？',
      content: '将删除该项目下测试助手的全部历史对话，不影响其他数据。',
      okText: '清空',
      okButtonProps: { danger: true },
      onOk: async () => {
        await clearAgentMessages(projectId);
        setMessages([]);
        setReplyTo(null);
        message.success('已清空对话');
      },
    });
  };

  useImperativeHandle(ref, () => ({ clear }));

  const canSend = (!!input.trim() || hasAttachments || hasPendingDocs) && !!projectId;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1, ...style }}>
      <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '16px 16px 8px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : messages.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={(
              <span style={{ fontSize: 13, color: '#888' }}>
                可问用例、覆盖率、测试进度；也可直接粘贴截图或 Figma 链接，
                <br />
                我会解析设计功能点，确认后合并到需求；
                <br />
                还可上传 Word / Markdown 需求文档，导入后自动设为默认合并目标。
              </span>
            )}
            style={{ marginTop: 60 }}
          />
        ) : (
          messages.map((m, i) => (
            <MessageBubble
              key={m.id || `tmp-${i}`}
              msg={m}
              projectId={projectId}
              navigate={navigate}
              canReply={!streaming}
              onReply={(target) => setReplyTo({
                id: target.id,
                role: target.role,
                content: target.content,
              })}
              onMerged={() => setMessages((prev) => {
                const next = [...prev];
                if (next[i]) next[i] = { ...next[i], mergeDone: true, pendingInsightIds: [] };
                return next;
              })}
            />
          ))
        )}
      </div>
      <div style={{ padding: 12, borderTop: '1px solid #f0f0f0' }}>
        {replyTo && (
          <ReplyQuote
            replyTo={replyTo}
            onClear={() => setReplyTo(null)}
          />
        )}
        {(hasAttachments || hasPendingDocs) && (
          <div
            style={{
              marginBottom: 8,
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              color: '#64748b',
            }}
          >
            {pendingDocs.map((f, idx) => (
              <Tag
                key={`doc-${f.name}-${idx}-${f.lastModified}`}
                icon={<FileTextOutlined />}
                color="geekblue"
                closable={!streaming && !uploading}
                onClose={(e) => {
                  e.preventDefault();
                  setPendingDocs((prev) => prev.filter((_, i) => i !== idx));
                }}
              >
                {f.name}
              </Tag>
            ))}
            {pendingFiles.map((f, idx) => (
              <LocalFileThumb
                key={`${f.name}-${idx}-${f.lastModified}`}
                file={f}
                onRemove={() => setPendingFiles((prev) => prev.filter((_, i) => i !== idx))}
              />
            ))}
            {figmaUrls.map((url) => (
              <Tag key={url} color="blue" icon={<LinkOutlined />}>Figma 链接</Tag>
            ))}
            {hasPendingDocs ? (
              <span>{hasAttachments ? '文档导入后设为默认合并目标，截图将解析到新文档' : '将导入为需求文档，并设为默认合并目标'}</span>
            ) : (
              <>
                <span>解析到</span>
                <Dropdown
                  trigger={['click']}
                  disabled={streaming || !docs.length}
                  menu={{
                    selectedKeys: documentId ? [String(documentId)] : [],
                    items: docs.map((d) => ({
                      key: String(d.id),
                      label: d.title || `需求 #${d.id}`,
                    })),
                    onClick: ({ key }) => setDocumentId(Number(key)),
                  }}
                >
                  <a onClick={(e) => e.preventDefault()}>
                    {targetDoc?.title || (docs.length ? '选择需求' : '暂无需求，请先导入')}
                    {docs.length > 1 && <DownOutlined style={{ marginLeft: 4, fontSize: 10 }} />}
                  </a>
                </Dropdown>
              </>
            )}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <Upload
            accept=".png,.jpg,.jpeg,.webp,.docx,.md,.markdown"
            multiple
            showUploadList={false}
            beforeUpload={(file) => {
              addFiles([file]);
              return false;
            }}
            disabled={streaming || !projectId}
          >
            <Button
              type="text"
              icon={<PaperClipOutlined />}
              disabled={streaming || !projectId}
              title="添加设计稿截图或需求文档（Word/Markdown）"
            />
          </Upload>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPaste={(e) => {
              const files = [...(e.clipboardData?.files || [])];
              if (files.length) {
                e.preventDefault();
                addFiles(files);
              }
            }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={replyTo ? '回复这条消息…（Enter 发送）' : '提问、粘贴截图 / Figma 链接，或上传需求文档…（Enter 发送）'}
            autoSize={{ minRows: 1, maxRows: 4 }}
            maxLength={2000}
            disabled={streaming || uploading || !projectId}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={send}
            loading={streaming || uploading}
            disabled={!canSend}
          />
        </div>
      </div>
    </div>
  );
});

export default AgentChat;
