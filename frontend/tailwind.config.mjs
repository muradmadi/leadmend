/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
	theme: {
		extend: {
			colors: {
				'lm-bg': '#1c1c1e',
				'lm-card': '#2c2c2e',
				'lm-text': '#f5f5f5',
				'lm-accent': '#e76f51',
				'lm-border': '#ffffff14',
			},
			fontFamily: {
				heading: ['"Playfair Display"', 'serif'],
				body: ['Inter', 'sans-serif'],
				mono: ['"JetBrains Mono"', 'monospace'],
			},
			borderRadius: {
				'none': '0px',
			},
		},
	},
	plugins: [],
}
