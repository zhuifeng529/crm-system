import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Alert, Button, Drawer, Space, Spin, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fetchUserManual } from "@/api/help";
import { getErrorMessage } from "@/api/client";
import type { ManualTocItem, UserManual } from "@/api/types";

interface Props {
  open: boolean;
  onClose: () => void;
}

function headingText(children: ReactNode): string {
  if (typeof children === "string") return children;
  if (Array.isArray(children)) return children.map(headingText).join("");
  if (children && typeof children === "object" && "props" in (children as object)) {
    return headingText((children as { props?: { children?: ReactNode } }).props?.children);
  }
  return "";
}

function slugify(title: string): string {
  const text = title.trim().toLowerCase().replace(/\s+/g, "-");
  return text.replace(/[^\w\u4e00-\u9fff-]+/g, "") || "section";
}

export function UserManualDrawer({ open, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manual, setManual] = useState<UserManual | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchUserManual();
      setManual(data);
    } catch (err) {
      setManual(null);
      setError(getErrorMessage(err, "说明书加载失败，请稍后重试"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      void load();
    }
  }, [open]);

  const toc = useMemo(() => manual?.toc ?? [], [manual]);

  const scrollToSection = (item: ManualTocItem) => {
    const el = document.getElementById(item.id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const markdownComponents = useMemo(() => {
    const seen: Record<string, number> = {};
    const makeId = (raw: string) => {
      const base = slugify(raw);
      const count = seen[base] ?? 0;
      seen[base] = count + 1;
      return count === 0 ? base : `${base}-${count + 1}`;
    };

    return {
      h1: ({ children }: { children?: ReactNode }) => <h1>{children}</h1>,
      h2: ({ children }: { children?: ReactNode }) => {
        const text = headingText(children);
        return <h2 id={makeId(text)}>{children}</h2>;
      },
      h3: ({ children }: { children?: ReactNode }) => {
        const text = headingText(children);
        return <h3 id={makeId(text)}>{children}</h3>;
      },
      h4: ({ children }: { children?: ReactNode }) => {
        const text = headingText(children);
        return <h4 id={makeId(text)}>{children}</h4>;
      },
    };
  }, [manual?.content]);

  return (
    <Drawer
      className="manual-drawer"
      title={manual?.title || "系统使用说明书"}
      placement="right"
      width={typeof window !== "undefined" ? Math.min(920, window.innerWidth * 0.96) : 920}
      open={open}
      onClose={onClose}
      destroyOnClose
      keyboard
      extra={
        <Space>
          {manual?.version ? (
            <Typography.Text type="secondary">v{manual.version}</Typography.Text>
          ) : null}
          <Button
            icon={<ReloadOutlined />}
            onClick={() => void load()}
            disabled={loading}
            aria-label="重新加载说明书"
          >
            刷新
          </Button>
        </Space>
      }
    >
      {loading && !manual ? (
        <div className="manual-error" style={{ textAlign: "center" }}>
          <Spin tip="正在加载说明书…" />
        </div>
      ) : null}

      {error ? (
        <div className="manual-error">
          <Alert
            type="error"
            showIcon
            message="无法加载系统使用说明书"
            description={error}
            action={
              <Button size="small" onClick={() => void load()}>
                重试
              </Button>
            }
          />
        </div>
      ) : null}

      {!error && manual ? (
        <div className="manual-layout">
          <aside className="manual-toc" aria-label="说明书目录">
            <p className="manual-toc-title">目录</p>
            {toc.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`manual-toc-item level-${item.level}`}
                onClick={() => scrollToSection(item)}
              >
                {item.title}
              </button>
            ))}
          </aside>
          <article className="manual-body manual-markdown" aria-label="说明书正文">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {manual.content}
            </ReactMarkdown>
          </article>
        </div>
      ) : null}
    </Drawer>
  );
}
