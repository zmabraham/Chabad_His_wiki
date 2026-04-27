/**
 * Undaunted Knowledge System — Main Viewer
 */

type EntityType = 'person' | 'place' | 'event' | 'time' | 'quote' | 'concept';

interface Entity {
  id: string;
  type: EntityType;
  primary_name: string;
  aliases: string[];
  description: string;
  born?: string;
  died?: string;
}

interface Page {
  pdf_page: number;
  book_page: number;
  chapter: number;
  text: string;
  tags: TagSpan[];
}

interface TagSpan {
  start: number;
  end: number;
  entity_id: string | null;
}

interface Chapter {
  num: number;
  title: string;
  first: number;
  last: number;
}

interface Manifest {
  version: string;
  page_range: [number, number];
  entity_count: number;
  wiki_ids: string[];
}

class UndauntedApp {
  private entities: Entity[] = [];
  private entityMap: Map<string, Entity> = new Map();
  private chapters: Chapter[] = [];
  private currentChapter = 0;
  private currentPages: Page[] = [];
  private selectedEntity: string | null = null;
  private filterType: EntityType | 'all' = 'all';
  private searchQuery = '';

  private readonly ENTITY_COLORS: Record<string, string> = {
    person: '#4A6FA5',
    place: '#8B7355',
    event: '#C45C3E',
    time: '#6B8E4F',
    quote: '#7B6B8E',
    concept: '#A67C52',
  };

  private readonly CHAPTER_TITLES: Record<number, string> = {
    0: 'Preface',
    1: 'Lubavitch',
    2: 'Tomchei Temimim',
    3: 'The Secret Covenant',
    4: 'Armed Men at Midnight',
    5: 'Exile to Riga',
    6: 'The Royal Wedding',
    7: 'The Voyage',
    8: 'Poland – Starting Anew',
    9: 'The World Is Shattered',
    10: 'America Iz Nisht Anderesh',
    11: 'A Global Vision',
  };

  async init() {
    try {
      await this.loadData();
      this.buildEntityMap();
      this.render();
      this.setupEventListeners();
      await this.loadChapter(0);
    } catch (error) {
      this.showError((error as Error).message);
      console.error(error);
    }
  }

  private async loadData() {
    const [manifestRes, entitiesRes] = await Promise.all([
      fetch('./data/manifest.json'),
      fetch('./data/entities.json'),
    ]);
    if (!manifestRes.ok) throw new Error('Failed to load manifest');
    if (!entitiesRes.ok) throw new Error('Failed to load entities');

    const manifest: Manifest = await manifestRes.json();
    this.entities = await entitiesRes.json();

    // Try chapters.json (handle both old {num,file} and new {num,title,first,last} formats)
    try {
      const chapRes = await fetch('./data/chapters.json');
      if (chapRes.ok) {
        const raw: Array<{ num: number; title?: string; first?: number; last?: number }> =
          await chapRes.json();
        this.chapters = raw
          .map((c) => ({
            num: c.num,
            title: c.title || this.CHAPTER_TITLES[c.num] || `Chapter ${c.num}`,
            first: c.first || 0,
            last: c.last || 0,
          }))
          .sort((a, b) => a.num - b.num);
      }
    } catch (_) { /* ignore */ }

    if (this.chapters.length === 0) {
      this.chapters = Object.entries(this.CHAPTER_TITLES).map(([num, title]) => ({
        num: parseInt(num), title, first: 0, last: 0,
      })).sort((a, b) => a.num - b.num);
    }

    const statsEl = document.getElementById('stats');
    if (statsEl) {
      statsEl.textContent =
        `${this.entities.length} entities · ${this.chapters.length} chapters · built ${manifest.version}`;
    }
  }

  private buildEntityMap() {
    for (const entity of this.entities) this.entityMap.set(entity.id, entity);
  }

  async loadChapter(chapterNum: number) {
    this.currentChapter = chapterNum;
    this.currentPages = [];

    const container = document.getElementById('source-content');
    if (container) container.innerHTML = '<div class="loading">Loading…</div>';

    // Load all pages and filter by chapter
    const pages: Page[] = [];
    const fetches: Promise<void>[] = [];
    for (let p = 19; p <= 413; p++) {
      fetches.push(
        fetch(`./data/pages/${p}.json`)
          .then((r) => (r.ok ? r.json() : null))
          .then((page: Page | null) => {
            if (page && page.chapter === chapterNum) pages.push(page);
          })
          .catch(() => { /* ignore missing pages */ }),
      );
    }
    await Promise.all(fetches);

    this.currentPages = pages.sort((a, b) => a.pdf_page - b.pdf_page);
    this.renderSourceText();
    this.updateChapterNav();
  }

  private render() {
    this.renderEntityList();
    this.renderChapterNav();
  }

  private renderChapterNav() {
    const nav = document.getElementById('chapter-nav');
    if (!nav) return;
    nav.innerHTML = this.chapters
      .map(
        (ch) =>
          `<div class="chapter-nav-item ${ch.num === this.currentChapter ? 'active' : ''}"
                data-chapter="${ch.num}">
             <span class="chapter-num">${ch.num === 0 ? 'P' : ch.num}</span>
             <span class="chapter-name">${ch.title}</span>
           </div>`,
      )
      .join('');
  }

  private updateChapterNav() {
    document.querySelectorAll<HTMLElement>('.chapter-nav-item').forEach((el) => {
      el.classList.toggle('active', parseInt(el.dataset.chapter ?? '-1') === this.currentChapter);
    });
  }

  private renderEntityList() {
    const container = document.getElementById('entity-list');
    if (!container) return;

    let filtered = this.entities;
    if (this.filterType !== 'all') filtered = filtered.filter((e) => e.type === this.filterType);
    if (this.searchQuery) {
      const q = this.searchQuery.toLowerCase();
      filtered = filtered.filter(
        (e) =>
          e.primary_name.toLowerCase().includes(q) ||
          e.aliases.some((a) => a.toLowerCase().includes(q)),
      );
    }

    container.innerHTML = filtered
      .map((entity) => {
        const color = this.ENTITY_COLORS[entity.type] || '#888';
        const sel = this.selectedEntity === entity.id;
        return `<div class="entity-item${sel ? ' selected' : ''}"
                     data-entity-id="${entity.id}"
                     style="border-left:3px solid ${color}${sel ? ';background:rgba(255,255,255,0.06)' : ''}">
                  <div class="entity-name">${entity.primary_name}</div>
                  <div class="entity-type" style="color:${color}">${entity.type}</div>
                </div>`;
      })
      .join('');
  }

  private renderSourceText() {
    const container = document.getElementById('source-content');
    if (!container) return;

    if (this.currentPages.length === 0) {
      container.innerHTML = '<div class="loading">No pages found for this chapter.</div>';
      return;
    }

    const chapter = this.chapters.find((c) => c.num === this.currentChapter);
    let html = `<div class="chapter-header">
      <div class="chapter-header-num">${this.currentChapter === 0 ? 'Preface' : `Chapter ${this.currentChapter}`}</div>
      <div class="chapter-header-title">${chapter?.title ?? ''}</div>
      <div class="chapter-header-pages">${this.currentPages.length} pages</div>
    </div>`;

    for (const page of this.currentPages) {
      html += `<div class="page-block" id="page-${page.pdf_page}">
        <div class="page-num">p. ${page.book_page}</div>
        <div class="page-text">${this.renderTaggedText(page)}</div>
      </div>`;
    }

    container.innerHTML = html;
    container.scrollTop = 0;
  }

  private renderTaggedText(page: Page): string {
    const { text, tags } = page;
    if (!tags || tags.length === 0) return this.escHtml(text);

    // Filter valid tags and sort by start position
    const sorted = [...tags]
      .filter(
        (t) =>
          t.entity_id !== null &&
          t.start >= 0 &&
          t.end > t.start &&
          t.end <= text.length,
      )
      .sort((a, b) => a.start - b.start);

    // Resolve overlaps: keep first-starting tag
    const clean: TagSpan[] = [];
    let lastEnd = 0;
    for (const tag of sorted) {
      if (tag.start >= lastEnd) {
        clean.push(tag);
        lastEnd = tag.end;
      }
    }

    // Build HTML left-to-right
    let result = '';
    let pos = 0;

    for (const tag of clean) {
      if (tag.start > pos) result += this.escHtml(text.slice(pos, tag.start));

      const tagText = text.slice(tag.start, tag.end);
      const entity = this.entityMap.get(tag.entity_id!);
      const type = entity?.type ?? 'concept';
      const color = this.ENTITY_COLORS[type] ?? '#888';
      const isSel = this.selectedEntity === tag.entity_id;
      const style = isSel
        ? `background:${color};color:#fff;border-radius:2px;padding:0 2px`
        : `border-bottom:1px solid ${color};cursor:pointer`;

      result +=
        `<span class="entity-tag ${type}${isSel ? ' selected' : ''}"` +
        ` data-entity-id="${tag.entity_id}"` +
        ` style="${style}"` +
        ` title="${entity?.primary_name ?? tag.entity_id}">${this.escHtml(tagText)}</span>`;

      pos = tag.end;
    }

    if (pos < text.length) result += this.escHtml(text.slice(pos));
    return result;
  }

  private escHtml(s: string): string {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  private setupEventListeners() {
    document.getElementById('entity-list')?.addEventListener('click', (e) => {
      const item = (e.target as HTMLElement).closest<HTMLElement>('[data-entity-id]');
      if (item?.dataset.entityId) this.selectEntity(item.dataset.entityId);
    });

    document.getElementById('chapter-nav')?.addEventListener('click', (e) => {
      const item = (e.target as HTMLElement).closest<HTMLElement>('[data-chapter]');
      if (item?.dataset.chapter !== undefined) void this.loadChapter(parseInt(item.dataset.chapter));
    });

    document.getElementById('source-content')?.addEventListener('click', (e) => {
      const span = (e.target as HTMLElement).closest<HTMLElement>('[data-entity-id]');
      if (span?.dataset.entityId) this.selectEntity(span.dataset.entityId);
    });

    document.querySelectorAll('.filter-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        this.filterType = ((btn as HTMLElement).dataset.type ?? 'all') as EntityType | 'all';
        this.renderEntityList();
      });
    });

    document.getElementById('entity-search')?.addEventListener('input', (e) => {
      this.searchQuery = (e.target as HTMLInputElement).value.trim();
      this.renderEntityList();
    });
  }

  private selectEntity(entityId: string) {
    this.selectedEntity = this.selectedEntity === entityId ? null : entityId;
    this.renderEntityList();
    this.renderSourceText();
    this.renderEntityDetail();
  }

  private renderEntityDetail() {
    const panel = document.getElementById('entity-detail');
    if (!panel) return;

    if (!this.selectedEntity) {
      panel.innerHTML = '<div class="detail-empty">Select an entity to see details</div>';
      return;
    }

    const entity = this.entityMap.get(this.selectedEntity);
    if (!entity) return;

    const color = this.ENTITY_COLORS[entity.type] ?? '#888';
    const mentions = this.currentPages.flatMap((p) =>
      p.tags.filter((t) => t.entity_id === this.selectedEntity),
    ).length;

    panel.innerHTML = `
      <div class="detail-type" style="color:${color}">${entity.type}</div>
      <h3 class="detail-name">${entity.primary_name}</h3>
      ${entity.aliases.length ? `<div class="detail-aliases">Also: ${entity.aliases.join(', ')}</div>` : ''}
      ${entity.born ? `<div class="detail-meta">Born: ${entity.born}</div>` : ''}
      ${entity.died ? `<div class="detail-meta">Died: ${entity.died}</div>` : ''}
      <p class="detail-desc">${entity.description}</p>
      ${mentions > 0 ? `<div class="detail-mentions">${mentions} mention${mentions !== 1 ? 's' : ''} in chapter</div>` : ''}
    `;
  }

  private showError(message: string) {
    const app = document.getElementById('app');
    if (app)
      app.innerHTML = `<div style="padding:3rem;text-align:center;color:#c45c3e"><h2>Error</h2><p>${message}</p></div>`;
  }
}

const app = new UndauntedApp();
void app.init();
(window as unknown as Record<string, unknown>).app = app;
