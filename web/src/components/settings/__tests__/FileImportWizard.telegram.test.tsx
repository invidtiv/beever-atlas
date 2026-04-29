import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FileImportWizard } from "../FileImportWizard";

const previewMock = vi.fn();

vi.mock("@/hooks/useFileImport", () => ({
  useFileImport: () => ({
    preview: previewMock,
    commit: vi.fn(),
    previewing: false,
    committing: false,
    error: null,
  }),
}));

describe("FileImportWizard Telegram JSON", () => {
  it("accepts .json uploads for Telegram Desktop exports", async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue({
      file_id: "file-1",
      filename: "result.json",
      encoding: "utf-8",
      format: "json",
      row_count_estimate: 1,
      headers: ["_telegram_content"],
      sample_messages: [],
      mapping: { content: "_telegram_content" },
      mapping_source: "preset",
      preset: "telegram_desktop_json",
      overall_confidence: 1,
      per_field_confidence: {},
      needs_review: false,
      detected_source: "telegram_export",
      notes: "",
      expires_at: "2026-04-29T00:00:00Z",
    });

    const { container } = render(
      <FileImportWizard onClose={vi.fn()} onComplete={vi.fn()} />,
    );
    const input = container.querySelector('input[type="file"]');
    if (!(input instanceof HTMLInputElement)) {
      throw new Error("file input not found");
    }

    await user.upload(
      input,
      new File(["{}"], "result.json", { type: "application/json" }),
    );

    expect(previewMock).toHaveBeenCalled();
  });
});
