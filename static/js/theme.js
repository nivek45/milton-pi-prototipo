export function themeColors() {
  const style = getComputedStyle(document.documentElement);
  const token = name => style.getPropertyValue('--color-' + name).trim();
  return {
    background: token('bg'),
    surface: token('map-surface'),
    scaleLow: token('scale-low'),
    accent: token('primary-titles'),
    title: token('title-ink'),
    text: token('text'),
    tooltipSurface: token('inverse-surface'),
    tooltipText: token('inverse-ink'),
  };
}
