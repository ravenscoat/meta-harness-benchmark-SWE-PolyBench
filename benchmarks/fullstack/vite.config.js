import { defineConfig } from 'vite';
export default defineConfig({server: {proxy: {'/items': 'http://127.0.0.1:8000', '/archive': 'http://127.0.0.1:8000'}}, test: {environment: 'jsdom', globals: true}, build: {outDir: 'dist'}});
