describe('Settings - Cost Dashboard & State Tabs', () => {
  it('navigates to settings and shows three tabs', () => {
    cy.visit('/settings')
    cy.contains('General').should('be.visible')
    cy.contains('💰 Costos').should('be.visible')
    cy.contains('📊 Estado').should('be.visible')
  })

  it('switches to Costos tab and renders CostDashboard', () => {
    cy.visit('/settings')
    cy.contains('💰 Costos').click()
    cy.contains('Cost Dashboard').should('be.visible')
    cy.contains('Refresh').should('be.visible')
  })

  it('switches to Estado tab and renders GlobalStateWidget', () => {
    cy.visit('/settings')
    cy.contains('📊 Estado').click()
    cy.contains('Estado de Sesión').should('be.visible')
  })

  it('switches back to General tab', () => {
    cy.visit('/settings')
    cy.contains('💰 Costos').click()
    cy.contains('General').click()
    cy.contains('Preferencias').should('be.visible')
    cy.contains('Nombre visible').should('be.visible')
  })

  it('renders costs tab with responsive layout at mobile', () => {
    cy.viewport(375, 667)
    cy.visit('/settings')
    cy.contains('💰 Costos').click()
    cy.contains('Cost Dashboard').should('be.visible')
  })

  it('renders state tab with responsive layout at mobile', () => {
    cy.viewport(375, 667)
    cy.visit('/settings')
    cy.contains('📊 Estado').click()
    cy.contains('Estado de Sesión').should('be.visible')
  })

  it('active tab has brand color and indicator', () => {
    cy.visit('/settings')
    cy.contains('💰 Costos').click()
    cy.get('button').contains('💰 Costos').should('have.class', 'text-brand')
  })
})
