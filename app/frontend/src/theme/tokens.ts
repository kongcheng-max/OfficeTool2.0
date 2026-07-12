/**
 * 设计 token — 语义化颜色系统（亮/暗成对）
 *
 * 单一事实来源：CSS 变量在 index.css 中定义，供 inline style 通过 var(--xxx) 引用；
 * 本文件导出与之数值一致的 JS 常量，供两类场景使用：
 *   1) AntD ConfigProvider 的 theme.token / components（无法读 CSS 变量）
 *   2) 需要真实色值的 JS 逻辑（如 G6 知识图谱节点着色）
 *
 * 参见 UI/docs/OfficeTool-UI设计规范.md
 */

export type ThemeMode = 'light' | 'dark';

/** 品牌与功能色（AntD token 用） */
const light = {
  brand: '#3370FF',
  brandHover: '#4E83FD',
  brandActive: '#1C4AC9',
  success: '#21A366',
  warning: '#E67E00',
  danger: '#F54A45',
  ink: '#1F2329',
  ink2: '#646A73',
  body: '#EEF0F3',
  paper: '#FFFFFF',
  line: '#E4E6EA',
};

const dark = {
  brand: '#4E83FD',
  brandHover: '#6A97FE',
  brandActive: '#3D71E8',
  success: '#3BD67E',
  warning: '#FFA53D',
  danger: '#F76965',
  ink: 'rgba(255,255,255,0.92)',
  ink2: 'rgba(255,255,255,0.58)',
  body: '#121316',
  paper: '#202225',
  line: '#33363B',
};

/** 知识图谱实体色 — 校准后统一层级 */
export const entityColors: Record<ThemeMode, Record<string, string>> = {
  light: {
    PERSON: '#3370FF',
    ORG: '#0F9E8E',
    DATE: '#C77700',
    MONEY: '#21A366',
    LOCATION: '#7C5CFF',
    TERM: '#D6417E',
  },
  dark: {
    PERSON: '#6A97FE',
    ORG: '#2DD4BF',
    DATE: '#FBBF24',
    MONEY: '#3BD67E',
    LOCATION: '#A78BFA',
    TERM: '#F472B6',
  },
};

/** 检索来源标签色 */
export const sourceColors: Record<ThemeMode, Record<string, string>> = {
  light: { vector: '#3370FF', bm25: '#21A366', kg: '#E67E00' },
  dark: { vector: '#4E83FD', bm25: '#3BD67E', kg: '#FFA53D' },
};

const palette: Record<ThemeMode, typeof light> = { light, dark };

/** 生成 AntD ConfigProvider theme.token */
export function antdToken(mode: ThemeMode) {
  const p = palette[mode];
  return {
    colorPrimary: p.brand,
    colorSuccess: p.success,
    colorWarning: p.warning,
    colorError: p.danger,
    colorInfo: p.brand,
    colorTextBase: mode === 'light' ? p.ink : '#FFFFFF',
    colorBgBase: mode === 'light' ? '#FFFFFF' : '#121316',
    borderRadius: 8,
    fontFamily:
      '"Inter", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    fontSize: 14,
  };
}

/** 组件级微调 */
export function antdComponents(mode: ThemeMode) {
  const p = palette[mode];
  return {
    Layout: {
      bodyBg: p.body,
      headerBg: p.paper,
      siderBg: mode === 'light' ? '#FBFBFC' : '#1A1B1E',
    },
    Card: { borderRadiusLG: 14 },
    Button: { borderRadius: 9, controlHeight: 34 },
    Menu: {
      itemBorderRadius: 11,
      itemSelectedBg: mode === 'light' ? '#EBF1FF' : 'rgba(78,131,253,0.18)',
      itemSelectedColor: p.brand,
    },
  };
}
