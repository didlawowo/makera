(() => {
  'use strict';
  const search = document.querySelector('#search');
  const results = document.querySelector('#search-results');
  const items = document.querySelector('#search-items');
  const status = document.querySelector('#search-status');
  const prefix = document.body.dataset.prefix || '';
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const pages = (window.MAKERA_PAGES || []).map(page => ({...page, normalizedTitle: normalize(page.title), normalizedText: normalize(page.text)}));
  function closeSearch() { results.hidden = true; search.value = ''; }
  search.addEventListener('input', () => {
    const query = normalize(search.value.trim());
    items.replaceChildren();
    if (query.length < 2) { results.hidden = true; return; }
    const words = query.split(/\s+/);
    const matches = pages.filter(page => words.every(word => (page.normalizedTitle + ' ' + page.normalizedText).includes(word)))
      .sort((a, b) => Number(b.normalizedTitle.includes(query)) - Number(a.normalizedTitle.includes(query)));
    status.textContent = `${matches.length} résultat${matches.length > 1 ? 's' : ''}`;
    for (const page of matches) {
      const link = document.createElement('a'); link.className = 'search-result'; link.href = prefix + page.url;
      const group = document.createElement('span'); group.className = 'result-group'; group.textContent = page.group;
      const title = document.createElement('h3'); title.textContent = page.title;
      const summary = document.createElement('p');
      const position = Math.max(0, page.normalizedText.indexOf(words[0]) - 65);
      summary.textContent = (position ? '…' : '') + page.text.slice(position, position + 220) + '…';
      link.append(group, title, summary); items.append(link);
    }
    if (!matches.length) { const message = document.createElement('p'); message.textContent = 'Aucune page trouvée. Essayez un terme plus court, comme « broche », « palpage » ou « Makera CAM ».'; items.append(message); }
    results.hidden = false;
  });
  document.querySelector('#search-close').addEventListener('click', closeSearch);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') { closeSearch(); document.body.classList.remove('menu-open'); document.querySelector('#menu-toggle').setAttribute('aria-expanded', 'false'); }
    if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && !document.activeElement.isContentEditable) { event.preventDefault(); search.focus(); }
  });
  document.querySelector('#menu-toggle').addEventListener('click', event => {
    const open = document.body.classList.toggle('menu-open'); event.currentTarget.setAttribute('aria-expanded', String(open));
  });
  for (const table of document.querySelectorAll('.article-body table')) {
    const wrapper = document.createElement('div'); wrapper.className = 'table-scroll'; wrapper.tabIndex = 0;
    wrapper.setAttribute('role', 'region'); wrapper.setAttribute('aria-label', 'Tableau à défilement horizontal');
    table.parentNode.insertBefore(wrapper, table); wrapper.append(table);
  }
})();
