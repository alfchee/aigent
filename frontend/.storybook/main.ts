import type { StorybookConfig } from '@storybook/vue3-vite'

const config: StorybookConfig = {
  framework: '@storybook/vue3-vite',
  stories: ['../src/**/*.stories.@(js|jsx|ts|tsx)'],
  addons: ['@storybook/addon-essentials'],
  docs: { autodocs: true },
}

export default config
