import { expect, test } from '@playwright/test'

test('renders split layout', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Navibot')).toBeVisible()
  await expect(page.getByText('Artefactos')).toBeVisible()
})

