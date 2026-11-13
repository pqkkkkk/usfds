import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

export type ThemeMode = 'dark' | 'light';

export const THEME_STORAGE_KEY = 'usfds_theme';

export interface ChartThemeTokens {
	gridStroke: string;
	gridSubtleStroke: string;
	axisStroke: string;
	axisTick: string;
	axisLabel: string;
	tooltipBg: string;
	tooltipBorder: string;
	tooltipText: string;
	canvasDot: string;
	inactiveBar: string;
}

const DARK_CHART_TOKENS: ChartThemeTokens = {
	gridStroke: '#334155',
	gridSubtleStroke: '#1E293B',
	axisStroke: '#64748B',
	axisTick: '#CBD5E1',
	axisLabel: '#94A3B8',
	tooltipBg: '#0F172A',
	tooltipBorder: '#334155',
	tooltipText: '#F1F5F9',
	canvasDot: '#334155',
	inactiveBar: '#334155',
};

const LIGHT_CHART_TOKENS: ChartThemeTokens = {
	gridStroke: '#CBD5E1',
	gridSubtleStroke: '#E2E8F0',
	axisStroke: '#64748B',
	axisTick: '#334155',
	axisLabel: '#475569',
	tooltipBg: '#FFFFFF',
	tooltipBorder: '#CBD5E1',
	tooltipText: '#0F172A',
	canvasDot: '#CBD5E1',
	inactiveBar: '#CBD5E1',
};

export function resolveStoredTheme(raw: string | null | undefined): ThemeMode {
	if (raw === 'light' || raw === 'dark') {
		return raw;
	}
	return 'dark';
}

export function getChartThemeTokens(theme: ThemeMode): ChartThemeTokens {
	return theme === 'light' ? LIGHT_CHART_TOKENS : DARK_CHART_TOKENS;
}

export function applyThemeToDocument(theme: ThemeMode, rootElement?: HTMLElement | null): void {
	const el = rootElement ?? (typeof document !== 'undefined' ? document.documentElement : null);
	if (!el) {
		return;
	}
	el.setAttribute('data-theme', theme);
	if (theme === 'dark') {
		el.classList.add('dark');
		el.classList.remove('light');
	} else {
		el.classList.add('light');
		el.classList.remove('dark');
	}
}

interface ThemeContextValue {
	theme: ThemeMode;
	isLight: boolean;
	setTheme: (theme: ThemeMode) => void;
	toggleTheme: () => void;
	chartTokens: ChartThemeTokens;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
	const [theme, setThemeState] = useState<ThemeMode>(() => {
		if (typeof window === 'undefined') {
			return 'dark';
		}
		try {
			return resolveStoredTheme(window.localStorage.getItem(THEME_STORAGE_KEY));
		} catch {
			return 'dark';
		}
	});

	useEffect(() => {
		applyThemeToDocument(theme);
		try {
			window.localStorage.setItem(THEME_STORAGE_KEY, theme);
		} catch {
			// Ignore storage quota / privacy errors
		}
	}, [theme]);

	const setTheme = useCallback((nextTheme: ThemeMode) => {
		setThemeState(nextTheme);
	}, []);

	const toggleTheme = useCallback(() => {
		setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'));
	}, []);

	const value = useMemo<ThemeContextValue>(
		() => ({
			theme,
			isLight: theme === 'light',
			setTheme,
			toggleTheme,
			chartTokens: getChartThemeTokens(theme),
		}),
		[theme, setTheme, toggleTheme]
	);

	return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
	const context = useContext(ThemeContext);
	if (!context) {
		return {
			theme: 'dark',
			isLight: false,
			setTheme: () => {},
			toggleTheme: () => {},
			chartTokens: DARK_CHART_TOKENS,
		};
	}
	return context;
}

