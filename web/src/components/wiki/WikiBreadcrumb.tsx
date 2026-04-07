import type { WikiPage } from "@/lib/types";

interface WikiBreadcrumbProps {
  page: WikiPage;
}

export function WikiBreadcrumb({ page }: WikiBreadcrumbProps) {
  const crumbs = ["Wiki"];
  if (page.page_type === "topic" || page.page_type === "sub-topic") crumbs.push("Topics");
  crumbs.push(page.title);

  return (
    <nav className="flex items-center gap-1 text-sm text-muted-foreground mb-4">
      {crumbs.map((crumb, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <span className="text-muted-foreground/50">/</span>}
          <span className={i === crumbs.length - 1 ? "text-foreground font-medium" : ""}>{crumb}</span>
        </span>
      ))}
    </nav>
  );
}
