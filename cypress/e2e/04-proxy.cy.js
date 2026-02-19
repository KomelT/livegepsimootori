function testPage(page) {
	const origin = page.split("/").slice(0, 3).join("/");
	cy.intercept("GET", `${page}map`).as(`mapLoaded${page}`, {
		statusCode: 200,
		forceNetworkError: true,
	});
	cy.get("#loading-text").should("be.visible");
	cy.get("#loading-text", { timeout: 30000 }).should("not.exist");
	cy.wait(`@mapLoaded${page}`, { timeout: 60000 });
}

context("Test proxy pages", () => {
	after(() => {
		cy.wait(100);
	});

	it("Visit livelox proxy page", () => {
		const page = "https://livelox.track.meshtrail.si/886369/";
		cy.visit(page);
		testPage(page);
	});

	it("Visit loggator proxy page", () => {
		const page = "https://loggator.track.meshtrail.si/EADQWA/";
		cy.visit(page);
		testPage(page);
	});

	it("Visit gpsseuranta proxy page", () => {
		const page = "https://gpsseuranta.track.meshtrail.si/20241205VJyoA/";
		cy.visit(page);
		testPage(page);
	});
});
