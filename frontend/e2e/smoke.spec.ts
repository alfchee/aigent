import { expect, test } from '@playwright/test'

test('renders split layout', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Navibot')).toBeVisible()
  await expect(page.getByText('Artefactos')).toBeVisible()
})

<<<<<<< Updated upstream
=======
for (const viewport of viewports) {
  test(`renders split layout on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Navibot' })).toBeVisible()
    await expect(page.getByText('Artefactos', { exact: true }).first()).toBeVisible()
  })
}
>>>>>>> Stashed changes
