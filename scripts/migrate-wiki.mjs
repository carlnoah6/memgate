#!/usr/bin/env node
/**
 * Migrate 5 research docs from Luna Wiki to Carl's private Wiki
 */

import fs from 'fs';

const TOKEN_FILE = '/home/ubuntu/.openclaw/workspace/data/lark-user-token.json';
const { access_token } = JSON.parse(fs.readFileSync(TOKEN_FILE, 'utf-8'));
const AUTH = `Bearer ${access_token}`;
const BASE = 'https://open.larksuite.com/open-apis';

// Target Wiki
const TARGET_SPACE = '7604150806383693538';
const TARGET_PARENT = 'OZmqwn4yviwsY2k1JBblkgTYg5c';

// Source Wiki (to delete)
const SOURCE_SPACE = '7604126789916479197';
const OLD_NODES = [
  'NIjpwPJ8RieE2Nkh6ERlEWFUgog',
  'C6KkwspVviOnxJk4jGsl10eigqL',
  'Q8fkwEORoiqMeJka5e6luTaxgKc',
  'VycywVflXieGSRkf799lyBcdgxf',
  'GHBkwVf5diByJekp47RlCbz8gIg',
];

// Documents to migrate
const DOCS = [
  {
    file: '/home/ubuntu/.openclaw/workspace/memory/research/llm-architecture-survey-2026-02-08.md',
    title: 'LLM 架构综述：Transformer 变体、Mamba/SSM、MoE 及当前 SOTA 选型建议',
  },
  {
    file: '/home/ubuntu/.openclaw/workspace/memory/research/llm-training-data-guide-2026-02-08.md',
    title: 'LLM 预训练数据：公开数据集全景、清洗流程与配比策略',
  },
  {
    file: '/home/ubuntu/.openclaw/workspace/memory/research/tokenizer-design-2026-02-08.md',
    title: 'Tokenizer 设计：BPE vs SentencePiece vs Unigram，中英文混合方案',
  },
  {
    file: '/home/ubuntu/.openclaw/workspace/memory/research/llm-training-framework-comparison-2026-02-08.md',
    title: 'LLM 训练框架对比：PyTorch FSDP / DeepSpeed / Megatron-LM / JAX+TPU',
  },
  {
    file: '/home/ubuntu/.openclaw/workspace/memory/research/hardware-cost-analysis-2026-02-08.md',
    title: '硬件与成本分析：GPU vs TPU，LLM 训练算力需求与预算估算',
  },
];

async function api(method, path, body) {
  const url = `${BASE}${path}`;
  const opts = {
    method,
    headers: {
      'Authorization': AUTH,
      'Content-Type': 'application/json',
    },
  };
  if (body) opts.body = JSON.stringify(body);
  
  const res = await fetch(url, opts);
  const json = await res.json();
  if (json.code !== 0) {
    console.error(`API Error [${method} ${path}]:`, JSON.stringify(json, null, 2));
    throw new Error(`API error code=${json.code} msg=${json.msg}`);
  }
  return json.data;
}

// Convert markdown to Lark docx blocks
function markdownToBlocks(md) {
  const lines = md.split('\n');
  const blocks = [];
  let i = 0;
  
  while (i < lines.length) {
    const line = lines[i];
    
    // Skip empty lines
    if (line.trim() === '') {
      i++;
      continue;
    }
    
    // Headings
    const headingMatch = line.match(/^(#{1,9})\s+(.+)/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      // Lark heading levels: heading1=3, heading2=4, ..., heading9=11
      const blockType = 2 + level; // heading1=3, heading2=4, etc.
      blocks.push({
        block_type: blockType,
        [`heading${level}`]: {
          elements: parseInlineElements(headingMatch[2]),
        },
      });
      i++;
      continue;
    }
    
    // Code blocks
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim();
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      blocks.push({
        block_type: 14,
        code: {
          elements: [{
            text_run: {
              content: codeLines.join('\n'),
              text_element_style: {},
            },
          }],
          style: {
            language: mapCodeLanguage(lang),
          },
        },
      });
      continue;
    }
    
    // Blockquote
    if (line.startsWith('> ')) {
      // Collect consecutive quote lines
      const quoteLines = [];
      while (i < lines.length && lines[i].startsWith('> ')) {
        quoteLines.push(lines[i].slice(2));
        i++;
      }
      // Quote container needs children - we'll use a paragraph inside
      // Actually, Lark quote_container (type 7) is a container that must contain children blocks
      // But the create children API only allows one level. Let's use callout (type 15) instead
      // Actually, let's just use a paragraph with special formatting
      blocks.push({
        block_type: 2,
        text: {
          elements: parseInlineElements(quoteLines.join('\n')),
          style: {},
        },
      });
      continue;
    }
    
    // Tables (markdown)
    if (line.includes('|') && line.trim().startsWith('|')) {
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        tableLines.push(lines[i]);
        i++;
      }
      // Parse table - skip separator line
      const rows = tableLines
        .filter(l => !l.match(/^\|[\s-:|]+\|$/))
        .map(l => l.split('|').slice(1, -1).map(c => c.trim()));
      
      if (rows.length > 0) {
        // Convert table to text paragraphs since Lark table API is complex
        for (const row of rows) {
          blocks.push({
            block_type: 2,
            text: {
              elements: parseInlineElements(row.join(' | ')),
              style: {},
            },
          });
        }
      }
      continue;
    }
    
    // Unordered list
    if (line.match(/^[-*]\s+/) || line.match(/^\s+[-*]\s+/)) {
      const content = line.replace(/^\s*[-*]\s+/, '');
      blocks.push({
        block_type: 9,
        bullet: {
          elements: parseInlineElements(content),
        },
      });
      i++;
      continue;
    }
    
    // Ordered list
    if (line.match(/^\d+\.\s+/) || line.match(/^\s+\d+\.\s+/)) {
      const content = line.replace(/^\s*\d+\.\s+/, '');
      blocks.push({
        block_type: 10,
        ordered: {
          elements: parseInlineElements(content),
        },
      });
      i++;
      continue;
    }

    // Checkbox list  
    if (line.match(/^- \[[ x]\]\s+/)) {
      const checked = line.includes('[x]');
      const content = line.replace(/^- \[[ x]\]\s+/, '');
      blocks.push({
        block_type: 2,
        text: {
          elements: parseInlineElements((checked ? '☑ ' : '☐ ') + content),
          style: {},
        },
      });
      i++;
      continue;
    }
    
    // Horizontal rule
    if (line.match(/^---+$/)) {
      blocks.push({
        block_type: 22,
        divider: {},
      });
      i++;
      continue;
    }
    
    // Default: paragraph
    blocks.push({
      block_type: 2,
      text: {
        elements: parseInlineElements(line),
        style: {},
      },
    });
    i++;
  }
  
  return blocks;
}

function parseInlineElements(text) {
  const elements = [];
  // Simple inline parsing - handle **bold**, *italic*, `code`, [link](url)
  let remaining = text;
  
  while (remaining.length > 0) {
    // Bold **text**
    let match = remaining.match(/^(.*?)\*\*(.+?)\*\*(.*)/s);
    if (match) {
      if (match[1]) {
        elements.push(...parseInlineSimple(match[1]));
      }
      elements.push({
        text_run: {
          content: match[2],
          text_element_style: { bold: true },
        },
      });
      remaining = match[3];
      continue;
    }
    
    // Code `text`
    match = remaining.match(/^(.*?)`(.+?)`(.*)/s);
    if (match) {
      if (match[1]) {
        elements.push(...parseInlineSimple(match[1]));
      }
      elements.push({
        text_run: {
          content: match[2],
          text_element_style: { inline_code: true },
        },
      });
      remaining = match[3];
      continue;
    }
    
    // No more inline formatting
    elements.push(...parseInlineSimple(remaining));
    break;
  }
  
  if (elements.length === 0) {
    elements.push({
      text_run: {
        content: ' ',
        text_element_style: {},
      },
    });
  }
  
  return elements;
}

function parseInlineSimple(text) {
  if (!text) return [];
  // Handle links [text](url)
  const parts = [];
  let remaining = text;
  
  while (remaining.length > 0) {
    const match = remaining.match(/^(.*?)\[(.+?)\]\((.+?)\)(.*)/s);
    if (match) {
      if (match[1]) {
        parts.push({
          text_run: {
            content: match[1],
            text_element_style: {},
          },
        });
      }
      parts.push({
        text_run: {
          content: match[2],
          text_element_style: {
            link: { url: encodeURI(match[3]) },
          },
        },
      });
      remaining = match[4];
    } else {
      parts.push({
        text_run: {
          content: remaining,
          text_element_style: {},
        },
      });
      break;
    }
  }
  
  return parts;
}

function mapCodeLanguage(lang) {
  const map = {
    python: 18,
    py: 18,
    javascript: 12,
    js: 12,
    json: 35,
    bash: 22,
    sh: 22,
    shell: 22,
    markdown: 39,
    md: 39,
    '': 1, // plain text
  };
  return map[lang.toLowerCase()] ?? 1;
}

async function createWikiNode(title) {
  console.log(`Creating wiki node: ${title}`);
  const data = await api('POST', `/wiki/v2/spaces/${TARGET_SPACE}/nodes`, {
    obj_type: 'docx',
    node_type: 'origin',
    parent_node_token: TARGET_PARENT,
    title: title,
  });
  console.log(`  → node_token: ${data.node.node_token}, obj_token: ${data.node.obj_token}`);
  return data.node;
}

async function writeDocxContent(documentId, blocks) {
  // Lark limits children creation. We'll batch in groups of 50.
  const BATCH_SIZE = 50;
  for (let start = 0; start < blocks.length; start += BATCH_SIZE) {
    const batch = blocks.slice(start, start + BATCH_SIZE);
    const batchNum = Math.floor(start / BATCH_SIZE) + 1;
    const totalBatches = Math.ceil(blocks.length / BATCH_SIZE);
    console.log(`  Writing blocks batch ${batchNum}/${totalBatches} (${batch.length} blocks)`);
    
    try {
      await api('POST', `/docx/v1/documents/${documentId}/blocks/${documentId}/children`, {
        children: batch,
        index: -1,
      });
    } catch (err) {
      console.error(`  Failed batch ${batchNum}, trying one-by-one...`);
      // Try one by one for failed batch
      for (const block of batch) {
        try {
          await api('POST', `/docx/v1/documents/${documentId}/blocks/${documentId}/children`, {
            children: [block],
            index: -1,
          });
        } catch (e2) {
          console.error(`  Skipping block type ${block.block_type}:`, e2.message);
        }
      }
    }
    
    // Small delay to avoid rate limiting
    await new Promise(r => setTimeout(r, 300));
  }
}

async function deleteOldNode(nodeToken) {
  console.log(`Deleting old node: ${nodeToken}`);
  try {
    await api('DELETE', `/wiki/v2/spaces/${SOURCE_SPACE}/nodes/${nodeToken}`);
    console.log(`  → Deleted`);
  } catch (err) {
    console.error(`  → Failed to delete ${nodeToken}:`, err.message);
  }
}

async function main() {
  console.log('=== Wiki Migration: Luna → Carl ===\n');
  
  const results = [];
  
  // Step 1: Create nodes and write content
  for (const doc of DOCS) {
    console.log(`\n--- Processing: ${doc.title} ---`);
    
    // Read local file
    const md = fs.readFileSync(doc.file, 'utf-8');
    
    // Skip the first heading line (title) since it's already in the node title
    const mdWithoutTitle = md.replace(/^#\s+.+\n/, '');
    
    // Create wiki node
    const node = await createWikiNode(doc.title);
    const documentId = node.obj_token;
    
    // Convert markdown to blocks
    const blocks = markdownToBlocks(mdWithoutTitle);
    console.log(`  Total blocks: ${blocks.length}`);
    
    // Write content
    await writeDocxContent(documentId, blocks);
    
    results.push({ title: doc.title, nodeToken: node.node_token, objToken: documentId });
    console.log(`  ✅ Done`);
    
    // Delay between documents
    await new Promise(r => setTimeout(r, 500));
  }
  
  // Step 2: Delete old nodes
  console.log('\n\n--- Deleting old nodes from Luna Wiki ---');
  for (const nodeToken of OLD_NODES) {
    await deleteOldNode(nodeToken);
    await new Promise(r => setTimeout(r, 300));
  }
  
  // Summary
  console.log('\n\n=== Migration Complete ===');
  console.log('Created nodes:');
  for (const r of results) {
    console.log(`  ✅ ${r.title} → ${r.nodeToken}`);
  }
  console.log(`\nDeleted ${OLD_NODES.length} old nodes from Luna Wiki`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
