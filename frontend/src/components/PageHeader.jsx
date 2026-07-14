export default function PageHeader({ title, description, extra }) {
  return (
    <div className="page-header">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">{title}</h1>
          {description && <p className="page-desc">{description}</p>}
        </div>
        {extra && <div>{extra}</div>}
      </div>
    </div>
  );
}
