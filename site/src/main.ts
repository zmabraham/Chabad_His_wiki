/**
 * Undaunted Knowledge System - Main Viewer
 * A three-layer knowledge system: Source → Index → Wiki
 */

// Type definitions
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

// Application State
class UndauntedApp {
  private entities: Entity[] = [];
  private chapters: Chapter[] = [];
  private pages: Map<number, Page> = new Map();
  private selectedEntity: string | null = null;
  private filterType: EntityType | 'all' = 'all';

  // Color palette
  private readonly colors = {
    person: '#4A6FA5',
    place: '#8B7355',
    event: '#C45C3E',
    time: '#6B8E4F',
    quote: '#7B6B8E',
    concept: '#A67C52'
  };

  async init() {
    try {
      await this.loadEntities();
      await this.loadChapters();
      await this.loadPages();
      this.render();
      this.setupFilters();
    } catch (error) {
      this.showError('Failed to load data');
      console.error(error);
    }
  }

  private async loadEntities() {
    const response = await fetch('./data/entities.json');
    if (!response.ok) throw new Error('Failed to load entities');
    this.entities = await response.json();
  }

  private async loadChapters() {
    const response = await fetch('./data/chapters.json');
    if (!response.ok) throw new Error('Failed to load chapters');
    this.chapters = await response.json();
  }

  private async loadPages() {
    // For now, load the chapter files we have
    for (let i = 0; i < 12; i++) {
      try {
        const response = await fetch(`/corpus/chapter_${i}.txt`);
        if (response.ok) {
          const text = await response.text();
          const page: Page = {
            pdf_page: i + 19,
            book_page: i + 1,
            chapter: i,
            text: text,
            tags: this.tagPage(text)
          };
          this.pages.set(i, page);
        }
      } catch (e) {
        console.log(`Could not load chapter ${i}`);
      }
    }
  }

  private tagPage(text: string): TagSpan[] {
    const tags: TagSpan[] = [];
    const tagPatterns = {
      'person.yosef_yitzchak': ['Rabbi Yosef Yitzchak', 'Yosef Yitzchak', 'the Rayatz', 'The Rayatz', 'Rayatz'],
      'person.shalom_dovber': ['Rabbi Shalom Dovber', 'the Rashab', 'The Rashab', 'Rashab'],
      'person.menachem_mendel': ['Rabbi Menachem Mendel', 'the Ramash', 'The Ramash', 'Ramash'],
      'place.lubavitch': ['Lubavitch', 'Lyubavichi'],
      'place.warsaw': ['Warsaw'],
      'place.new_york': ['New York'],
      'time.1927': ['1927'],
      'time.1940': ['1940']
    };

    for (const [entityId, patterns] of Object.entries(tagPatterns)) {
      for (const pattern of patterns) {
        let start = 0;
        while (true) {
          const idx = text.indexOf(pattern, start);
          if (idx === -1) break;
          tags.push({
            start: idx,
            end: idx + pattern.length,
            entity_id: entityId
          });
          start = idx + pattern.length;
        }
      }
    }

    return tags;
  }

  private render() {
    this.updateStats();
    this.renderEntityList();
    this.renderSourceText();
  }

  private updateStats() {
    const stats = document.getElementById('stats')!;
    stats.textContent = `${this.entities.length} entities • ${this.chapters.length} chapters • ${this.pages.size} pages`;
  }

  private renderEntityList() {
    const container = document.getElementById('entity-list')!;

    let filtered = this.entities;
    if (this.filterType !== 'all') {
      filtered = this.entities.filter(e => e.type === this.filterType);
    }

    container.innerHTML = filtered.map(entity => `
      <div class="entity-item ${this.selectedEntity === entity.id ? 'selected' : ''}"
           data-entity-id="${entity.id}"
           onclick="app.selectEntity('${entity.id}')">
        <div class="entity-name">${entity.primary_name}</div>
        <div class="entity-type">${entity.type}</div>
      </div>
    `).join('');
  }

  private renderSourceText() {
    const container = document.getElementById('source-content')!;

    let html = '';

    // Render chapters
    for (const [num, page] of this.pages) {
      const chapter = this.chapters.find(ch => ch.num === num);

      html += `
        <div class="chapter-divider">
          <div class="chapter-title">${chapter?.title || `Chapter ${num}`}</div>
        </div>
        <div class="source-text">${this.renderTaggedText(page)}</div>
      `;
    }

    container.innerHTML = html || '<div class="loading">No source text available</div>';
  }

  private renderTaggedText(page: Page): string {
    const { text, tags } = page;

    if (!tags || tags.length === 0) {
      return text;
    }

    // Sort tags by position (descending)
    const sortedTags = [...tags].sort((a, b) => b.start - a.start);

    let result = '';
    let lastEnd = text.length;

    for (const tag of sortedTags) {
      // Add text after this tag
      if (tag.end < lastEnd) {
        result += this.escapeHtml(text.substring(tag.end, lastEnd));
      }

      // Add the tagged text
      const taggedText = text.substring(tag.start, tag.end);
      const entity = this.entities.find(e => e.id === tag.entity_id);
      const entityType = entity?.type || 'concept';
      const color = this.colors[entityType as keyof typeof this.colors] || '#666';

      result += `<span class="entity-tag ${entityType}"
                     data-entity-id="${tag.entity_id}"
                     style="${this.selectedEntity === tag.entity_id ? 'background:' + color + ' !important;color:white;' : ''}"
                     onclick="app.selectEntity('${tag.entity_id}')">${taggedText}</span>`;

      lastEnd = tag.start;
    }

    // Add remaining text
    result += this.escapeHtml(text.substring(0, lastEnd));

    return result.split('').reverse().join('');
  }

  private escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  private setupFilters() {
    const buttons = document.querySelectorAll('.filter-btn');
    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        buttons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const button = btn as HTMLElement;
        this.filterType = (button.dataset.type || 'all') as EntityType | 'all';
        this.renderEntityList();
      });
    });
  }

  selectEntity(entityId: string) {
    this.selectedEntity = this.selectedEntity === entityId ? null : entityId;
    this.renderEntityList();
    this.renderSourceText();
  }

  private showError(message: string) {
    document.getElementById('app')!.innerHTML = `
      <div style="padding: 3rem; text-align: center; color: var(--accent);">
        <h2>Error</h2>
        <p>${message}</p>
      </div>
    `;
  }
}

// Initialize app
const app = new UndauntedApp();
app.init();

// Make app globally accessible for onclick handlers
(window as any).app = app;
