describe('Chat', () => {
  it('mantiene scroll solo en la lista de mensajes con alto volumen', () => {
    cy.visit('/')

    cy.contains('Nueva').click()

    const total = 45
    for (let i = 0; i < total; i += 1) {
      cy.get('textarea[aria-label="Escribir mensaje"]').type(`Mensaje ${i}{enter}`)
    }

    cy.contains('Mensaje 44').should('exist')

    cy.get('[data-testid="message-list-scroll"]').then(($el) => {
      const node = $el[0]
      expect(node.scrollHeight).to.be.greaterThan(node.clientHeight)
    })

    cy.window().then((win) => {
      const root = win.document.documentElement
      expect(root.scrollHeight).to.be.lte(win.innerHeight + 2)
    })
  })

  it('conserva layout fijo en mobile, tablet y desktop', () => {
    const viewports: Array<[number, number]> = [
      [320, 640],
      [768, 900],
      [1440, 900],
    ]

    for (const [width, height] of viewports) {
      cy.viewport(width, height)
      cy.visit('/')
      cy.contains('Nueva').click()
      cy.get('[data-testid="chat-page-root"]').should('have.length', 1)
      cy.get('[data-testid="message-list-scroll"]').should('have.length', 1)

      cy.window().then((win) => {
        const root = win.document.documentElement
        expect(root.scrollHeight).to.be.lte(win.innerHeight + 2)
      })
    }
  })
})
