import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConnectionWizard } from "../ConnectionWizard";

const createMock = vi.fn();

vi.mock("@/hooks/useConnections", () => ({
  useCreateConnection: () => ({ create: createMock }),
  useConnectionChannels: () => ({ channels: [], loading: false }),
  useUpdateChannels: () => ({ updateChannels: vi.fn(), loading: false }),
}));

describe("ConnectionWizard Telegram ingestion mode", () => {
  it("lets Telegram choose webhook mode and submits it with credentials", async () => {
    const user = userEvent.setup();
    createMock.mockResolvedValue({
      id: "conn-telegram",
      platform: "telegram",
      display_name: "Atlas Bot",
      status: "connected",
      error_message: null,
      selected_channels: [],
      source: "ui",
      ingestion_mode: "webhook",
      created_at: "2026-04-29T00:00:00Z",
      updated_at: "2026-04-29T00:00:00Z",
    });

    render(
      <ConnectionWizard
        platform="telegram"
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText(/display name/i), "Atlas Bot");
    await user.click(screen.getByRole("button", { name: /next/i }));

    expect(screen.getByRole("button", { name: /polling/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /webhook/i }));
    await user.type(screen.getByLabelText(/bot token/i), "123:abc");
    await user.click(screen.getByRole("button", { name: /validate/i }));

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith({
        platform: "telegram",
        credentials: { bot_token: "123:abc" },
        display_name: "Atlas Bot",
        ingestion_mode: "webhook",
      });
    });
  });
});
