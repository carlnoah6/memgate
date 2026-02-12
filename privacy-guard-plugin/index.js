import { z } from 'zod';

/**
 * Privacy Guard Plugin for OpenClaw
 * 
 * Provides multi-user privacy isolation with:
 * 1. Context-based knowledge access control
 * 2. Output review for privacy violations
 * 3. Knowledge tagging (public/private)
 * 4. Memory search filtering
 */

// Plugin configuration schema
const pluginConfigSchema = z.object({
  enabled: z.boolean().default(true),
  review: z.object({
    enabled: z.boolean().default(true),
    llmSelfReview: z.boolean().default(false),
    blockOnViolation: z.boolean().default(true),
  }).default({}),
  knowledgeBase: z.object({
    path: z.string().default('./privacy/knowledge'),
    autoTag: z.boolean().default(true),
  }).default({}),
  defaults: z.object({
    visibility: z.enum(['private', 'public']).default('private'),
    alwaysPrivateCategories: z.array(z.string()).default([
      'calendar', 'family', 'finance', 'health', 
      'auth', 'contact_private', 'dm_content'
    ]),
  }).default({}),
});

// Knowledge item schema
const knowledgeItemSchema = z.object({
  id: z.string(),
  user: z.string(),
  content: z.string(),
  visibility: z.enum(['public', 'private']),
  category: z.string(),
  source: z.string(),
  created: z.string().datetime(),
});

// Privacy context class
class PrivacyContext {
  constructor(channelId, participants, config) {
    this.channelId = channelId;
    this.participants = new Set(participants);
    this.config = config;
    this.isPrivate = this.participants.size <= 1;
  }

  getAccessibleKnowledge(knowledgeStore) {
    if (!this.config.enabled) {
      return knowledgeStore.getAll();
    }

    if (this.isPrivate) {
      const user = Array.from(this.participants)[0];
      return knowledgeStore.getByUser(user);
    } else {
      const result = [];
      for (const user of this.participants) {
        result.push(...knowledgeStore.getPublicByUser(user));
      }
      return result;
    }
  }

  canAccessItem(item) {
    if (!this.config.enabled) return true;
    
    if (this.isPrivate) {
      const user = Array.from(this.participants)[0];
      return item.user === user;
    } else {
      return this.participants.has(item.user) && item.visibility === 'public';
    }
  }

  filterMemoryResults(results) {
    if (!this.config.enabled) return results;
    
    const accessiblePaths = new Set();
    if (this.isPrivate) {
      const user = Array.from(this.participants)[0];
      accessiblePaths.add(`${user}/public.jsonl`);
      accessiblePaths.add(`${user}/private.jsonl`);
    } else {
      for (const user of this.participants) {
        accessiblePaths.add(`${user}/public.jsonl`);
      }
    }
    
    return results.filter(r => accessiblePaths.has(r.path));
  }

  getContextSummary() {
    if (!this.config.enabled) {
      return '[Privacy] Disabled';
    }
    
    if (this.isPrivate) {
      const user = Array.from(this.participants)[0];
      return `[Privacy] Private chat (user: ${user}) - Access to all knowledge`;
    } else {
      const users = Array.from(this.participants).sort().join(', ');
      return `[Privacy] Group chat (participants: ${users}) - Only public knowledge accessible`;
    }
  }
}

// Privacy reviewer class
class PrivacyReviewer {
  constructor(config, knowledgeStore) {
    this.config = config;
    this.knowledgeStore = knowledgeStore;
    this.patterns = this.loadPatterns();
  }

  loadPatterns() {
    return {
      calendar: {
        description: 'Schedule/calendar information',
        patterns: [
          /明天.*[去见约]/,
          /今天.*[去见约]/,
          /昨天.*[去见约]/,
          /\d{1,2}[:.]\d{2}.*[去见约到]/,
          /(上午|下午|晚上|早上)\d{1,2}[点时]/,
          /日程|行程|安排|预约|航班/,
          /schedule|appointment|meeting at/i,
        ],
      },
      finance: {
        description: 'Financial information',
        patterns: [
          /工资|薪水|月薪|年薪|收入/,
          /投资.*\d|账户.*余额|信用卡.*\d/,
          /salary|income|balance|investment.*\$/i,
        ],
      },
      contact_private: {
        description: 'Private contact information',
        patterns: [
          /\d{8,11}/, // phone numbers
          /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/, // email
          /住在|地址[是为]|家在/,
        ],
      },
    };
  }

  review(message, channelType, participants) {
    if (!this.config.review.enabled) {
      return { passed: true, message };
    }

    if (participants.length <= 1) {
      return { passed: true, message };
    }

    const violations = this.checkPatterns(message);
    
    if (violations.length > 0) {
      return {
        passed: false,
        violations,
        suggestion: 'Message contains private information, please rewrite',
      };
    }

    return { passed: true, message };
  }

  checkPatterns(message) {
    const violations = [];
    const alwaysPrivate = this.config.defaults.alwaysPrivateCategories || [];
    
    for (const [category, data] of Object.entries(this.patterns)) {
      if (!alwaysPrivate.includes(category)) continue;
      
      for (const pattern of data.patterns) {
        const match = message.match(pattern);
        if (match) {
          violations.push({
            category,
            matched: match[0],
            description: `Detected ${data.description}`,
          });
          break;
        }
      }
    }
    
    return violations;
  }
}

// Knowledge store class
class KnowledgeStore {
  constructor(basePath) {
    this.basePath = basePath;
    this.items = new Map(); // user -> items[]
  }

  async load() {
    // Implementation would load from filesystem
    return this;
  }

  getByUser(user) {
    return this.items.get(user) || [];
  }

  getPublicByUser(user) {
    const items = this.items.get(user) || [];
    return items.filter(item => item.visibility === 'public');
  }

  getAll() {
    const result = [];
    for (const items of this.items.values()) {
      result.push(...items);
    }
    return result;
  }

  add(item) {
    if (!this.items.has(item.user)) {
      this.items.set(item.user, []);
    }
    this.items.get(item.user).push(item);
    // TODO: Save to filesystem
    return item;
  }

  listUsers() {
    return Array.from(this.items.keys());
  }
}

// Plugin implementation
const privacyGuardPlugin = {
  id: 'privacy-guard',
  name: 'Privacy Guard',
  description: 'Multi-user privacy isolation framework',
  
  async register(api, config) {
    const validatedConfig = pluginConfigSchema.parse(config);
    
    // Initialize components
    const knowledgeStore = new KnowledgeStore(validatedConfig.knowledgeBase.path);
    await knowledgeStore.load();
    
    const reviewer = new PrivacyReviewer(validatedConfig, knowledgeStore);
    
    // Store instances for hooks
    const pluginState = {
      config: validatedConfig,
      knowledgeStore,
      reviewer,
      contexts: new Map(), // channelId -> PrivacyContext
    };
    
    // Register hooks
    api.registerHook('session:init', async (session) => {
      const context = new PrivacyContext(
        session.channelId,
        session.participants || [],
        validatedConfig
      );
      pluginState.contexts.set(session.channelId, context);
      
      // Inject privacy context into session prompt
      const summary = context.getContextSummary();
      if (session.prompt) {
        session.prompt = `${summary}\n\n${session.prompt}`;
      }
      
      return session;
    });
    
    api.registerHook('message:beforeSend', async (message, session) => {
      if (!validatedConfig.review.enabled) return message;
      
      const context = pluginState.contexts.get(session.channelId);
      if (!context || context.isPrivate) return message;
      
      const result = reviewer.review(
        message.content,
        context.isPrivate ? 'dm' : 'group',
        Array.from(context.participants)
      );
      
      if (!result.passed && validatedConfig.review.blockOnViolation) {
        throw new Error(`Privacy violation: ${JSON.stringify(result.violations)}`);
      }
      
      return message;
    });
    
    api.registerHook('memory:search', async (results, session) => {
      if (!validatedConfig.enabled) return results;
      
      const context = pluginState.contexts.get(session.channelId);
      if (!context) return results;
      
      return context.filterMemoryResults(results);
    });
    
    api.registerHook('file:read', async (path, session) => {
      if (!validatedConfig.enabled) return { allow: true };
      
      const context = pluginState.contexts.get(session.channelId);
      if (!context) return { allow: true };
      
      // Check if file is in privacy knowledge directory
      if (path.includes(validatedConfig.knowledgeBase.path)) {
        const user = path.split('/').slice(-2, -1)[0];
        const isPrivate = path.endsWith('private.jsonl');
        
        if (isPrivate && !context.isPrivate) {
          return { allow: false, reason: 'Private knowledge not accessible in group chat' };
        }
        
        if (!context.participants.has(user)) {
          return { allow: false, reason: 'Knowledge belongs to non-participant user' };
        }
      }
      
      return { allow: true };
    });
    
    // Register tools
    api.registerTool('privacyContext', async () => {
      const context = pluginState.contexts.get(api.getCurrentSession().channelId);
      if (!context) {
        return { error: 'No privacy context for current session' };
      }
      
      return {
        isPrivate: context.isPrivate,
        participants: Array.from(context.participants),
        accessibleKnowledge: context.getAccessibleKnowledge(knowledgeStore),
        summary: context.getContextSummary(),
      };
    });
    
    api.registerTool('privacyReview', async ({ message, channelType, participants }) => {
      return reviewer.review(message, channelType, participants);
    });
    
    api.registerTool('addKnowledge', async ({ user, content, category, visibility, source }) => {
      const item = {
        id: `k_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        user,
        content,
        visibility: visibility || validatedConfig.defaults.visibility,
        category,
        source: source || 'manual',
        created: new Date().toISOString(),
      };
      
      const validatedItem = knowledgeItemSchema.parse(item);
      knowledgeStore.add(validatedItem);
      
      return { success: true, item: validatedItem };
    });
    
    return pluginState;
  },
};

export default privacyGuardPlugin;