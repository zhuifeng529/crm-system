import { Typography } from "antd";

interface Props {
  title: string;
  description?: string;
}

export function PlaceholderPage({ title, description }: Props) {
  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        {title}
      </Typography.Title>
      <Typography.Paragraph type="secondary">
        {description || "业务功能页面占位，本需求交付重点为「系统使用说明书」入口与展示。"}
      </Typography.Paragraph>
    </div>
  );
}
