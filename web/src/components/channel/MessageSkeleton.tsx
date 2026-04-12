export function MessageSkeleton() {
  return (
    <div className="flex gap-3 animate-pulse">
      <div className="w-8 h-8 rounded-full bg-muted shrink-0" />
      <div className="flex-1 space-y-3 max-w-[70%]">
        <div className="h-3 bg-muted rounded w-24" />
        <div className="space-y-2">
          <div className="h-3 bg-muted rounded w-full" />
          <div className="h-3 bg-muted rounded w-5/6" />
          <div className="h-3 bg-muted rounded w-4/6" />
        </div>
      </div>
    </div>
  );
}
