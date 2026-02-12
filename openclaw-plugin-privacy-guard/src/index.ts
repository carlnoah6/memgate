import * as fs from 'fs';
import * as path from 'path';

// --- OpenClaw Plugin Interfaces (Hypothetical SDK) ---

export interface PluginContext {
  workspaceDir: string;
  config: any;
  logger: {
    info: (msg: string) => void;
    warn: (msg: string) => void;
    error: (msg: string) => void;
  };
}

export interface SessionContext {
  sessionId: string;
  channelType: 'dm' | 'group';
  participants: string[];
  userId: string; // The primary user in DM, or sender in group
}

export interface Message {
  content: string;
  role: 'user' | 'assistant' | 'system';
}

export interface SearchResult {
  path: string;
  content: string;
  score?: number;
}

// --- Privacy Guard Plugin Implementation ---

export interface PrivacyGuardConfig {
  knowledgePath: string; // Path to knowledge base (JSONL files)
  patterns?: Record<string, { description: string; patterns: string[] }>;
  enabled?: boolean;
  blockOnViolation?: boolean;
}

export class PrivacyGuardPlugin {
  private config: PrivacyGuardConfig;
  private defaultPatterns: any;

  constructor(config: PrivacyGuardConfig) {
    this.config = {
      enabled: true,
      blockOnViolation: true,
      ...config
    };
    this.defaultPatterns = this.loadDefaultPatterns();
  }

  /**
   * Hook: On Session Start
   * Inject privacy context summary into the system prompt.
   */
  public onSessionStart(context: SessionContext): string {
    if (!this.config.enabled) return '';

    if (context.channelType === 'dm') {
      return `[Privacy System] Private Chat Mode (User: ${context.participants[0]}). You have full access to this user's private and public knowledge.`;
    } else {
      const users = context.participants.join(', ');
      return `[Privacy System] Group Chat Mode (Participants: ${users}). You may ONLY access PUBLIC knowledge. DO NOT reveal private information (calendar, finance, home address, etc.) for any participant.`;
    }
  }

  /**
   * Hook: On Tool Result (Memory Search)
   * Filter search results based on current context visibility.
   */
  public onMemorySearch(context: SessionContext, results: SearchResult[]): SearchResult[] {
    if (!this.config.enabled) return results;

    const accessiblePaths = this.getAccessiblePaths(context);
    
    return results.filter(result => {
      // Check if result path is in accessible paths
      // Logic assumes result.path contains user identifier or specific structure
      // For this generic plugin, we check if the file path implies privacy
      return this.isPathAccessible(result.path, accessiblePaths);
    });
  }

  /**
   * Hook: On Agent Output
   * Review the generated message for privacy violations before sending.
   */
  public async onOutput(context: SessionContext, message: string): Promise<{ passed: boolean; violation?: string; filteredMessage?: string }> {
    if (!this.config.enabled) return { passed: true };
    if (context.channelType === 'dm') return { passed: true }; // No review needed for DM itself (usually) - *Policy decision*

    // 1. Regex Pattern Check
    const patternViolation = this.checkPatterns(message);
    if (patternViolation) {
      return { 
        passed: false, 
        violation: `Detected private info category: ${patternViolation}` 
      };
    }

    // 2. Private Entity Check (Knowledge Base)
    // In a real implementation, this would load the user's private entities
    // and check if they appear in the text.
    // const entityViolation = this.checkEntities(message, context.participants);
    
    return { passed: true };
  }

  // --- Internal Helpers ---

  private loadDefaultPatterns() {
    return {
      calendar: {
        patterns: [
          /schedule|appointment|meeting at/i,
          /\d{1,2}[:.]\d{2}.*(meeting|call)/i
        ]
      },
      contact: {
        patterns: [
          /\d{3}-\d{3}-\d{4}/, // Simple phone
          /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/ // Email
        ]
      },
      finance: {
        patterns: [
          /salary|income|balance|credit card/i,
          /\$\d+/
        ]
      }
    };
  }

  private checkPatterns(text: string): string | null {
    const patterns = { ...this.defaultPatterns, ...(this.config.patterns || {}) };
    
    for (const [category, data] of Object.entries(patterns)) {
      // @ts-ignore
      for (const pattern of data.patterns) {
        if (new RegExp(pattern).test(text)) {
          return category;
        }
      }
    }
    return null;
  }

  private getAccessiblePaths(context: SessionContext): Set<string> {
    const paths = new Set<string>();
    const baseDir = this.config.knowledgePath;

    // Logic to determine allowed files based on context
    // This mirrors the Python logic:
    // DM -> user/public.jsonl + user/private.jsonl
    // Group -> user/public.jsonl only (for all participants)

    if (context.channelType === 'dm') {
       const user = context.participants[0];
       paths.add(path.join(baseDir, user, 'public.jsonl'));
       paths.add(path.join(baseDir, user, 'private.jsonl'));
    } else {
      for (const user of context.participants) {
        paths.add(path.join(baseDir, user, 'public.jsonl'));
      }
    }
    return paths;
  }

  private isPathAccessible(filePath: string, allowedPaths: Set<string>): boolean {
    // Exact match or subdirectory match could be implemented here
    // For now, strict exact match on expected knowledge files
    // In production, might check "startsWith" for directories
    for (const allowed of allowedPaths) {
      if (filePath.includes(allowed)) return true; // Loose check for demo
    }
    return false;
  }
}
