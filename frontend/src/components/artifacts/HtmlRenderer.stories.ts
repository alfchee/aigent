import type { Meta, StoryObj } from '@storybook/vue3'

import HtmlRenderer from './HtmlRenderer.vue'

const meta: Meta<typeof HtmlRenderer> = {
  title: 'Artifacts/HtmlRenderer',
  component: HtmlRenderer
}

export default meta
type Story = StoryObj<typeof HtmlRenderer>

export const Basic: Story = {
  args: {
    html: '<h1>Preview HTML</h1><p>Este iframe está sandboxed.</p><script>alert(\"xss\")</script>'
  }
}

