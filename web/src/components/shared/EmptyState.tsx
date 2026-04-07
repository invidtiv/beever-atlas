import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

interface EmptyStateAction {
  label: string;
  href?: string;
  onClick?: () => void;
}

interface EmptyStateProps {
  icon: React.ComponentType<{ className?: string; size?: number }>;
  title: string;
  description: string;
  action?: EmptyStateAction;
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-card p-10 flex flex-col items-center gap-3 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
        <Icon size={22} className="text-muted-foreground/40" />
      </div>
      <div>
        <p className="text-sm font-medium text-foreground/70">{title}</p>
        <p className="text-xs text-muted-foreground mt-1 max-w-xs mx-auto leading-relaxed">
          {description}
        </p>
      </div>
      {action && (
        <div className="mt-1">
          {action.href ? (
            <Link
              to={action.href}
              className={cn(
                "inline-flex items-center justify-center px-4 py-2 text-sm font-medium",
                "rounded-full border border-border bg-background hover:bg-muted transition-colors"
              )}
            >
              {action.label}
            </Link>
          ) : (
            <button
              type="button"
              onClick={action.onClick}
              className={cn(
                "inline-flex items-center justify-center px-4 py-2 text-sm font-medium",
                "rounded-full border border-border bg-background hover:bg-muted transition-colors"
              )}
            >
              {action.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
