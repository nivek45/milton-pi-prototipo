const storageKey = 'saudash.theme';

export function themeColors() {
  const style = getComputedStyle(document.documentElement);
  const token = name => style.getPropertyValue('--color-' + name).trim();
  return {
    background: token('bg'),
    surface: token('map-surface'),
    accent: token('primary-titles'),
    title: token('title-ink'),
    text: token('text'),
    white: token('white'),
  };
}

export function setupTheme(select, storage, onChange, signal) {
  const root = document.documentElement;
  const supported = new Set(Array.from(select.options, option => option.value));
  let initial = root.dataset.theme;
  try {
    const saved = storage?.getItem(storageKey);
    if (supported.has(saved)) initial = saved;
  } catch { /* The theme also works with storage disabled. */ }

  function apply(value) {
    root.dataset.theme = value;
    select.value = value;
    document.querySelector('meta[name="theme-color"]').content = themeColors().background;
  }

  apply(initial);
  select.addEventListener('change', () => {
    apply(select.value);
    try { storage?.setItem(storageKey, select.value); } catch {}
    onChange();
  }, {signal});
}
