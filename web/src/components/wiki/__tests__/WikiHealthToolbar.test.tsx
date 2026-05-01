import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WikiHealthToolbar } from "../WikiHealthToolbar";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock useWikiLint
const mockRunLint = vi.fn();
const mockLintClear = vi.fn();
const mockLintState = {
  report: null as null | { findings: { severity: string; page_id: string; section_id?: string; message: string; suggested_action?: string; category: string }[]; pages_scanned: number; channel_id: string; target_lang: string; generated_at: string },
  loading: false,
  error: null as string | null,
  runLint: mockRunLint,
  clear: mockLintClear,
};

vi.mock("@/hooks/useWikiLint", () => ({
  useWikiLint: () => mockLintState,
}));

// Mock useWikiMaintain
const mockMaintain = vi.fn();
const mockMaintainState = {
  result: null as null | { rewritten: number; errors: number },
  loading: false,
  error: null as string | null,
  maintain: mockMaintain,
};

vi.mock("@/hooks/useWikiMaintain", () => ({
  useWikiMaintain: () => mockMaintainState,
}));

// Mock FailedBatchPanel to avoid fetch in tests
vi.mock("../FailedBatchPanel", () => ({
  FailedBatchPanel: ({ onClose }: { channelId: string; onClose?: () => void }) => (
    <div data-testid="failed-batch-panel">
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

// Tooltip provider is not needed since TooltipTrigger renders children directly
// Mock the tooltip components for simplicity
vi.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  // TooltipTrigger forwards all props to a <button> so tests can find it by role/label
  TooltipTrigger: ({
    children,
    className,
    onClick,
    disabled,
    "aria-label": ariaLabel,
    ...rest
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children?: React.ReactNode }) => (
    <button
      type="button"
      aria-label={ariaLabel}
      className={className}
      onClick={onClick}
      disabled={disabled}
      {...rest}
    >
      {children}
    </button>
  ),
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content" hidden>{children}</div>
  ),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderToolbar(props: Partial<{ manualMode: boolean }> = {}) {
  return render(<WikiHealthToolbar channelId="ch-1" manualMode={props.manualMode ?? true} />);
}

beforeEach(() => {
  mockLintState.report = null;
  mockLintState.loading = false;
  mockLintState.error = null;
  mockMaintainState.result = null;
  mockMaintainState.loading = false;
  mockMaintainState.error = null;
  mockRunLint.mockResolvedValue(undefined);
  mockMaintain.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WikiHealthToolbar", () => {
  it("renders Lint Wiki and Maintain Wiki buttons", () => {
    renderToolbar();
    expect(screen.getByRole("button", { name: /lint wiki/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /maintain wiki/i })).toBeInTheDocument();
  });

  it("has aria-label on Maintain Wiki button", () => {
    renderToolbar();
    const btn = screen.getByRole("button", { name: /maintain wiki/i });
    expect(btn).toHaveAttribute("aria-label");
  });

  it("has aria-label on Lint Wiki button", () => {
    renderToolbar();
    const btn = screen.getByRole("button", { name: /lint wiki/i });
    expect(btn).toHaveAttribute("aria-label");
  });

  it("shows loading skeleton during lint scan with role=status and aria-live", async () => {
    // First open the panel with loading=false so we can click the button,
    // then simulate a second lint run that shows the loading state.
    mockLintState.loading = false;
    mockLintState.report = {
      findings: [],
      pages_scanned: 4,
      channel_id: "ch-1",
      target_lang: "en",
      generated_at: new Date().toISOString(),
    };

    const { rerender } = renderToolbar();
    const user = userEvent.setup();

    // Click lint — panel opens
    await user.click(screen.getByRole("button", { name: /lint wiki/i }));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    // Now simulate lint running again (e.g. a retry) — flip loading=true
    mockLintState.loading = true;
    rerender(<WikiHealthToolbar channelId="ch-1" manualMode={true} />);

    // The loading skeleton should now be visible inside the open panel
    const status = screen.getByRole("status");
    expect(status).toBeInTheDocument();
    expect(status).toHaveAttribute("aria-live", "polite");
  });

  it("shows retry button on lint error", async () => {
    mockLintState.error = "Network error";
    mockLintState.loading = false;

    renderToolbar();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /lint wiki/i }));

    expect(screen.getByRole("button", { name: /retry lint/i })).toBeInTheDocument();
  });

  it("retry button calls runLint again", async () => {
    mockLintState.error = "Network error";
    mockLintState.loading = false;

    renderToolbar();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /lint wiki/i }));
    await user.click(screen.getByRole("button", { name: /retry lint/i }));

    expect(mockRunLint).toHaveBeenCalledTimes(2);
  });

  it("opens findings panel with role=dialog after lint completes", async () => {
    mockRunLint.mockImplementation(() => {
      mockLintState.report = {
        findings: [],
        pages_scanned: 3,
        channel_id: "ch-1",
        target_lang: "en",
        generated_at: new Date().toISOString(),
      };
      return Promise.resolve();
    });

    renderToolbar();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /lint wiki/i }));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Lint findings");
  });

  it("shows no-issues message when findings is empty", async () => {
    mockLintState.report = {
      findings: [],
      pages_scanned: 2,
      channel_id: "ch-1",
      target_lang: "en",
      generated_at: new Date().toISOString(),
    };

    renderToolbar();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /lint wiki/i }));

    await waitFor(() => {
      expect(screen.getByText(/no issues/i)).toBeInTheDocument();
    });
  });

  it("shows maintain error with retry button", async () => {
    mockMaintainState.error = "Maintain failed";
    renderToolbar();

    expect(screen.getByText("Maintain failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry maintain/i })).toBeInTheDocument();
  });

  it("hides Maintain Wiki button when manualMode=false", () => {
    renderToolbar({ manualMode: false });
    expect(screen.queryByRole("button", { name: /maintain wiki/i })).not.toBeInTheDocument();
  });

  it("opens FailedBatchPanel when Failures button is clicked", async () => {
    renderToolbar();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /view failed extractions/i }));

    await waitFor(() => {
      expect(screen.getByTestId("failed-batch-panel")).toBeInTheDocument();
    });
  });
});
