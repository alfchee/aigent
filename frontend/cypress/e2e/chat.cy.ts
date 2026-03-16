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

  it('filtra conversaciones por carpeta y agente', () => {
    cy.visit('/')
    cy.contains('Nueva').click()
    cy.contains('Nueva').click()

    cy.window().then((win) => {
      cy.stub(win, 'prompt').callsFake((label: string) => {
        if (label.includes('Carpeta')) return 'Clientes'
        if (label.includes('Agente')) return 'planner'
        return null
      })
    })

    cy.get('button[aria-label="Cambiar carpeta"]').first().click({ force: true })
    cy.get('button[aria-label="Cambiar agente"]').first().click({ force: true })

    cy.get('select[aria-label="Filtrar por carpeta"]').select('Clientes')
    cy.contains('Clientes').should('exist')

    cy.get('select[aria-label="Filtrar por agente"]').select('planner')
    cy.contains('@planner').should('exist')
  })
})
