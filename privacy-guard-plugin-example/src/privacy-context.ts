import type { ChannelInfo, KnowledgeItem, PrivacyContext as IPrivacyContext } from './types';
import { KnowledgeStore } from './knowledge-store';

export class PrivacyContext implements IPrivacyContext {
  constructor(
    private channel: ChannelInfo,
    private store: KnowledgeStore
  ) {}

  get isPrivate(): boolean {
    return this.channel.participants.size <= 1;
  }

  get participants(): Set<string> {
    return this.channel.participants;
  }

  getAccessibleKnowledge(): KnowledgeItem[] {
    if (this.isPrivate) {
      // Private chat: all knowledge of the single user
      const user = Array.from(this.participants)[0];
      return this.store.getAll(user);
    } else {
      // Group chat: public knowledge of all participants
      const result: KnowledgeItem[] = [];
      for (const user of this.participants) {
        result.push(...this.store.getPublic(user));
      }
      return result;
    }
  }

  canAccessItem(item: KnowledgeItem): boolean {
    if (this.isPrivate) {
      const user = Array.from(this.participants)[0];
      return item.user === user;
    } else {
      // Group chat: only public knowledge of participants
      if (!this.participants.has(item.user)) {
        return false;
      }
      return item.visibility === 'public';
    }
  }

  getAccessiblePaths(): Set<string> {
    const paths = new Set<string>();

    if (this.isPrivate) {
      const user = Array.from(this.participants)[0];
      paths.add(`${this.store.basePath}/${user}/public.jsonl`);
      paths.add(`${this.store.basePath}/${user}/private.jsonl`);
    } else {
      for (const user of this.participants) {
        paths.add(`${this.store.basePath}/${user}/public.jsonl`);
        // NOT private.jsonl in group context
      }
    }

    return paths;
  }

  filterMemoryResults(results: any[]): any[] {
    const accessiblePaths = this.getAccessiblePaths();
    return results.filter(r => accessiblePaths.has(r.path));
  }

  getContextSummary(): string {
    if (this.isPrivate) {
      const user = Array.from(this.participants)[0];
      return `[Privacy] Private chat mode (user: ${user}) - Access to all knowledge of this user`;
    } else {
      const users = Array.from(this.participants).sort().join(', ');
      return `[Privacy] Group chat mode (participants: ${users}) - Only public knowledge of participants is accessible`;
    }
  }
}