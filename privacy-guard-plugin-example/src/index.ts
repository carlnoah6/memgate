/**
 * Privacy Guard Plugin for OpenClaw
 * 
 * This plugin provides multi-user privacy isolation for OpenClaw agents.
 * It ensures that private information is not leaked in group chats.
 */

import type { AgentPlugin } from 'openclaw/plugin-sdk';
import type { PrivacyGuardConfig } from './types';
import { PrivacyContext } from './privacy-context';
import { PrivacyReviewer } from './privacy-reviewer';
import { KnowledgeStore } from './knowledge-store';

export class PrivacyGuardPlugin {
  private config: PrivacyGuardConfig;
  private knowledgeStore: KnowledgeStore;
  private contexts: Map<string, PrivacyContext> = new Map();
  private reviewers: Map<string, PrivacyReviewer> = new Map();

  constructor(config: PrivacyGuardConfig) {
    this.config = config;
    this.knowledgeStore = new KnowledgeStore(config.knowledgeBase.path);
  }

  /**
   * Initialize privacy context for a session
   */
  initializeSession(sessionId: string, channelInfo: {
    channelId: string;
    participants: string[];
    channelType: 'dm' | 'group';
  }): void {
    if (!this.config.enabled) {
      return;
    }

    const context = new PrivacyContext(
      {
        channelId: channelInfo.channelId,
        participants: new Set(channelInfo.participants),
        channelType: channelInfo.channelType
      },
      this.knowledgeStore
    );

    this.contexts.set(sessionId, context);
    
    // Create reviewer for this channel if needed
    if (this.config.review.enabled) {
      const reviewer = new PrivacyReviewer(this.config);
      this.reviewers.set(channelInfo.channelId, reviewer);
    }
  }

  /**
   * Get privacy context for a session
   */
  getContext(sessionId: string): PrivacyContext | undefined {
    return this.contexts.get(sessionId);
  }

  /**
   * Review a message before sending
   */
  reviewMessage(
    channelId: string,
    message: string,
    participants: string[],
    sender?: string
  ): ReviewResult {
    const reviewer = this.reviewers.get(channelId);
    if (!reviewer || !this.config.review.enabled) {
      return { passed: true, violations: [] };
    }

    return reviewer.review(
      message,
      channelId,
      new Set(participants),
      sender
    );
  }

  /**
   * Filter memory search results
   */
  filterMemoryResults(sessionId: string, results: any[]): any[] {
    const context = this.contexts.get(sessionId);
    if (!context) {
      return results;
    }

    return context.filterMemoryResults(results);
  }

  /**
   * Get plugin status
   */
  getStatus() {
    return {
      enabled: this.config.enabled,
      activeSessions: this.contexts.size,
      activeReviewers: this.reviewers.size,
      knowledgeUsers: this.knowledgeStore.listUsers().length,
      config: {
        reviewEnabled: this.config.review.enabled,
        blockOnViolation: this.config.review.blockOnViolation
      }
    };
  }
}

// Plugin export for OpenClaw
export const privacyGuardPlugin: AgentPlugin<PrivacyGuardConfig> = {
  id: 'privacy-guard',
  name: 'Privacy Guard',
  description: 'Multi-user privacy isolation framework',
  
  initialize(config: PrivacyGuardConfig) {
    return new PrivacyGuardPlugin(config);
  },

  hooks: {
    // Session initialization hook
    sessionInit: (plugin: PrivacyGuardPlugin, session: any) => {
      // Extract channel info from session
      const channelInfo = {
        channelId: session.channelId,
        participants: session.participants || [],
        channelType: session.channelType || 'dm'
      };
      
      plugin.initializeSession(session.id, channelInfo);
      
      // Inject privacy context into session
      const context = plugin.getContext(session.id);
      if (context) {
        session.privacyContext = context.getContextSummary();
      }
    },

    // Message pre-send hook
    messagePreSend: (plugin: PrivacyGuardPlugin, message: any) => {
      const result = plugin.reviewMessage(
        message.channelId,
        message.content,
        message.participants || [],
        message.sender
      );

      if (!result.passed && plugin.config.review.blockOnViolation) {
        throw new Error(`Privacy violation: ${result.violations.map(v => v.description).join(', ')}`);
      }

      return result;
    },

    // Memory search filter hook
    memorySearchFilter: (plugin: PrivacyGuardPlugin, sessionId: string, results: any[]) => {
      return plugin.filterMemoryResults(sessionId, results);
    }
  }
};

export default privacyGuardPlugin;