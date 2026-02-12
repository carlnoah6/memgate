/**
 * Privacy Guard Plugin Types
 */

export interface ChannelInfo {
  channelId: string;
  participants: Set<string>;
  channelType: 'dm' | 'group';
}

export interface KnowledgeItem {
  id: string;
  user: string;
  content: string;
  visibility: 'public' | 'private';
  category: string;
  source: string;
  created: string;
}

export interface Violation {
  category: string;
  matched: string;
  description: string;
}

export interface ReviewResult {
  passed: boolean;
  message?: string;
  violations: Violation[];
  suggestion?: string;
}

export interface PrivacyGuardConfig {
  enabled: boolean;
  review: {
    enabled: boolean;
    blockOnViolation: boolean;
    llmSelfReview: boolean;
  };
  defaults: {
    visibility: 'public' | 'private';
    alwaysPrivateCategories: string[];
  };
  knowledgeBase: {
    path: string;
    autoSync: boolean;
    syncInterval?: number;
  };
  channels: {
    autoDetect: boolean;
    manualMapping?: Record<string, string[]>;
  };
}

export interface PrivacyContext {
  getAccessibleKnowledge(): KnowledgeItem[];
  canAccessItem(item: KnowledgeItem): boolean;
  getAccessiblePaths(): Set<string>;
  filterMemoryResults(results: any[]): any[];
  getContextSummary(): string;
}

export interface PrivacyReviewer {
  review(
    message: string,
    channelId: string,
    participants: Set<string>,
    sender?: string
  ): ReviewResult;
  getStatus(): {
    enabled: boolean;
    blockOnViolation: boolean;
    patternCategories: string[];
  };
}

export interface KnowledgeStore {
  getPublic(user: string): KnowledgeItem[];
  getPrivate(user: string): KnowledgeItem[];
  getAll(user: string): KnowledgeItem[];
  listUsers(): string[];
  addItem(item: KnowledgeItem): void;
  updateItem(itemId: string, updates: Partial<KnowledgeItem>): void;
  deleteItem(itemId: string): void;
}