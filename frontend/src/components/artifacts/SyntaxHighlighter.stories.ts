import type { Meta, StoryObj } from '@storybook/vue3'

import SyntaxHighlighter from './SyntaxHighlighter.vue'

const meta: Meta<typeof SyntaxHighlighter> = {
  title: 'Artifacts/SyntaxHighlighter',
  component: SyntaxHighlighter
}

export default meta
type Story = StoryObj<typeof SyntaxHighlighter>

export const Python: Story = {
  args: {
    language: 'python',
    code: 'def hello(name: str) -> str:\n    return f\"Hola {name}\"\\n'
  }
}

