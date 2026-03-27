import Redis from "ioredis";

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";

async function main(): Promise<void> {
  console.log(`Connecting to Redis at ${REDIS_URL}...`);

  const redis = new Redis(REDIS_URL, {
    maxRetriesPerRequest: 3,
    retryStrategy(times: number): number | null {
      if (times > 3) {
        console.error("Redis connection failed after 3 retries. Exiting.");
        process.exit(1);
      }
      return Math.min(times * 500, 2000);
    },
  });

  redis.on("connect", () => {
    console.log("Bot service ready");
  });

  redis.on("error", (err: Error) => {
    console.error("Redis error:", err.message);
  });

  // Verify connection
  try {
    await redis.ping();
  } catch (err) {
    console.error("Failed to connect to Redis:", err);
    process.exit(1);
  }

  // Keep process alive
  process.on("SIGINT", async () => {
    console.log("Shutting down bot service...");
    await redis.quit();
    process.exit(0);
  });

  process.on("SIGTERM", async () => {
    console.log("Shutting down bot service...");
    await redis.quit();
    process.exit(0);
  });
}

main().catch((err: unknown) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
