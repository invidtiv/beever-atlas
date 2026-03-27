import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full p-6">
      <h2 className="text-2xl font-semibold text-slate-900 mb-2">404</h2>
      <p className="text-slate-500 mb-4">Page not found</p>
      <Link to="/" className="text-indigo-600 hover:text-indigo-800 text-sm">
        Back to Dashboard
      </Link>
    </div>
  );
}
