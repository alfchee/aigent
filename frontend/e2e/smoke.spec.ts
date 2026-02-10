import { expect, test } from '@playwright/test'

const viewports = [
  { name: 'desktop', width: 1280, height: 720 },
  { name: 'tablet', width: 834, height: 1112 },
  { name: 'mobile', width: 390, height: 844 }
]

for (const viewport of viewports) {
  test(`renders split layout on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.goto('/')
    await expect(page.getByText('Navibot')).toBeVisible()
    await expect(page.getByText('Artefactos')).toBeVisible()
  })
}
