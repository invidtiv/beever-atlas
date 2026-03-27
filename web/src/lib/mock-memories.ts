import type { MemoryTier0, MemoryTier1, MemoryTier2 } from "./types";

export const mockSummary: MemoryTier0 = {
  channel_id: "backend-engineering",
  channel_name: "#backend-engineering",
  summary:
    "Backend engineering channel focused on authentication architecture, API design patterns, and infrastructure decisions. Key contributors: Alice Chen, Bob Martinez, Carol Wang. Active discussions on JWT implementation, database migration strategy, and CI/CD pipeline improvements.",
  updated_at: "2026-03-25T14:30:00Z",
  message_count: 1247,
};

export const mockClusters: MemoryTier1[] = [
  {
    id: "cluster-auth",
    topic: "Authentication & Authorization",
    summary:
      "Decisions around JWT implementation, RS256 vs HS256, token refresh strategy, and OAuth2 integration with external providers.",
    fact_count: 12,
    date_range: { start: "2026-02-15T00:00:00Z", end: "2026-03-20T00:00:00Z" },
    topic_tags: ["authentication", "security", "jwt"],
  },
  {
    id: "cluster-db",
    topic: "Database Migration Strategy",
    summary:
      "Planning and execution of PostgreSQL to MongoDB migration for session storage, schema design discussions, and data migration tooling.",
    fact_count: 8,
    date_range: { start: "2026-03-01T00:00:00Z", end: "2026-03-18T00:00:00Z" },
    topic_tags: ["database", "migration", "mongodb"],
  },
  {
    id: "cluster-cicd",
    topic: "CI/CD Pipeline",
    summary:
      "GitHub Actions workflow improvements, Docker build optimization, staging environment setup, and deployment automation.",
    fact_count: 6,
    date_range: { start: "2026-03-10T00:00:00Z", end: "2026-03-24T00:00:00Z" },
    topic_tags: ["ci-cd", "devops", "docker"],
  },
];

export const mockFacts: MemoryTier2[] = [
  {
    id: "fact-1",
    memory:
      "Alice decided to use RS256 for JWT signing instead of HS256 because it allows public key verification without sharing the secret.",
    quality_score: 8.5,
    timestamp: "2026-03-15T10:30:00Z",
    user_name: "Alice Chen",
    topic_tags: ["authentication", "jwt"],
    entity_tags: ["Alice Chen", "RS256", "JWT"],
    importance: "high",
    permalink: "https://slack.com/archives/C01/p1710498600",
    cluster_id: "cluster-auth",
  },
  {
    id: "fact-2",
    memory:
      "Token refresh strategy: use rotating refresh tokens with 7-day expiry. Access tokens expire in 15 minutes.",
    quality_score: 7.2,
    timestamp: "2026-03-16T14:15:00Z",
    user_name: "Bob Martinez",
    topic_tags: ["authentication", "jwt"],
    entity_tags: ["Bob Martinez"],
    importance: "high",
    permalink: "https://slack.com/archives/C01/p1710597300",
    cluster_id: "cluster-auth",
  },
  {
    id: "fact-3",
    memory:
      "Carol's security review blocked the RS256 decision — wants to validate key rotation strategy before approval.",
    quality_score: 6.8,
    timestamp: "2026-03-17T09:00:00Z",
    user_name: "Carol Wang",
    topic_tags: ["authentication", "security"],
    entity_tags: ["Carol Wang", "RS256"],
    importance: "medium",
    permalink: "https://slack.com/archives/C01/p1710658800",
    cluster_id: "cluster-auth",
  },
  {
    id: "fact-4",
    memory:
      "MongoDB selected for session storage over Redis due to need for complex session metadata queries. Redis kept for cache layer.",
    quality_score: 7.8,
    timestamp: "2026-03-12T11:00:00Z",
    user_name: "Alice Chen",
    topic_tags: ["database", "migration"],
    entity_tags: ["Alice Chen", "MongoDB", "Redis"],
    importance: "high",
    permalink: "https://slack.com/archives/C01/p1710234000",
    cluster_id: "cluster-db",
  },
  {
    id: "fact-5",
    memory:
      "GitHub Actions parallel build reduced CI time from 12 min to 4 min by splitting test and lint jobs.",
    quality_score: 5.5,
    timestamp: "2026-03-20T16:45:00Z",
    user_name: "Bob Martinez",
    topic_tags: ["ci-cd", "devops"],
    entity_tags: ["Bob Martinez", "GitHub Actions"],
    importance: "low",
    permalink: "https://slack.com/archives/C01/p1710953100",
    cluster_id: "cluster-cicd",
  },
  {
    id: "fact-6",
    memory:
      "OAuth2 PKCE flow chosen for mobile clients — implicit flow deprecated per security best practices.",
    quality_score: 9.0,
    timestamp: "2026-03-18T13:20:00Z",
    user_name: "Alice Chen",
    topic_tags: ["authentication", "security"],
    entity_tags: ["Alice Chen", "OAuth2"],
    importance: "critical",
    permalink: "https://slack.com/archives/C01/p1710760800",
    cluster_id: "cluster-auth",
  },
];
